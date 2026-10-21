"""B0: registry tập trung trên SQLite, cùng các kiểm tra lớp A như contract (PLAN.md mục 4.2).

- `SqliteRegistry` (b0_shared): một CSDL dùng chung cho mọi issuer.
- `SeparateRegistry` (b0_separate): mỗi issuer một CSDL; khóa và ngân sách chỉ thấy dữ liệu của issuer đó.
  `reconcile()` gộp các CSDL rồi chạy lại khóa và ngân sách CP để tìm bản trùng đã phát hành.

Khác với chain, người vận hành CSDL có `operator_edit`: sửa, xóa, phát hành lại mà không để dấu vết (insider).
"""
from __future__ import annotations

import sqlite3

from rec.registry.base import (DAY_END_OFFSET_S, DAY_S, SLOTS_PER_HOUR, LotEvidence, Outcome, Plant, Registry,
                               reject)
from rec.schema import (GROUP_MAX_CAPACITY_W, GROUP_MAX_MEMBERS, Deregistration, Device, EditAction, IssueRequest,
                        OperatorEdit, RegistrationTransfer, RejectReason, Retire, Transfer, token_key)
from rec.timeutil import day_date

OPEN = 2**32 - 1
CLEAR, REVIEW, APPROVED, REJECTED = "clear", "review", "approved", "rejected"

_SCHEMA = """
CREATE TABLE devices (device_id TEXT PRIMARY KEY, cp_id TEXT, cap_w INTEGER, effective_day INTEGER,
                      end_day INTEGER, is_group INTEGER, member_count INTEGER);
CREATE TABLE stewards (device_id TEXT, from_day INTEGER, issuer TEXT);
CREATE TABLE lots (cp_id TEXT, day INTEGER, o1 INTEGER, max_slot INTEGER, sun_slots INTEGER, flags INTEGER,
                   status TEXT, issued_wh INTEGER DEFAULT 0, PRIMARY KEY (cp_id, day));
CREATE TABLE issued (token_key TEXT PRIMARY KEY, device_id TEXT, cp_id TEXT, day INTEGER, wh INTEGER,
                     req_id TEXT, t INTEGER, retired_wh INTEGER DEFAULT 0, suspended INTEGER DEFAULT 0);
CREATE TABLE holdings (token_key TEXT, holder TEXT, wh INTEGER, PRIMARY KEY (token_key, holder));
CREATE TABLE retirements (token_key TEXT, holder TEXT, wh INTEGER, beneficiary TEXT, purpose TEXT,
                          location TEXT, period TEXT, t INTEGER);
"""


