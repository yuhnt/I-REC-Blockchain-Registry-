"""Trang công khai: tổng quan, tra mọi chứng chỉ, nhật ký công khai, lineage completeness."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from dashboard import state as S
from dashboard.components import certificate_detail
from dashboard.onchain import tx_cell, when
from dashboard.tables import (cert_of, certificates, mwh, pick, production_by_day, rejected, section, show, tok)
from rec.experiments.e3 import lineage
from rec.timeutil import day_date


def render() -> None:
    ev = S.ev
    st.title("Registry chứng chỉ I-REC – điện mặt trời")
    sec = section(["Tổng quan", "Tra chứng chỉ", "Nhật ký công khai", "Lineage completeness"], "pub-sec")
    if sec == "Tổng quan":
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Đã phát hành", mwh(sum(e["wh"] for e in ev["Issued"])))
        c2.metric("Đã retire", mwh(sum(e["wh"] for e in ev["Retired"])))
        c3.metric("Yêu cầu bị từ chối", len(ev["IssueRejected"]))
        c4.metric("Lô bị REVIEW", len(ev["LotReview"]))
        c5.metric("Code Manager", f"{len(ev['Suspended']) + len(ev['Withdrawn'])} thao tác")
        prod = production_by_day(S.CP)
        if len(prod):
            long = prod.melt(id_vars="ngày sản xuất", value_vars=["công tơ O1 (kWh)", "đã phát hành (kWh)"],
                             var_name="loại", value_name="kWh")
            long["MWh"] = long["kWh"] / 1000
            long["loại"] = long["loại"].map({"công tơ O1 (kWh)": "sản lượng công tơ", "đã phát hành (kWh)": "đã phát hành"})
            st.altair_chart(alt.Chart(long).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("ngày sản xuất:O", title="Ngày sản xuất", axis=alt.Axis(labelAngle=-45)),
                xOffset="loại:N", y=alt.Y("MWh:Q", title="MWh"),
                color=alt.Color("loại:N", scale=alt.Scale(range=["#2a78d6", "#eb6834"]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=["ngày sản xuất", "loại", alt.Tooltip("MWh:Q", format=".3f")]), width="stretch")
    elif sec == "Tra chứng chỉ":
        st.caption("Bấm vào một dòng để xem chuỗi truy vết của chứng chỉ.")
        certs = certificates()
        i = pick(certs, "pub-certs")
        if i is not None:
            certificate_detail(int(certs.iloc[i]["tokenId"]))
    elif sec == "Nhật ký công khai":
        st.markdown("**Yêu cầu bị từ chối** (lý do lưu on-chain, I-REC §8.7)")
        show(rejected())
        st.markdown("**Thao tác của Code Manager** (I-REC §11; luôn công khai, kèm lý do)")
        cmap = cert_of()
        cm = [{"thời điểm": when(e["block"]), "thao tác": "tạm khóa" if e["active"] else "mở khóa",
               "chứng chỉ": " · ".join(map(str, cmap.get(int(e["tokenId"]), ("?", "")))),
               "tokenId (hex)": tok(e["tokenId"]), "lượng (kWh)": None, "lý do": e["reason"],
               "giao dịch": tx_cell(e["tx"])} for e in ev["Suspended"]]
        cm += [{"thời điểm": when(e["block"]), "thao tác": "rút",
                "chứng chỉ": " · ".join(map(str, cmap.get(int(e["tokenId"]), ("?", "")))),
                "tokenId (hex)": tok(e["tokenId"]), "lượng (kWh)": e["wh"] / 1000, "lý do": e["reason"],
                "giao dịch": tx_cell(e["tx"])} for e in ev["Withdrawn"]]
        show(pd.DataFrame(cm))
        st.markdown("**Phân xử của Production Auditor**")
        lots = {bytes(x["lotKey"]): x for x in ev["LotEvidenced"]}
        show(pd.DataFrame([{"thời điểm": when(e["block"]),
                            "ngày sản xuất của lô": day_date(int(lots[bytes(e["lotKey"])]["day"])).isoformat(),
                            "kết quả": "duyệt" if e["approved"] else "bác", "auditor": S.name_of(e["auditor"]),
                            "giao dịch": tx_cell(e["tx"])} for e in ev["LotResolved"]]))
    else:
        lin = lineage(S.chain, S.chain.store, S.ev)  # event đã đọc theo khúc
        st.metric("Lineage completeness", f"{lin['complete'].mean():.1%}" if len(lin) else "—",
                  help="% chứng chỉ dựng lại được đủ chuỗi chỉ từ event on-chain và kho file")
        if len(lin):
            lin = lin.rename(columns={"device": "thiết bị", "registered": "đã đăng ký", "lot_evidence": "có bằng chứng",
                                      "files_verified": "file khớp hash", "review_trail": "dấu vết REVIEW",
                                      "supply_consistent": "số dư khớp", "transfers": "số lần chuyển",
                                      "retired_wh": "đã retire (Wh)", "withdrawn_wh": "đã rút (Wh)",
                                      "complete": "đủ chuỗi"})
            lin["ngày sản xuất"] = [day_date(int(d)).isoformat() for d in lin.pop("day")]
            lin["tokenId (hex)"] = [tok(int(x, 16)) for x in lin.pop("token_id")]
            show(lin[["tokenId (hex)", "thiết bị", "ngày sản xuất", "đã đăng ký", "có bằng chứng", "file khớp hash",
                      "dấu vết REVIEW", "số dư khớp", "số lần chuyển", "đã retire (Wh)", "đã rút (Wh)", "đủ chuỗi"]])
