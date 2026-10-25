"""Khối hiển thị dùng ở nhiều trang: bằng chứng của lô, chuỗi truy vết chứng chỉ, tuyên bố retire, form thao tác."""
from __future__ import annotations

import json

import altair as alt
import pandas as pd
import streamlit as st

from dashboard import state as S
from dashboard.onchain import s32, send, tx_cell, when
from dashboard.tables import STATUS, ZERO, flags_text, lot_of, lot_status, show, tok
from rec.timeutil import PLANT_TZ, day_date

ORACLE_NAMES = ("O1 công tơ", "O2 tổng 24 inverter", "O3 bức xạ tại chỗ", "O4 bức xạ vệ tinh NSRDB")


def series_chart(roots: list[bytes], names: tuple, scale: float, unit: str, colors: list[str]) -> None:
    series = {}
    for name, x in zip(names, roots):
        try:
            doc = S.chain.store.get(x)
            series[name] = pd.Series([None if v is None else v * scale for v in doc["values"]],
                                     index=pd.to_datetime(doc["slot_ends"]), dtype=float)
        except Exception:  # noqa: BLE001 – thiếu file hoặc file bị sửa
            pass
    if not series:
        return
    df = pd.DataFrame(series)
    df.index = df.index.tz_convert(PLANT_TZ).tz_localize(None).tz_localize("UTC")  # giờ đồng hồ của nhà máy
    long = df.reset_index(names="t").melt("t", var_name="nguồn", value_name="v").dropna()
    st.altair_chart(alt.Chart(long).mark_line(strokeWidth=2).encode(
        x=alt.X("utchoursminutes(t):T", title="Giờ địa phương của nhà máy"), y=alt.Y("v:Q", title=unit),
        color=alt.Color("nguồn:N", scale=alt.Scale(range=colors), legend=alt.Legend(orient="top", title=None)),
        tooltip=["nguồn", alt.Tooltip("utchoursminutes(t):T", title="giờ"), alt.Tooltip("v:Q", title=unit, format=".1f")]),
        width="stretch")


def evidence_block(key: bytes, lot: dict) -> None:
    """Bằng chứng của lô: 4 báo cáo theo data_root (kiểm hash), cờ, reason code, biểu đồ 15 phút."""
    roots = [bytes(x) for x in lot["dataRoots"]]
    files = []
    for name, unit, x in zip(ORACLE_NAMES, ("kWh", "kWh", "kWh/m²", "kWh/m²"), roots):
        try:
            doc = S.chain.store.get(x)
            vals = [v for v in doc["values"] if v is not None]
            files.append({"oracle": name, "đơn vị": unit, "tổng ngày": round(sum(vals) / 1000, 2),
                          "slot lớn nhất": round(max(vals, default=0) / 1000, 3),
                          "slot có số liệu": f"{len(vals)}/{len(doc['values'])}",
                          "data_root": x.hex()[:16] + "…", "file gốc": "✔ khớp hash"})
        except Exception:  # noqa: BLE001
            files.append({"oracle": name, "đơn vị": unit, "tổng ngày": None, "slot lớn nhất": None,
                          "slot có số liệu": "", "data_root": x.hex()[:16] + "…", "file gốc": "✘ thiếu hoặc bị sửa"})
    c1, c2, c3 = st.columns(3)
    c1.metric("O1 công tơ", f"{lot['o1Wh'] / 1000:,.1f} kWh")
    c2.metric("Cờ lớp B", flags_text(int(lot["flags"])))
    c3.metric("Trạng thái lô", STATUS[lot_status(key)])
    st.caption(f"Bằng chứng gửi lúc {when(lot['block'])} (giờ nhà máy). Số liệu từng inverter không đưa lên chain; "
               "O2 là tổng 24 inverter của 6 thiết bị.")
    st.dataframe(pd.DataFrame(files), hide_index=True, width="stretch")
    rv = next((e for e in S.ev["LotReview"] if bytes(e["lotKey"]) == key), None)
    if rv is not None:
        f = S.chain.store.root / f"{bytes(rv['reasonsHash']).hex()}.json"
        if f.exists():
            r = json.loads(f.read_text(encoding="utf-8"))
            parts = []
            if "consistency" in r:
                parts.append("nhất quán: " + ", ".join(f"{k} = {v:+.1%}" for k, v in r["consistency"].items()
                                                      if v is not None))
            if "ceiling" in r:
                c = r["ceiling"]
                parts.append(f"trần: O1 = {c['o1_wh'] / 1000:,.0f} kWh so với {c['base_wh'] * (1 + c['tau']) / 1000:,.0f}"
                             f" kWh (nền {c['base_wh'] / 1000:,.0f} × (1 + {c['tau']:.1%}))")
            if "coverage" in r:
                parts.append("độ phủ: " + ", ".join(f"{k} {v:.0%}" for k, v in r["coverage"].items()))
            st.write("**Reason code của verifier:** " + " · ".join(parts))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Công suất: công tơ so với tổng inverter**")
        series_chart(roots[:2], ("O1 công tơ", "O2 tổng inverter"), 4 / 1000, "kW", ["#2a78d6", "#eb6834"])
    with c2:
        st.markdown("**Bức xạ: cảm biến tại chỗ so với vệ tinh**")
        series_chart(roots[2:], ("O3 tại chỗ", "O4 NSRDB"), 4, "W/m²", ["#1baf7a", "#6250d6"])


