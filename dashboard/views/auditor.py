"""Trang Production Auditor: chứng chỉ chờ duyệt (xem bằng chứng rồi duyệt / bác cả lô), mọi lô, lô đã phân xử."""
from __future__ import annotations

import pandas as pd
import streamlit as st
from web3 import Web3

from dashboard import state as S
from dashboard.components import certificate_detail, evidence_block
from dashboard.onchain import s32, send, tx_cell, when
from dashboard.tables import STATUS, certificates, flags_text, held_info, lot_status, pick, rejected, section, show
from rec.timeutil import day_date


def _held_requests(lots: dict) -> pd.DataFrame:
    """Mỗi yêu cầu từng bị giữ (một dòng), kèm trạng thái hiện tại của lô."""
    info_of = held_info()
    issued_by_req = {s32(e["reqId"]): e for e in S.ev["Issued"]}
    rows, seen = [], set()
    for e in S.ev["IssueHeld"]:
        rid, key = s32(e["reqId"]), bytes(e["lotKey"])
        if rid in seen:  # issuer gửi lại khi lô vẫn REVIEW thì có thêm một IssueHeld trùng
            continue
        seen.add(rid)
        lot = lots[key]
        r = info_of.get(rid) or ({"device": s32(issued_by_req[rid]["deviceId"]), "wh": issued_by_req[rid]["wh"]}
                                 if rid in issued_by_req else {})
        rows.append({"key": key, "yêu cầu": rid, "thiết bị": r.get("device", "—"),
                     "ngày sản xuất": day_date(int(lot["day"])).isoformat(), "lượng xin (kWh)": r.get("wh", 0) / 1000,
                     "cờ lớp B": flags_text(int(lot["flags"])), "O1 của lô (kWh)": lot["o1Wh"] / 1000,
                     "trạng thái lô": STATUS[lot_status(key)], "bị giữ lúc": when(e["block"])})
    return pd.DataFrame(rows)


def render() -> None:
    ev = S.ev
    st.title("Production Auditor")
    st.caption("Lớp B đánh dấu theo lô (cả nhà máy trong một ngày). Mọi chứng chỉ của lô bị giữ cho tới khi auditor "
               "phân xử; quyết định áp dụng cho cả lô. Khóa auditor chỉ đổi trạng thái lô, không mint được.")
    lots = {bytes(e["lotKey"]): e for e in ev["LotEvidenced"]}
    allq = _held_requests(lots)
    queue = allq[allq["trạng thái lô"] == "REVIEW"].reset_index(drop=True) if len(allq) else allq
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chờ duyệt", f"{len(queue)} chứng chỉ")
    c2.metric("Lô chờ phân xử", queue["key"].nunique() if len(queue) else 0)
    c3.metric("Lô đã gửi", len(ev["LotEvidenced"]))
    c4.metric("Yêu cầu bị từ chối", len(ev["IssueRejected"]))
    sec = section(["Chứng chỉ chờ duyệt", "Mọi lô đã gửi", "Yêu cầu bị từ chối", "Đã phân xử",
                   "Chứng chỉ bị tạm khóa"], "audit-sec")
    if sec == "Chứng chỉ chờ duyệt":
        st.caption("Bấm vào một dòng để xem chi tiết và phân xử.")
        i = pick(queue, "audit-queue", hide=("key",))
        if i is not None:
            row = queue.iloc[i]
            key = row["key"]
            st.markdown(f"#### {row['yêu cầu']} · thiết bị {row['thiết bị']} · ngày sản xuất {row['ngày sản xuất']}")
            st.write(f"Chứng chỉ này xin **{row['lượng xin (kWh)']:,.1f} kWh**. Cả lô có "
                     f"{int((queue['key'] == key).sum())} chứng chỉ chờ, tổng "
                     f"{queue.loc[queue['key'] == key, 'lượng xin (kWh)'].sum():,.1f} kWh.")
            evidence_block(key, lots[key])
            with st.form(f"resolve-{key.hex()}"):
                note = st.text_input("Lý do (ghi hash on-chain, nội dung lưu ở hồ sơ auditor)",
                                     "Đã đối chiếu hóa đơn điện lực")
                c1, c2 = st.columns(2)
                approve = c1.form_submit_button("Duyệt cả lô", type="primary")
                reject = c2.form_submit_button("Bác cả lô")
                if approve or reject:
                    send(S.chain.gate.functions.resolveReview(key, bool(approve), Web3.keccak(text=note)), "auditor",
                         ("Đã duyệt" if approve else "Đã bác") + " lô ngày " + str(row["ngày sản xuất"]) +
                         (". Issuer gửi lại yêu cầu để được MINT." if approve else
                          ". Mọi yêu cầu của lô sẽ bị REJECT (LOT_REJECTED)."))
    elif sec == "Mọi lô đã gửi":
        st.caption("Mọi bằng chứng của lô đã gửi lên chain, kể cả lô sạch. Bấm vào một lô để xem 4 báo cáo oracle và "
                   "biểu đồ 15 phút.")
        all_lots = pd.DataFrame([{"key": bytes(e["lotKey"]), "gửi lúc": when(e["block"]), "CP": s32(e["cpId"]),
                                  "ngày sản xuất": day_date(int(e["day"])).isoformat(), "O1 (kWh)": e["o1Wh"] / 1000,
                                  "cờ lớp B": flags_text(int(e["flags"])),
                                  "trạng thái lô": STATUS[lot_status(bytes(e["lotKey"]))],
                                  "giao dịch": tx_cell(e["tx"])}
                                 for e in sorted(ev["LotEvidenced"], key=lambda x: int(x["day"]))])
        status_filter = st.multiselect("Lọc theo trạng thái lô", STATUS[1:], default=STATUS[1:])
        if len(all_lots):
            all_lots = all_lots[all_lots["trạng thái lô"].isin(status_filter)].reset_index(drop=True)
        i = pick(all_lots, "audit-lots", hide=("key",))
        if i is not None:
            evidence_block(all_lots.iloc[i]["key"], lots[all_lots.iloc[i]["key"]])
    elif sec == "Yêu cầu bị từ chối":
        st.caption("Yêu cầu bị lớp A từ chối tự động (không qua auditor), kèm lý do lưu on-chain.")
        show(rejected())
    elif sec == "Đã phân xử":
        done = allq[allq["trạng thái lô"] != "REVIEW"].reset_index(drop=True) if len(allq) else allq
        i = pick(done, "audit-done", hide=("key",))
        if i is not None:
            evidence_block(done.iloc[i]["key"], lots[done.iloc[i]["key"]])
    else:
        certs = certificates()
        locked = certs[certs["trạng thái"] == "tạm khóa"].reset_index(drop=True) if len(certs) else certs
        i = pick(locked, "audit-locked")
        if i is not None:
            certificate_detail(int(locked.iloc[i]["tokenId"]))
