"""Bảng dữ liệu dựng từ event on-chain, và cách hiển thị bảng thống nhất cho mọi trang."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import state as S
from dashboard.onchain import b32, s32, tx_cell, when
from rec.registry.chain_registry import REASONS
from rec.schema import Flag
from rec.timeutil import day_date

ZERO = "0x" + "0" * 40
STATUS = ["chưa có bằng chứng", "sạch", "REVIEW", "đã duyệt", "bị bác"]
REASON_TEXT = {"key": "trùng (thiết bị, ngày) đã phát hành", "budget": "vượt sản lượng công tơ của CP",
               "capacity": "vượt công suất thiết bị hoặc CP", "period": "kỳ phát hành sai quy định (§8.2)",
               "oracle": "lô chưa có bằng chứng oracle", "lot_rejected": "auditor đã bác lô",
               "not_issuer": "người gửi không phải issuer của thiết bị", "not_registered": "thiết bị chưa đăng ký"}


# ---------------------------------------------------------------------- định dạng

def flags_text(f: int) -> str:
    names = [n for n, v in (("không nhất quán", Flag.INCONSISTENT), ("thiếu báo cáo", Flag.MISSING_REPORT),
                            ("vượt trần", Flag.OVER_CEILING)) if f & int(v)]
    return ", ".join(names) or "—"


def reason_of(e: dict) -> str:
    code = REASONS[int(e["reason"])].value
    return f"{code}: {REASON_TEXT.get(code, '')}"


def tok(tid: int) -> str:
    """tokenId đầy đủ: 0x + 64 chữ số hex (giữ số 0 ở đầu), đúng như trên Etherscan."""
    return f"0x{int(tid):064x}"


def mwh(wh: float) -> str:
    return f"{wh / 1e6:,.2f} MWh"


def column_config(df: pd.DataFrame) -> dict:
    """Định dạng thống nhất: kWh một chữ số thập phân, MWh ba chữ số, liên kết giao dịch."""
    cfg = {}
    for c in df.columns:
        if "(kWh)" in c:
            cfg[c] = st.column_config.NumberColumn(c, format="%.1f")
        elif "(MWh)" in c:
            cfg[c] = st.column_config.NumberColumn(c, format="%.3f")
        elif c == "tokenId (hex)":
            cfg[c] = st.column_config.TextColumn(c, width="large")
        elif c == "giao dịch":
            cfg[c] = st.column_config.LinkColumn(c, display_text="Etherscan") if S.chain.explorer else \
                st.column_config.TextColumn(c)
    return cfg


def show(df: pd.DataFrame, hide: tuple = ()) -> None:
    if df.empty:
        st.info("Không có dòng nào.")
        return
    view = df.drop(columns=[c for c in hide if c in df])
    st.dataframe(view, hide_index=True, width="stretch", column_config=column_config(view))


def pick(df: pd.DataFrame, key: str, hide: tuple = ("tokenId",)) -> int | None:
    """Bảng bấm chọn một dòng; trả chỉ số dòng được chọn."""
    if df.empty:
        st.info("Không có dòng nào.")
        return None
    view = df.drop(columns=[c for c in hide if c in df])
    sel = st.dataframe(view, hide_index=True, width="stretch", on_select="rerun",
                       selection_mode="single-row", key=key, column_config=column_config(view))
    rows = sel.selection.rows
    return rows[0] if rows else None


def section(options: list[str], key: str) -> str:
    """Thanh chọn mục giữ nguyên khi trang tải lại (st.tabs quay về tab đầu sau mỗi lần chọn dòng)."""
    return st.radio("Mục", options, horizontal=True, key=key, label_visibility="collapsed")


# ---------------------------------------------------------------------- bảng

def lot_status(key: bytes) -> int:
    return S.chain.gate.functions.lotState(key).call()[4]


def lot_of(cp: str, day: int):
    key = bytes(S.chain.gate.functions.lotKeyOf(b32(cp), day).call())
    lot = next((e for e in S.ev["LotEvidenced"] if bytes(e["lotKey"]) == key), None)
    return key, lot


def cert_of() -> dict[int, tuple[str, int]]:
    return {int(e["tokenId"]): (s32(e["deviceId"]), int(e["day"])) for e in S.ev["Issued"]}


def token_of(device: str, day: int) -> int | None:
    return next((int(e["tokenId"]) for e in S.ev["Issued"] if s32(e["deviceId"]) == device and int(e["day"]) == day),
                None)


def certificates() -> pd.DataFrame:
    """Một dòng mỗi chứng chỉ (thiết bị-ngày) đã phát hành, kèm lượng đã retire / đã rút và trạng thái khóa."""
    ev = S.ev
    rows = []
    retired, withdrawn, suspended = {}, {}, {}
    for e in ev["Retired"]:
        retired[int(e["tokenId"])] = retired.get(int(e["tokenId"]), 0) + e["wh"]
    for e in ev["Withdrawn"]:
        withdrawn[int(e["tokenId"])] = withdrawn.get(int(e["tokenId"]), 0) + e["wh"]
    for e in sorted(ev["Suspended"], key=lambda x: x["block"]):
        suspended[int(e["tokenId"])] = e["active"]
    cp_of = {s32(e["deviceId"]): s32(e["cpId"]) for e in ev["DeviceRegistered"]}
    for e in ev["Issued"]:
        tid = int(e["tokenId"])
        rows.append({"tokenId": tid, "tokenId (hex)": tok(tid), "thiết bị": s32(e["deviceId"]),
                     "CP": cp_of.get(s32(e["deviceId"]), ""), "ngày sản xuất": day_date(int(e["day"])).isoformat(),
                     "phát hành (kWh)": e["wh"] / 1000, "đã retire (kWh)": retired.get(tid, 0) / 1000,
                     "đã rút (kWh)": withdrawn.get(tid, 0) / 1000,
                     "trạng thái": "tạm khóa" if suspended.get(tid) else "bình thường"})
    return pd.DataFrame(rows)


def balances(df: pd.DataFrame, addr: str, col: str, pos: int = 6) -> pd.DataFrame:
    """Thêm cột số dư ERC-1155 của `addr` cho từng chứng chỉ."""
    if df.empty:
        return df
    bal = S.chain.certs.functions.balanceOfBatch([addr] * len(df), [int(t) for t in df["tokenId"]]).call()
    out = df.copy()
    out.insert(pos, col, [b / 1000 for b in bal])
    return out


def holdings(addr: str) -> pd.DataFrame:
    """Chứng chỉ mà địa chỉ `addr` đang giữ (số dư ERC-1155 > 0)."""
    df = balances(certificates(), addr, "đang giữ (kWh)")
    return df[df["đang giữ (kWh)"] > 0].reset_index(drop=True) if len(df) else df


def transfers(addr: str, outgoing: bool) -> pd.DataFrame:
    """Chuyển nhượng đi (outgoing) hoặc nhận về của một địa chỉ; không tính mint và burn."""
    cmap = cert_of()
    rows = []
    for e in sorted(S.ev["TransferSingle"], key=lambda x: -x["block"]):
        if e["from"] == ZERO or e["to"] == ZERO or (e["from"] if outgoing else e["to"]) != addr:
            continue
        dev, day = cmap.get(int(e["id"]), ("?", 0))
        rows.append({"tokenId": int(e["id"]), "tokenId (hex)": tok(int(e["id"])), "thời điểm": when(e["block"]),
                     ("người nhận" if outgoing else "người chuyển"): S.name_of(e["to"] if outgoing else e["from"]),
                     "thiết bị": dev, "ngày sản xuất": day_date(day).isoformat() if day else "",
                     "lượng (kWh)": e["value"] / 1000, "giao dịch": tx_cell(e["tx"])})
    return pd.DataFrame(rows)


def rejected(keep=lambda e: True) -> pd.DataFrame:
    """Yêu cầu bị lớp A từ chối (mới nhất trước), kèm lý do lưu on-chain."""
    return pd.DataFrame([{"thời điểm": when(e["block"]), "yêu cầu": s32(e["reqId"]), "thiết bị": s32(e["deviceId"]),
                          "ngày sản xuất": day_date(int(e["day"])).isoformat(), "lý do": reason_of(e),
                          "giao dịch": tx_cell(e["tx"])}
                         for e in sorted(S.ev["IssueRejected"], key=lambda x: -x["block"]) if keep(e)])


def held_info() -> dict[str, dict]:
    """Yêu cầu bị giữ mà issuer lưu off-chain (on-chain chỉ có reqId và lô)."""
    return {r["req_id"]: r for r in S.chain.dep.get("held_requests", [])}


def requests_of_cp(cp: str) -> pd.DataFrame:
    """Mọi yêu cầu phát hành bị từ chối hoặc đang bị giữ tại CP, kèm thời điểm và lý do."""
    ev = S.ev
    devs = {s32(e["deviceId"]): S.name_of(e["issuer"]) for e in ev["DeviceRegistered"] if s32(e["cpId"]) == cp}
    info_of = held_info()
    lots = {bytes(e["lotKey"]): e for e in ev["LotEvidenced"]}
    rows = []
    for e in ev["IssueRejected"]:
        dev = s32(e["deviceId"])
        if dev in devs:
            rows.append({"thời điểm": when(e["block"]), "kết cục": "bị từ chối", "thiết bị": dev, "issuer": devs[dev],
                         "ngày sản xuất": day_date(int(e["day"])).isoformat(), "lý do": reason_of(e),
                         "yêu cầu": s32(e["reqId"]), "giao dịch": tx_cell(e["tx"])})
    seen = set()
    for e in ev["IssueHeld"]:
        rid, key = s32(e["reqId"]), bytes(e["lotKey"])
        if rid in seen or key not in lots or lot_status(key) != 2:  # chỉ yêu cầu của lô còn REVIEW
            continue
        seen.add(rid)
        info = info_of.get(rid, {})
        rows.append({"thời điểm": when(e["block"]), "kết cục": "bị giữ (chờ auditor)",
                     "thiết bị": info.get("device", "—"), "issuer": info.get("issuer", "—"),
                     "ngày sản xuất": day_date(int(lots[key]["day"])).isoformat(),
                     "lý do": "lô bị lớp B đánh dấu: " + flags_text(int(lots[key]["flags"])),
                     "yêu cầu": rid, "giao dịch": tx_cell(e["tx"])})
    return pd.DataFrame(rows).sort_values("thời điểm", ascending=False).reset_index(drop=True) if rows else \
        pd.DataFrame()


def production_by_day(cp: str) -> pd.DataFrame:
    """Mỗi ngày sản xuất: sản lượng công tơ (O1), lượng đã phát hành, số yêu cầu bị giữ / bị từ chối."""
    ev = S.ev
    devs = {s32(e["deviceId"]) for e in ev["DeviceRegistered"] if s32(e["cpId"]) == cp}
    issued, n_cert, n_rej = {}, {}, {}
    for e in ev["Issued"]:
        if s32(e["deviceId"]) in devs:
            d = int(e["day"])
            issued[d] = issued.get(d, 0) + e["wh"]
            n_cert[d] = n_cert.get(d, 0) + 1
    for e in ev["IssueRejected"]:
        if s32(e["deviceId"]) in devs:
            n_rej[int(e["day"])] = n_rej.get(int(e["day"]), 0) + 1
    rows = []
    for e in ev["LotEvidenced"]:
        if s32(e["cpId"]) != cp:
            continue
        d = int(e["day"])
        rows.append({"day": d, "ngày sản xuất": day_date(d).isoformat(), "công tơ O1 (kWh)": e["o1Wh"] / 1000,
                     "đã phát hành (kWh)": issued.get(d, 0) / 1000, "chứng chỉ": n_cert.get(d, 0),
                     "yêu cầu bị từ chối": n_rej.get(d, 0), "cờ lớp B": flags_text(int(e["flags"])),
                     "trạng thái lô": STATUS[lot_status(bytes(e["lotKey"]))], "gửi bằng chứng lúc": when(e["block"])})
    return pd.DataFrame(rows).sort_values("day").reset_index(drop=True) if rows else pd.DataFrame()