def certificate_detail(tid: int) -> None:
    """Chuỗi truy vết của một chứng chỉ: đăng ký → bằng chứng của lô → phân xử → phát hành → chuyển → retire."""
    ev, chain, name_of = S.ev, S.chain, S.name_of
    iss = next((e for e in ev["Issued"] if int(e["tokenId"]) == tid), None)
    if iss is None:
        st.warning("Chưa có chứng chỉ này.")
        return
    dev, day = s32(iss["deviceId"]), int(iss["day"])
    reg = next((e for e in ev["DeviceRegistered"] if s32(e["deviceId"]) == dev), None)
    cp = s32(reg["cpId"]) if reg else ""
    st.markdown(f"#### Chứng chỉ {dev} · ngày sản xuất {day_date(day)}")
    st.code(f"tokenId = {tok(tid)}")
    if chain.explorer:
        st.markdown(f"[Xem token này trên Sepolia Etherscan]({chain.explorer}/token/{chain.certs.address}?a={tid})")
    steps = []
    if reg:
        steps.append((reg["block"], "Đăng ký thiết bị", f"{cp}, {reg['capacityW'] / 1000:.0f} kW, issuer "
                      f"{name_of(reg['issuer'])}, hiệu lực từ {day_date(int(reg['effectiveDay']))}", reg["tx"]))
    key, lot = lot_of(cp, day)
    if lot:
        steps.append((lot["block"], "Bằng chứng của lô", f"O1 = {lot['o1Wh'] / 1000:,.1f} kWh; cờ lớp B: "
                      f"{flags_text(int(lot['flags']))}", lot["tx"]))
    for e in ev["LotResolved"]:
        if bytes(e["lotKey"]) == key:
            steps.append((e["block"], "Production Auditor", "duyệt" if e["approved"] else "bác", e["tx"]))
    steps.append((iss["block"], "Phát hành (Issued)", f"{iss['wh'] / 1000:,.1f} kWh cho {name_of(iss['to'])}, yêu cầu "
                  f"{s32(iss['reqId'])}", iss["tx"]))
    for e in ev["TransferSingle"]:
        if int(e["id"]) == tid and e["from"] != ZERO and e["to"] != ZERO:
            steps.append((e["block"], "Chuyển nhượng", f"{name_of(e['from'])} → {name_of(e['to'])}: "
                          f"{e['value'] / 1000:,.1f} kWh", e["tx"]))
    for e in ev["Suspended"]:
        if int(e["tokenId"]) == tid:
            steps.append((e["block"], "Code Manager: " + ("tạm khóa" if e["active"] else "mở khóa"), e["reason"], e["tx"]))
    for e in ev["Withdrawn"]:
        if int(e["tokenId"]) == tid:
            steps.append((e["block"], "Code Manager: rút", f"{e['wh'] / 1000:,.1f} kWh – {e['reason']}", e["tx"]))
    for e in ev["Retired"]:
        if int(e["tokenId"]) == tid:
            steps.append((e["block"], "Retire", f"{e['wh'] / 1000:,.1f} kWh bởi {name_of(e['holder'])}; thụ hưởng: "
                          f"{e['beneficiary']}", e["tx"]))
    show(pd.DataFrame([{"thời điểm": when(b), "bước": s, "chi tiết": d, "giao dịch": tx_cell(h)}
                       for b, s, d, h in sorted(steps, key=lambda x: x[0])]))
    if lot:
        with st.expander("Bằng chứng của lô (4 báo cáo oracle, file gốc, biểu đồ)"):
            evidence_block(key, lot)


