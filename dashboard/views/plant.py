"""Trang nhà máy: sản xuất theo ngày, chứng chỉ đang giữ (chuyển nhượng, retire), yêu cầu bị từ chối / bị giữ."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import state as S
from dashboard.components import certificate_detail, evidence_block, transfer_and_retire
from dashboard.onchain import s32, tx_cell, when
from dashboard.tables import (held_info, holdings, lot_of, mwh, pick, production_by_day, reason_of, requests_of_cp,
                              section, show, transfers)
from rec.timeutil import day_date


def _day_outcomes(d: int, key: bytes) -> pd.DataFrame:
    """Kết cục của từng thiết bị trong một ngày: đã phát hành, bị từ chối (kèm lý do) hoặc đang bị giữ."""
    ev, info = S.ev, held_info()
    rows = [{"thiết bị": s32(e["deviceId"]), "kết cục": "đã phát hành", "lượng (kWh)": e["wh"] / 1000,
             "lý do": "", "thời điểm": when(e["block"]), "giao dịch": tx_cell(e["tx"])}
            for e in ev["Issued"] if int(e["day"]) == d]
    rows += [{"thiết bị": s32(e["deviceId"]), "kết cục": "bị từ chối", "lượng (kWh)": None,
              "lý do": reason_of(e), "thời điểm": when(e["block"]), "giao dịch": tx_cell(e["tx"])}
             for e in ev["IssueRejected"] if int(e["day"]) == d]
    done = {r["thiết bị"] for r in rows if r["kết cục"] == "đã phát hành"}
    rows += [{"thiết bị": info[s32(e["reqId"])]["device"], "kết cục": "bị giữ (chờ auditor)",
              "lượng (kWh)": info[s32(e["reqId"])]["wh"] / 1000, "lý do": "lô bị lớp B đánh dấu",
              "thời điểm": when(e["block"]), "giao dịch": tx_cell(e["tx"])}
             for e in ev["IssueHeld"] if bytes(e["lotKey"]) == key and s32(e["reqId"]) in info
             and info[s32(e["reqId"])]["device"] not in done]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values(["thiết bị", "thời điểm"])
    # Yêu cầu bị từ chối không có lượng on-chain: hiện "—" thay vì "None".
    df["lượng"] = [f"{v:,.1f} kWh" if pd.notna(v) else "—" for v in df.pop("lượng (kWh)")]
    return df[["thiết bị", "kết cục", "lượng", "lý do", "thời điểm", "giao dịch"]]


def render() -> None:
    st.title(f"Nhà máy · {S.CP}")
    st.caption("Chứng chỉ được MINT thẳng vào địa chỉ của nhà máy khi lô qua lớp A và lớp B. Nhà máy bán cho người mua "
               "bằng cách chuyển nhượng (thanh toán nằm ngoài hệ thống), hoặc tự retire nếu tự dùng điện.")
    prod = production_by_day(S.CP)
    mine = holdings(S.PLANT)
    sent = transfers(S.PLANT, outgoing=True)
    pending = requests_of_cp(S.CP)
    n_held = int((pending["kết cục"] == "bị giữ (chờ auditor)").sum()) if len(pending) else 0
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Sản lượng công tơ", mwh(prod["công tơ O1 (kWh)"].sum() * 1000) if len(prod) else "0")
    c2.metric("Đã phát hành", mwh(prod["đã phát hành (kWh)"].sum() * 1000) if len(prod) else "0")
    c3.metric("Đang giữ", mwh(mine["đang giữ (kWh)"].sum() * 1000) if len(mine) else "0")
    c4.metric("Đã chuyển nhượng", mwh(sent["lượng (kWh)"].sum() * 1000) if len(sent) else "0")
    c5.metric("Chờ auditor", f"{n_held} yêu cầu")
    sec = section(["Sản xuất theo ngày", "Chứng chỉ đang giữ", "Bị từ chối / bị giữ", "Đã chuyển nhượng"], "plant-sec")
    if sec == "Sản xuất theo ngày":
        st.caption("Mỗi dòng là một ngày sản xuất của cả nhà máy (một lô). Bấm vào một ngày để xem số liệu công tơ, "
                   "inverter, bức xạ và kết cục của từng thiết bị.")
        i = pick(prod, "plant-days", hide=("day",))
        if i is not None:
            d = int(prod.iloc[i]["day"])
            key, lot = lot_of(S.CP, d)
            st.markdown(f"#### Ngày sản xuất {day_date(d)}")
            show(_day_outcomes(d, key))
            if lot:
                evidence_block(key, lot)
    elif sec == "Chứng chỉ đang giữ":
        st.caption("Bấm vào một dòng để chuyển nhượng, retire, hoặc xem chuỗi truy vết.")
        i = pick(mine, "plant-certs")
        if i is not None:
            row = mine.iloc[i]
            transfer_and_retire("plant", row, ["buyer1", "buyer2", "buyer3"])
            certificate_detail(int(row["tokenId"]))
    elif sec == "Bị từ chối / bị giữ":
        st.caption("Mọi yêu cầu phát hành tại CP này bị lớp A từ chối (kèm lý do on-chain) hoặc đang bị giữ chờ "
                   "auditor. Cột issuer cho biết ai gửi: yêu cầu của thiết bị lạ cùng CP (ví dụ X-D4a) cũng hiện ở đây.")
        show(pending)
    else:
        st.caption("Nhà máy chuyển chứng chỉ cho người mua ở mục \"Chứng chỉ đang giữ\" (chọn chứng chỉ → form Chuyển "
                   "nhượng). Mỗi lần chuyển là một giao dịch ERC-1155 công khai.")
        i = pick(sent, "plant-sent")
        if i is not None:
            certificate_detail(int(sent.iloc[i]["tokenId"]))
