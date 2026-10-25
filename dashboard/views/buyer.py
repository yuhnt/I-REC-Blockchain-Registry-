"""Trang người mua: chứng chỉ đang giữ, chứng chỉ trên hệ thống, lịch sử nhận, tuyên bố đã retire."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import state as S
from dashboard.components import certificate_detail, statement, transfer_and_retire
from dashboard.onchain import when
from dashboard.tables import balances, cert_of, certificates, holdings, mwh, pick, section, tok, transfers

BUYERS = ["buyer1", "buyer2", "buyer3"]


def render() -> None:
    buyer = st.sidebar.selectbox("Tài khoản", BUYERS)
    st.title(f"Người mua · {buyer}")
    st.caption("Người mua nhận chứng chỉ qua chuyển nhượng, có thể chuyển tiếp, và retire khi dùng để tuyên bố "
               "điện tái tạo. Retire ghi người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo; không đảo ngược được.")
    addr = S.chain.dep["roles"][buyer]
    mine = holdings(addr)
    got = transfers(addr, outgoing=False)
    mine_r = sorted((e for e in S.ev["Retired"] if e["holder"] == addr), key=lambda e: -e["block"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Đang giữ", mwh(mine["đang giữ (kWh)"].sum() * 1000) if len(mine) else "0")
    c2.metric("Đã nhận", mwh(got["lượng (kWh)"].sum() * 1000) if len(got) else "0")
    c3.metric("Đã retire", mwh(sum(e["wh"] for e in mine_r)))
    sec = section(["Chứng chỉ đang giữ", "Chứng chỉ trên hệ thống", "Lịch sử nhận", "Tuyên bố đã retire"],
                  f"{buyer}-sec")
    if sec == "Chứng chỉ đang giữ":
        i = pick(mine, f"{buyer}-certs")
        if i is not None:
            row = mine.iloc[i]
            transfer_and_retire(buyer, row, [b for b in BUYERS if b != buyer])
            certificate_detail(int(row["tokenId"]))
    elif sec == "Chứng chỉ trên hệ thống":
        st.caption("Mọi chứng chỉ đã phát hành. Cột \"nhà máy còn giữ\" là lượng chưa bán; muốn mua thì liên hệ nhà máy "
                   "(thanh toán ngoài hệ thống), nhà máy chuyển nhượng sang tài khoản của bạn.")
        allc = balances(balances(certificates(), S.PLANT, "nhà máy còn giữ (kWh)"), addr, "bạn đang giữ (kWh)", 7)
        allc = allc.drop(columns=["CP"]) if len(allc) else allc
        only = st.checkbox("Chỉ hiện chứng chỉ nhà máy còn giữ", value=False)
        if only and len(allc):
            allc = allc[allc["nhà máy còn giữ (kWh)"] > 0].reset_index(drop=True)
        i = pick(allc, f"{buyer}-all")
        if i is not None:
            certificate_detail(int(allc.iloc[i]["tokenId"]))
    elif sec == "Lịch sử nhận":
        st.caption("Các lần chứng chỉ được chuyển vào tài khoản này (từ nhà máy hoặc người mua khác).")
        i = pick(got, f"{buyer}-got")
        if i is not None:
            certificate_detail(int(got.iloc[i]["tokenId"]))
    else:
        cmap = cert_of()
        table = pd.DataFrame([{"thời điểm": when(e["block"]),
                               "chứng chỉ": " · ".join(map(str, cmap.get(int(e["tokenId"]), ("?", "")))),
                               "tokenId (hex)": tok(e["tokenId"]), "lượng (kWh)": e["wh"] / 1000,
                               "thụ hưởng": e["beneficiary"], "mục đích": e["purpose"], "kỳ": e["reportingPeriod"]}
                              for e in mine_r])
        i = pick(table, f"{buyer}-stmts")
        if i is not None:
            statement(mine_r[i])