def statement(e: dict) -> None:
    """Tuyên bố retire (redemption statement) dựng lại từ event `Retired`."""
    tid = int(e["tokenId"])
    iss = next((x for x in S.ev["Issued"] if int(x["tokenId"]) == tid), None)
    st.markdown("#### Tuyên bố sử dụng chứng chỉ (redemption statement)")
    st.table(pd.DataFrame({"": [
        S.name_of(e["holder"]), e["beneficiary"], e["purpose"], e["consumptionLocation"], e["reportingPeriod"],
        f"{e['wh'] / 1000:,.3f} kWh",
        f"{s32(iss['deviceId'])}, ngày {day_date(int(iss['day']))}" if iss else "—",
        tok(tid), when(e["block"]), e["tx"]]},
        index=["Người retire", "Người thụ hưởng", "Mục đích", "Nơi tiêu thụ", "Kỳ báo cáo", "Lượng",
               "Nguồn (thiết bị, ngày sản xuất)", "tokenId", "Thời điểm retire", "Giao dịch"]))
    if S.chain.explorer:
        st.markdown(f"[Xem giao dịch retire trên Etherscan]({tx_cell(e['tx'])})")
    st.caption("Tuyên bố không sửa được và không đảo ngược được (I-REC §10); phần chứng chỉ được retire đã bị đốt.")


def transfer_and_retire(holder_role: str, row: pd.Series, others: list[str]) -> None:
    """Hai form thao tác trên một chứng chỉ đang giữ: chuyển nhượng và retire."""
    chain = S.chain
    tid, have = int(row["tokenId"]), float(row["đang giữ (kWh)"])
    locked = row["trạng thái"] == "tạm khóa"
    st.markdown(f"#### Thao tác với chứng chỉ {row['thiết bị']} · {row['ngày sản xuất']} (đang giữ {have:,.1f} kWh)")
    if locked:
        st.warning("Chứng chỉ đang bị Code Manager tạm khóa: không chuyển nhượng, không retire được (I-REC §11).")
    c1, c2 = st.columns(2)
    with c1.form(f"tr-{holder_role}-{tid}"):
        st.markdown("**Chuyển nhượng** (`safeTransferFrom` của ERC-1155; thanh toán nằm ngoài hệ thống)")
        to = st.selectbox("Người nhận", others)
        kwh = st.number_input("Lượng (kWh)", min_value=0.001, max_value=have, value=have, step=1.0, format="%.3f")
        if st.form_submit_button("Chuyển", disabled=locked):
            send(chain.certs.functions.safeTransferFrom(chain.dep["roles"][holder_role], chain.dep["roles"][to], tid,
                                                        int(round(kwh * 1000)), b""),
                 holder_role, f"Đã chuyển {kwh:,.3f} kWh cho {to}")
    with c2.form(f"rt-{holder_role}-{tid}"):
        st.markdown("**Retire** (sử dụng chứng chỉ để tuyên bố điện tái tạo; không đảo ngược)")
        ben = st.text_input("Người thụ hưởng", f"{holder_role} (ESG)")
        purpose = st.text_input("Mục đích", "Scope 2")
        loc = st.text_input("Nơi tiêu thụ", "California, US")
        period = st.text_input("Kỳ báo cáo", str(row["ngày sản xuất"])[:4])
        kwh_r = st.number_input("Lượng (kWh)", min_value=0.001, max_value=have, value=have, step=1.0, format="%.3f",
                                key=f"rtk-{tid}")
        if st.form_submit_button("Retire", disabled=locked):
            send(chain.certs.functions.retire(tid, int(round(kwh_r * 1000)), ben, purpose, loc, period),
                 holder_role, f"Đã retire {kwh_r:,.3f} kWh")
