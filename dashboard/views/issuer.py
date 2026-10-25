"""Trang issuer: yêu cầu bị giữ vì lô REVIEW (gửi lại sau khi auditor duyệt), yêu cầu bị từ chối."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import state as S
from dashboard.onchain import b32, clear_selection, s32, transact
from dashboard.tables import STATUS, lot_of, lot_status, rejected, show
from rec.timeutil import day_date


def render() -> None:
    chain = S.chain
    issuer = st.sidebar.selectbox("Tài khoản", ["issuerA", "issuerB"])
    st.title(f"Issuer · {issuer}")
    st.caption("Yêu cầu của lô REVIEW bị giữ, không được lưu on-chain; issuer gửi lại sau khi auditor duyệt.")
    rows = []
    for r in chain.dep.get("held_requests", []):
        if r["issuer"] != issuer:
            continue
        key, _ = lot_of(S.CP, r["day"])
        done = chain.certs.functions.keyUsed(b32(r["device"]), r["day"]).call()
        rows.append({**r, "lô": STATUS[lot_status(key)], "đã phát hành": done})
    df = pd.DataFrame(rows)
    st.subheader("Yêu cầu bị giữ")
    if df.empty:
        st.info("Không có yêu cầu nào bị giữ.")
    else:
        show(pd.DataFrame({"yêu cầu": df["req_id"], "thiết bị": df["device"],
                           "ngày sản xuất": [day_date(d).isoformat() for d in df["day"]],
                           "lượng (kWh)": df["wh"] / 1000, "trạng thái lô": df["lô"], "đã phát hành": df["đã phát hành"]}))
        ready = df[(df["lô"] == "đã duyệt") & ~df["đã phát hành"]]
        if st.button(f"Gửi lại {len(ready)} yêu cầu của các lô đã duyệt", disabled=ready.empty):
            with st.spinner("Đang gửi lại yêu cầu…"):
                for r in ready.itertuples():
                    transact(chain.gate.functions.issue(b32(r.req_id[:31]), b32(r.device), r.day, [int(r.wh)]), issuer)
            st.session_state["flash"] = ("success", f"Đã gửi lại {len(ready)} yêu cầu; xem kết quả ở trang Nhà máy.")
            clear_selection()
            st.rerun()
    st.subheader("Yêu cầu bị từ chối của issuer này")
    devs = {s32(e["deviceId"]) for e in S.ev["DeviceRegistered"] if e["issuer"] == chain.dep["roles"][issuer]}
    show(rejected(lambda e: s32(e["deviceId"]) in devs))
