"""Bộ chạy dòng sự kiện qua một backend `Registry` theo đồng hồ mô phỏng (FLOW.md mục 11).

Runner không đọc nhãn. Đầu ra là nhật ký quyết định: mỗi thao tác một dòng
`t, kind, id, issuer, device, day, outcome, reason, wh, minted_wh, trace, gas`.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from rec.generator.common import EVIDENCE_AT, INVERTER_MAX_W, REPORT_AT, local_t
from rec.generator.honest import PLANT
from rec.generator.io import read_events
from rec.registry.base import LotEvidence, Plant, Registry
from rec.schema import Event, EventKind, OracleId

ORDER = (OracleId.O1, OracleId.O2, OracleId.O3, OracleId.O4)
B1_MODEL_HASH = bytes.fromhex("00" * 32)


def plant_from_config(plant_cfg: dict) -> Plant:
    cap = INVERTER_MAX_W * sum(len(v) for v in plant_cfg["devices"].values())
    return Plant(cp_capacity_w={plant_cfg["cp_id"]: cap}, holder_of={plant_cfg["cp_id"]: PLANT},
                 issuers=tuple(plant_cfg["issuers"]))


def load_stream(e1_dir: Path, base: str, overlay: str | None = None) -> list[Event]:
    """Dòng hợp lệ `base` cộng sự kiện tấn công `overlay` (bỏ các yêu cầu hợp lệ bị thay), sắp theo thời gian."""
    events = list(read_events(e1_dir / f"{base}.jsonl"))
    if overlay is not None:
        removed = set(json.loads((e1_dir / f"{overlay}.removed.json").read_text(encoding="utf-8")))
        events = [e for e in events if not (e.kind is EventKind.REQUEST and e.payload.req_id in removed)]
        events += list(read_events(e1_dir / f"{overlay}.jsonl"))
    return sorted(events, key=lambda e: e.t)  # sắp ổn định: cùng t thì dòng hợp lệ đi trước


REVIEW_AT = 23 * 3600  # auditor xử lý hàng đợi REVIEW lúc 23:00 ngày d + 1 (FLOW mục 5)


def run_stream(backend: Registry, events: list[Event], sun_slots: dict[int, int], evidence_issuer: str,
               verdict_of=None, auditor=None) -> list[dict]:
    """Chạy một dòng sự kiện.

    `verdict_of(cp, day, reports) → LotEvidence` thay verdict mặc định (cờ 0, tức cấu hình B1 ở chế độ R1).
    `auditor(cp, day) → bool`: phân xử lô REVIEW lúc 23:00 ngày d + 1; duyệt thì issuer gửi lại các yêu cầu bị giữ.
    """
    log: list[dict] = []
    pending: dict[tuple[str, int], dict] = defaultdict(dict)
    held: dict[tuple[str, int], list] = {}

    def flush_reviews(now: int | None) -> None:
        for (cp, day) in sorted(held, key=lambda k: k[1]):
            t_rev = local_t(day + 1, REVIEW_AT)
            if now is not None and t_rev > now:
                continue
            reqs = held.pop((cp, day))
            out = backend.resolve_review(cp, day, bool(auditor(cp, day)), t_rev)
            log.append({"t": t_rev, "kind": "resolve_review", "id": f"lot:{cp}:{day}", "issuer": "auditor",
                        "device": "", "day": day, "outcome": out.kind, "reason": out.reason, "wh": 0, "minted_wh": 0,
                        "req_days": "", "minted_days": "", "trace": True, "gas": out.gas})
            for i, (e, p) in enumerate(reqs):
                retry = Event(t_rev + 60 + i, e.kind, p)
                row(retry, p.req_id, p.issuer, p.device_id, p.day_start, backend.issue(p, retry.t), p.total_wh,
                    ";".join(f"{d}:{w}" for d, w in zip(p.days, p.wh_per_day) if w), kind="request_retry")

    def row(e: Event, ident: str, issuer: str, device: str, day: int, out, wh: int = 0, req_days: str = "",
            kind: str | None = None) -> None:
        log.append({"t": e.t, "kind": kind or e.kind.value, "id": ident, "issuer": issuer, "device": device, "day": day,
                    "outcome": out.kind, "reason": out.reason, "wh": wh, "minted_wh": out.minted_wh,
                    "req_days": req_days, "minted_days": ";".join(f"{d}:{w}" for _, d, w in out.minted),
                    "trace": out.trace, "gas": out.gas})

    for e in events:
        if held:
            flush_reviews(e.t)
        p = e.payload
        if e.kind is EventKind.REPORT:
            reps = pending[(p.subject, p.day)]
            reps[p.oracle] = p
            if len(reps) == len(ORDER):
                del pending[(p.subject, p.day)]
                reports = tuple(reps.get(o) for o in ORDER)
                ev = (verdict_of(p.subject, p.day, reports) if verdict_of else
                      LotEvidence(p.subject, p.day, reports, 0, sun_slots[p.day], model_hash=B1_MODEL_HASH))
                t_ev = e.t + (EVIDENCE_AT - REPORT_AT)
                out = backend.submit_lot_evidence(ev, evidence_issuer, t_ev)
                log.append({"t": t_ev, "kind": "evidence", "id": f"lot:{p.subject}:{p.day}", "issuer": evidence_issuer,
                            "device": "", "day": p.day, "outcome": out.kind, "reason": out.reason, "wh": p.wh_day
                            if p.oracle is OracleId.O1 else reps[OracleId.O1].wh_day, "minted_wh": 0, "req_days": "",
                            "minted_days": "", "trace": True, "gas": out.gas})
        elif e.kind is EventKind.REGISTER:
            row(e, f"register:{p.device_id}:{p.issuer}", p.issuer, p.device_id, p.effective_day,
                backend.register_device(p, e.t))
        elif e.kind is EventKind.TRANSFER_REGISTRATION:
            row(e, f"transfer_registration:{p.device_id}", p.from_issuer, p.device_id, p.effective_day,
                backend.transfer_registration(p, e.t))
        elif e.kind is EventKind.DEREGISTER:
            row(e, f"deregister:{p.device_id}", p.issuer, p.device_id, p.effective_day,
                backend.close_registration(p, e.t))
        elif e.kind is EventKind.REQUEST:
            out = backend.issue(p, e.t)
            row(e, p.req_id, p.issuer, p.device_id, p.day_start, out, p.total_wh,
                ";".join(f"{d}:{w}" for d, w in zip(p.days, p.wh_per_day) if w))
            if out.kind == "held" and auditor is not None:
                held.setdefault((backend_cp(backend, p), p.day_start), []).append((e, p))
        elif e.kind is EventKind.TRANSFER:
            row(e, p.ref or f"transfer:{p.device_id}:{p.day}:{p.recipient}", p.sender, p.device_id, p.day,
                backend.transfer(p, e.t), p.wh)
        elif e.kind is EventKind.RETIRE:
            row(e, p.ref or f"retire:{p.device_id}:{p.day}", p.holder, p.device_id, p.day, backend.retire(p, e.t), p.wh)
        elif e.kind is EventKind.SUSPEND:
            row(e, f"suspend:{p.device_id}:{p.day}", "codeManager", p.device_id, p.day,
                backend.suspend(p.device_id, p.day, p.active, p.reason, e.t))
        elif e.kind is EventKind.WITHDRAW:
            row(e, f"withdraw:{p.device_id}:{p.day}", "codeManager", p.device_id, p.day,
                backend.withdraw(p.device_id, p.day, p.holder, p.wh, p.reason, e.t), p.wh)
        elif e.kind is EventKind.OPERATOR_EDIT:
            row(e, p.ref or f"edit:{p.target_req_id}", p.issuer, "", 0, backend.operator_edit(p, e.t))
    if held:
        flush_reviews(None)
    return log


def backend_cp(backend: Registry, req) -> str:
    """CP của thiết bị trong yêu cầu; dòng sự kiện của đề tài chỉ có một CP."""
    return next(iter(backend.plant.cp_capacity_w)) if hasattr(backend, "plant") else ""