class Ledger:
    """Một CSDL SQLite với đủ kiểm tra lớp A (giống DecisionGate + CertificateRegistry)."""

    def __init__(self, plant: Plant, path: str = ":memory:"):
        self.plant = plant
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.executescript(_SCHEMA)

    def q(self, sql: str, *args):
        return self.db.execute(sql, args)

    def one(self, sql: str, *args):
        return self.db.execute(sql, args).fetchone()

    # ---------------------------------------------------------------- đăng ký

    def register_device(self, dev: Device) -> Outcome:
        if dev.issuer not in self.plant.issuers:
            return Outcome("revert", "NotIssuer")
        if self.one("SELECT 1 FROM devices WHERE device_id = ?", dev.device_id):
            return Outcome("revert", "DuplicateDevice")
        cp_cap = self.plant.cp_capacity_w.get(dev.cp_id, 0)
        if cp_cap == 0:
            return Outcome("revert", "UnknownCP")
        if not 0 < dev.ac_capacity_w <= cp_cap:
            return Outcome("revert", "InvalidCapacity")
        if dev.is_group and (dev.ac_capacity_w > GROUP_MAX_CAPACITY_W or not 1 <= dev.member_count <= GROUP_MAX_MEMBERS):
            return Outcome("revert", "InvalidGroup")
        self.q("INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?)", dev.device_id, dev.cp_id, dev.ac_capacity_w,
               dev.effective_day, OPEN, int(dev.is_group), dev.member_count if dev.is_group else 1)
        self.q("INSERT INTO stewards VALUES (?, ?, ?)", dev.device_id, dev.effective_day, dev.issuer)
        return Outcome("ok")

    def current_issuer(self, device_id: str) -> tuple[int, str] | None:
        return self.one("SELECT from_day, issuer FROM stewards WHERE device_id = ? ORDER BY from_day DESC LIMIT 1",
                        device_id)

    def issuer_on(self, device_id: str, day: int) -> str | None:
        row = self.one("SELECT issuer FROM stewards WHERE device_id = ? AND from_day <= ? ORDER BY from_day DESC "
                       "LIMIT 1", device_id, day)
        return row[0] if row else None

    def transfer_registration(self, rt: RegistrationTransfer) -> Outcome:
        cur = self.current_issuer(rt.device_id)
        if cur is None:
            return Outcome("revert", "UnknownDevice")
        if cur[1] != rt.from_issuer:
            return Outcome("revert", "NotCurrentIssuer")
        if rt.to_issuer not in self.plant.issuers:
            return Outcome("revert", "NotIssuer")
        end_day = self.one("SELECT end_day FROM devices WHERE device_id = ?", rt.device_id)[0]
        if not cur[0] < rt.effective_day < end_day:
            return Outcome("revert", "InvalidDay")
        self.q("INSERT INTO stewards VALUES (?, ?, ?)", rt.device_id, rt.effective_day, rt.to_issuer)
        return Outcome("ok")

    def close_registration(self, dr: Deregistration) -> Outcome:
        cur = self.current_issuer(dr.device_id)
        if cur is None:
            return Outcome("revert", "UnknownDevice")
        if cur[1] != dr.issuer:
            return Outcome("revert", "NotCurrentIssuer")
        eff, end = self.one("SELECT effective_day, end_day FROM devices WHERE device_id = ?", dr.device_id)
        if dr.effective_day < eff or end != OPEN:
            return Outcome("revert", "InvalidDay")
        self.q("UPDATE devices SET end_day = ? WHERE device_id = ?", dr.effective_day, dr.device_id)
        return Outcome("ok")

    # ---------------------------------------------------------------- bằng chứng của lô và phát hành

    def submit_lot_evidence(self, ev: LotEvidence) -> Outcome:
        o1 = ev.o1
        row = self.one("SELECT o1 FROM lots WHERE cp_id = ? AND day = ?", ev.cp_id, ev.day)
        if row is not None:
            return Outcome("reject" if row[0] != o1.wh_day else "revert",
                           "O1Conflict" if row[0] != o1.wh_day else "LotAlreadyEvidenced")
        self.q("INSERT INTO lots (cp_id, day, o1, max_slot, sun_slots, flags, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
               ev.cp_id, ev.day, o1.wh_day, o1.max_slot_wh, ev.sun_slots, ev.flags, CLEAR if ev.flags == 0 else REVIEW)
        return Outcome("ok")

    def resolve_review(self, cp_id: str, day: int, approve: bool) -> Outcome:
        row = self.one("SELECT status FROM lots WHERE cp_id = ? AND day = ?", cp_id, day)
        if row is None or row[0] != REVIEW:
            return Outcome("revert", "NotUnderReview")
        self.q("UPDATE lots SET status = ? WHERE cp_id = ? AND day = ?", APPROVED if approve else REJECTED, cp_id, day)
        return Outcome("ok")

    def issue(self, req: IssueRequest, t: int) -> Outcome:
        dev = self.one("SELECT cp_id, cap_w, effective_day, end_day FROM devices WHERE device_id = ?", req.device_id)
        if req.issuer not in self.plant.issuers:
            return Outcome("revert", "NotIssuer")
        if dev is None:
            return reject(RejectReason.NOT_REGISTERED)
        cp_id, cap_w, eff, end = dev
        day_end = req.day_start + len(req.wh_per_day) - 1
        if (day_date(req.day_start).year != day_date(day_end).year or req.day_start < eff or day_end >= end
                or t < (day_end + 1) * DAY_S + DAY_END_OFFSET_S):
            return reject(RejectReason.PERIOD)
        for d in req.days:
            if self.issuer_on(req.device_id, d) != req.issuer:
                return reject(RejectReason.NOT_ISSUER)
        cp_cap = self.plant.cp_capacity_w[cp_id]
        held = False
        for d, wh in zip(req.days, req.wh_per_day):
            if wh == 0:
                continue
            if self.one("SELECT 1 FROM issued WHERE token_key = ?", token_key(req.device_id, d)):
                return reject(RejectReason.KEY)
            lot = self.one("SELECT o1, max_slot, sun_slots, status, issued_wh FROM lots WHERE cp_id = ? AND day = ?",
                           cp_id, d)
            if lot is None:
                return reject(RejectReason.ORACLE)
            o1, max_slot, sun, status, issued_wh = lot
            if issued_wh + wh > o1:
                return reject(RejectReason.BUDGET)
            if (wh * SLOTS_PER_HOUR > cap_w * sun or max_slot * SLOTS_PER_HOUR > cp_cap
                    or o1 * SLOTS_PER_HOUR > cp_cap * sun):
                return reject(RejectReason.CAPACITY)
            if status == REJECTED:
                return reject(RejectReason.LOT_REJECTED)
            held |= status == REVIEW
        if held:
            return Outcome("held")
        holder = self.plant.holder_of[cp_id]
        minted = []
        for d, wh in zip(req.days, req.wh_per_day):
            if wh == 0:
                continue
            key = token_key(req.device_id, d)
            self.q("INSERT INTO issued (token_key, device_id, cp_id, day, wh, req_id, t) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   key, req.device_id, cp_id, d, wh, req.req_id, t)
            self.q("UPDATE lots SET issued_wh = issued_wh + ? WHERE cp_id = ? AND day = ?", wh, cp_id, d)
            self._credit(key, holder, wh)
            minted.append((req.device_id, d, wh))
        return Outcome("mint", minted=tuple(minted))

    # ---------------------------------------------------------------- vòng đời

    def _credit(self, key: str, holder: str, wh: int) -> None:
        self.q("INSERT INTO holdings VALUES (?, ?, ?) ON CONFLICT(token_key, holder) DO UPDATE SET wh = wh + ?",
               key, holder, wh, wh)

    def balance(self, key: str, holder: str) -> int:
        row = self.one("SELECT wh FROM holdings WHERE token_key = ? AND holder = ?", key, holder)
        return row[0] if row else 0

    def _token(self, key: str):
        return self.one("SELECT suspended, retired_wh, cp_id, day, wh FROM issued WHERE token_key = ?", key)

    def transfer(self, tr: Transfer) -> Outcome:
        key = token_key(tr.device_id, tr.day)
        tok = self._token(key)
        if tok and tok[0]:
            return Outcome("revert", "TokenSuspended")
        if self.balance(key, tr.sender) < tr.wh:
            return Outcome("revert", "ERC1155InsufficientBalance")
        self.q("UPDATE holdings SET wh = wh - ? WHERE token_key = ? AND holder = ?", tr.wh, key, tr.sender)
        self._credit(key, tr.recipient, tr.wh)
        return Outcome("ok")

    def retire(self, rt: Retire, t: int) -> Outcome:
        key = token_key(rt.device_id, rt.day)
        tok = self._token(key)
        if tok is None:
            return Outcome("revert", "UnknownToken")
        if tok[0]:
            return Outcome("revert", "TokenSuspended")
        if self.balance(key, rt.holder) < rt.wh:
            return Outcome("revert", "ERC1155InsufficientBalance")
        self.q("UPDATE holdings SET wh = wh - ? WHERE token_key = ? AND holder = ?", rt.wh, key, rt.holder)
        self.q("UPDATE issued SET retired_wh = retired_wh + ? WHERE token_key = ?", rt.wh, key)
        self.q("INSERT INTO retirements VALUES (?, ?, ?, ?, ?, ?, ?, ?)", key, rt.holder, rt.wh, rt.beneficiary,
               rt.purpose, rt.consumption_location, rt.reporting_period, t)
        return Outcome("ok")

    def suspend(self, device_id: str, day: int, active: bool) -> Outcome:
        key = token_key(device_id, day)
        if self._token(key) is None:
            return Outcome("revert", "UnknownToken")
        self.q("UPDATE issued SET suspended = ? WHERE token_key = ?", int(active), key)
        return Outcome("ok")

    def withdraw(self, device_id: str, day: int, holder: str, wh: int) -> Outcome:
        key = token_key(device_id, day)
        tok = self._token(key)
        if tok is None:
            return Outcome("revert", "UnknownToken")
        if self.balance(key, holder) < wh:
            return Outcome("revert", "ERC1155InsufficientBalance")
        _, retired, cp_id, d, _ = tok
        self.q("UPDATE holdings SET wh = wh - ? WHERE token_key = ? AND holder = ?", wh, key, holder)
        self.q("UPDATE lots SET issued_wh = issued_wh - ? WHERE cp_id = ? AND day = ?", wh, cp_id, d)
        left = self.one("SELECT COALESCE(SUM(wh), 0) FROM holdings WHERE token_key = ?", key)[0]
        if left == 0 and retired == 0:
            self.q("DELETE FROM issued WHERE token_key = ?", key)
        return Outcome("ok")

    def operator_edit(self, edit: OperatorEdit) -> Outcome:
        """Người vận hành CSDL sửa thẳng bảng: không qua kiểm tra, không ghi lại ở đâu."""
        row = self.one("SELECT token_key, cp_id, wh FROM issued WHERE req_id = ?", edit.target_req_id)
        if row is None:
            return Outcome("revert", "UnknownRecord")
        key, cp_id, wh = row
        holder = self.plant.holder_of[cp_id]
        if edit.action is EditAction.UPDATE:  # khai tăng lượng đã phát hành lên gấp đôi
            self.q("UPDATE issued SET wh = wh * 2 WHERE token_key = ?", key)
            self._credit(key, holder, wh)
        elif edit.action is EditAction.DELETE:  # xóa bản ghi: mất dấu vết phát hành
            self.q("DELETE FROM issued WHERE token_key = ?", key)
            self.q("DELETE FROM holdings WHERE token_key = ?", key)
        else:  # phát hành lại cùng (thiết bị, ngày) lần thứ hai
            self._credit(key, holder, wh)
        return Outcome("ok", trace=False)

    def issued_rows(self) -> list[tuple]:
        return self.q("SELECT token_key, device_id, cp_id, day, wh, req_id, t FROM issued").fetchall()

    def o1_of(self) -> dict[tuple[str, int], int]:
        return {(c, d): o1 for c, d, o1 in self.q("SELECT cp_id, day, o1 FROM lots")}


class SqliteRegistry(Registry):
    """b0_shared: một CSDL dùng chung."""

    name = "b0_shared"

    def __init__(self, plant: Plant):
        self.ledger = Ledger(plant)

    def register_device(self, dev, t):
        return self.ledger.register_device(dev)

    def transfer_registration(self, rt, t):
        return self.ledger.transfer_registration(rt)

    def close_registration(self, dr, t):
        return self.ledger.close_registration(dr)

    def submit_lot_evidence(self, ev, issuer, t):
        return self.ledger.submit_lot_evidence(ev)

    def resolve_review(self, cp_id, day, approve, t):
        return self.ledger.resolve_review(cp_id, day, approve)

    def issue(self, req, t):
        return self.ledger.issue(req, t)

    def transfer(self, tr, t):
        return self.ledger.transfer(tr)

    def retire(self, rt, t):
        return self.ledger.retire(rt, t)

    def suspend(self, device_id, day, active, reason, t):
        return self.ledger.suspend(device_id, day, active)

    def withdraw(self, device_id, day, holder, wh, reason, t):
        return self.ledger.withdraw(device_id, day, holder, wh)

    def operator_edit(self, edit, t):
        return self.ledger.operator_edit(edit)


class SeparateRegistry(Registry):
    """b0_separate: mỗi issuer một CSDL. Báo cáo O1 của điện lực (R1) được gửi tới mọi issuer."""

    name = "b0_separate"

    def __init__(self, plant: Plant):
        self.plant = plant
        self.dbs = {issuer: Ledger(plant) for issuer in plant.issuers}

    def register_device(self, dev, t):
        return self.dbs[dev.issuer].register_device(dev)

    def transfer_registration(self, rt, t):
        """Issuer cũ đóng đăng ký từ ngày hiệu lực; issuer mới mở bản ghi cùng mã trong CSDL của mình."""
        old, new = self.dbs[rt.from_issuer], self.dbs[rt.to_issuer]
        row = old.one("SELECT cp_id, cap_w, is_group, member_count FROM devices WHERE device_id = ?", rt.device_id)
        if row is None:
            return Outcome("revert", "UnknownDevice")
        out = old.close_registration(Deregistration(rt.device_id, rt.from_issuer, rt.effective_day))
        if out.kind != "ok":
            return out
        return new.register_device(Device(rt.device_id, row[0], row[1], rt.to_issuer, rt.effective_day,
                                          bool(row[2]), row[3]))

    def close_registration(self, dr, t):
        return self.dbs[dr.issuer].close_registration(dr)

    def submit_lot_evidence(self, ev, issuer, t):
        outs = [db.submit_lot_evidence(ev) for db in self.dbs.values()]
        return outs[0]

    def resolve_review(self, cp_id, day, approve, t):
        return [db.resolve_review(cp_id, day, approve) for db in self.dbs.values()][0]

    def issue(self, req, t):
        return self.dbs[req.issuer].issue(req, t)

    def _holding_db(self, device_id: str, day: int, holder: str, wh: int) -> Ledger:
        key = token_key(device_id, day)
        for db in self.dbs.values():
            if db.balance(key, holder) >= wh:
                return db
        return next(iter(self.dbs.values()))

    def transfer(self, tr, t):
        return self._holding_db(tr.device_id, tr.day, tr.sender, tr.wh).transfer(tr)

    def retire(self, rt, t):
        return self._holding_db(rt.device_id, rt.day, rt.holder, rt.wh).retire(rt, t)

    def suspend(self, device_id, day, active, reason, t):
        outs = [db.suspend(device_id, day, active) for db in self.dbs.values()]
        return next((o for o in outs if o.kind == "ok"), outs[0])

    def withdraw(self, device_id, day, holder, wh, reason, t):
        return self._holding_db(device_id, day, holder, wh).withdraw(device_id, day, holder, wh)

    def operator_edit(self, edit, t):
        return self.dbs[edit.issuer].operator_edit(edit)

    def reconcile(self, t: int) -> list[dict]:
        """Gộp các CSDL, chạy lại khóa và ngân sách CP; trả các bản ghi vi phạm (bản phát hành sau)."""
        rows = sorted(((r[6], issuer) + r for issuer, db in self.dbs.items() for r in db.issued_rows()
                       if r[6] <= t), key=lambda x: (x[0], x[1]))
        o1 = {}
        for db in self.dbs.values():
            o1.update(db.o1_of())
        seen, budget, found = set(), {}, []
        for t_mint, issuer, key, device, cp, day, wh, req_id, _ in rows:
            used = budget.get((cp, day), 0) + wh
            budget[(cp, day)] = used
            if key in seen:
                found.append({"req_id": req_id, "issuer": issuer, "t_mint": t_mint, "rule": "key"})
            elif used > o1.get((cp, day), 0):
                found.append({"req_id": req_id, "issuer": issuer, "t_mint": t_mint, "rule": "budget"})
            seen.add(key)
        return found
