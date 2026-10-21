"""Dashboard (FLOW.md mục 12): đọc event on-chain và kho file theo `data_root`.

Chạy sau khi dựng chain demo:
    python -m rec.experiments.demo
    streamlit run dashboard/app.py
Màn hình hàng đợi REVIEW có nút duyệt / bác, gửi `resolveReview` bằng tài khoản auditor của node Hardhat (chỉ demo).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import altair as alt
import pandas as pd
import streamlit as st
from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rec import config  # noqa: E402
from rec.experiments.e3 import lineage  # noqa: E402
from rec.oracles.store import FileStore  # noqa: E402
from rec.registry.chain_registry import REASONS, _artifact  # noqa: E402
from rec.schema import Flag  # noqa: E402
from rec.timeutil import PLANT_TZ, day_date  # noqa: E402

ZERO = "0x" + "0" * 40
STATUS = ["NONE", "CLEAR", "REVIEW", "APPROVED", "REJECTED"]

st.set_page_config(page_title="Registry I-REC – demo", layout="wide")


def s32(b) -> str:
    return bytes(b).rstrip(b"\0").decode("ascii", "replace")


def flags_text(f: int) -> str:
    names = [n for n, v in (("không nhất quán", Flag.INCONSISTENT), ("thiếu báo cáo", Flag.MISSING_REPORT),
                            ("vượt trần", Flag.OVER_CEILING)) if f & int(v)]
    return ", ".join(names) or "—"


@st.cache_resource
def connect():
    dep_path = config.resolve_path("artifacts") / "demo" / "deployment.json"
    if not dep_path.exists():
        return None
    dep = json.loads(dep_path.read_text(encoding="utf-8"))
    w3 = Web3(Web3.HTTPProvider(dep["url"]))
    c = {name: w3.eth.contract(address=addr, abi=_artifact(name)["abi"]) for name, addr in dep["contracts"].items()}
    return SimpleNamespace(w3=w3, dep=dep, devices=c["DeviceRegistry"], certs=c["CertificateRegistry"],
                           gate=c["DecisionGate"], store=FileStore(Path(dep["store"])))


def logs(chain, contract, event: str) -> list:
    return getattr(contract.events, event)().get_logs(from_block=0)


@st.cache_data(ttl=5, show_spinner=False)
def load_events(block: int) -> dict:
    """Mọi event cần cho dashboard; khóa cache theo số block để tự làm mới khi chain có giao dịch mới."""
    ch = connect()
    out = {}
    for contract, names in ((ch.gate, ["LotEvidenced", "LotReview", "LotResolved", "O1Conflict", "Issued",
                                       "IssueRejected", "IssueHeld"]),
                            (ch.certs, ["TransferSingle", "Retired", "Suspended", "Withdrawn"]),
                            (ch.devices, ["DeviceRegistered", "RegistrationTransferred", "RegistrationClosed"])):
        for n in names:
            out[n] = [dict(lg.args) | {"block": lg.blockNumber, "tx": lg.transactionHash.hex()}
                      for lg in logs(ch, contract, n)]
    return out


chain = connect()
st.title("Registry chứng chỉ I-REC – điện mặt trời")
if chain is None or not chain.w3.is_connected():
    st.error("Chưa có chain demo. Chạy `python -m rec.experiments.demo` trước, rồi tải lại trang.")
    st.stop()
block = chain.w3.eth.block_number
ev = load_events(block)
st.caption(f"Chain {chain.dep['url']} · block {block} · cấu hình lớp B: {chain.dep['profile']} "
           f"({chain.dep['variant']}) · kho file: {chain.dep['store']}")
addr_name = {v: k for k, v in chain.dep["roles"].items()}

tab_over, tab_cert, tab_review, tab_log, tab_lin = st.tabs(
    ["Tổng quan", "Tra chứng chỉ", "Hàng đợi REVIEW", "Nhật ký công khai", "Lineage completeness"])

# ---------------------------------------------------------------- tổng quan
with tab_over:
    issued = pd.DataFrame(ev["Issued"])
    retired = pd.DataFrame(ev["Retired"])
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("MWh đã phát hành", f"{issued['wh'].sum() / 1e6:,.2f}" if len(issued) else "0")
    c2.metric("MWh đã retire", f"{retired['wh'].sum() / 1e6:,.2f}" if len(retired) else "0")
    c3.metric("Yêu cầu bị REJECT", len(ev["IssueRejected"]))
    c4.metric("Lô REVIEW", len(ev["LotReview"]))
    c5.metric("Thao tác của Code Manager", len(ev["Suspended"]) + len(ev["Withdrawn"]))
    if len(issued):
        daily = issued.assign(ngay=[day_date(int(d)) for d in issued["day"]]).groupby("ngay")["wh"].sum() / 1e6
        chart = alt.Chart(daily.reset_index().rename(columns={"wh": "MWh"})).mark_bar(
            color="#2a78d6", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("ngay:T", title="Ngày sản xuất"), y=alt.Y("MWh:Q", title="MWh phát hành"),
            tooltip=[alt.Tooltip("ngay:T", title="Ngày"), alt.Tooltip("MWh:Q", format=".3f")])
        st.altair_chart(chart, use_container_width=True)
    lots = pd.DataFrame(ev["LotEvidenced"])
    if len(lots):
        st.write("**Trạng thái lô**")
        st.dataframe(pd.DataFrame({
            "ngày": [day_date(int(d)) for d in lots["day"]],
            "O1 (kWh)": (lots["o1Wh"] / 1000).round(1), "cờ lớp B": [flags_text(int(f)) for f in lots["flags"]],
            "trạng thái": [STATUS[chain.gate.functions.lotState(bytes(k)).call()[4]] for k in lots["lotKey"]]}),
            hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- tra chứng chỉ
with tab_cert:
    devices = sorted({s32(e["deviceId"]) for e in ev["DeviceRegistered"]})
    issued_days = sorted({int(e["day"]) for e in ev["Issued"]})
    col1, col2 = st.columns(2)
    dev = col1.selectbox("Thiết bị", devices, index=devices.index("B1") if "B1" in devices else 0)
    day = col2.selectbox("Ngày sản xuất", issued_days, format_func=lambda d: f"{day_date(d)} (#{d})") if issued_days \
        else None
    if day is not None:
        dev32 = dev.encode().ljust(32, b"\0")
        tid = chain.certs.functions.tokenIdOf(dev32, day).call()
        st.code(f"tokenId = {hex(tid)}")
        reg = [e for e in ev["DeviceRegistered"] if bytes(e["deviceId"]) == dev32]
        cp32 = bytes(reg[0]["cpId"]) if reg else b""
        key = chain.gate.functions.lotKeyOf(cp32, day).call() if reg else b""
        lot = [e for e in ev["LotEvidenced"] if bytes(e["lotKey"]) == bytes(key)]
        iss = [e for e in ev["Issued"] if int(e["tokenId"]) == tid]
        steps = []
        if reg:
            r = reg[0]
            steps.append(("Đăng ký thiết bị", f"{s32(r['cpId'])}, {r['capacityW'] / 1000:.0f} kW, issuer "
                          f"{addr_name.get(r['issuer'], r['issuer'])}, hiệu lực từ {day_date(int(r['effectiveDay']))}",
                          True))
        if lot:
            lo = lot[0]
            roots = [bytes(x) for x in lo["dataRoots"]]
            ok = [chain.store.verify(x) for x in roots]
            steps.append(("Bằng chứng của lô", f"O1 = {lo['o1Wh'] / 1000:.1f} kWh; cờ: {flags_text(int(lo['flags']))}; "
                          f"file O1–O4 khớp hash: {sum(ok)}/4", all(ok)))
            rv = [e for e in ev["LotReview"] if bytes(e["lotKey"]) == bytes(key)]
            rs = [e for e in ev["LotResolved"] if bytes(e["lotKey"]) == bytes(key)]
            if rv:
                steps.append(("REVIEW → auditor", "duyệt" if rs and rs[0]["approved"] else
                              ("bác" if rs else "đang chờ"), bool(rs)))
        for e in iss:
            steps.append(("Phát hành (Issued)", f"{e['wh'] / 1000:.1f} kWh cho {addr_name.get(e['to'], e['to'])}, "
                          f"yêu cầu {s32(e['reqId'])}", True))
        for e in ev["TransferSingle"]:
            if int(e["id"]) == tid and e["from"] != ZERO and e["to"] != ZERO:
                steps.append(("Chuyển nhượng", f"{addr_name.get(e['from'], e['from'])} → "
                              f"{addr_name.get(e['to'], e['to'])}: {e['value'] / 1000:.1f} kWh", True))
        for e in ev["Suspended"]:
            if int(e["tokenId"]) == tid:
                steps.append(("Code Manager: " + ("tạm khóa" if e["active"] else "mở khóa"), e["reason"], True))
        for e in ev["Withdrawn"]:
            if int(e["tokenId"]) == tid:
                steps.append(("Code Manager: rút", f"{e['wh'] / 1000:.1f} kWh – {e['reason']}", True))
        for e in ev["Retired"]:
            if int(e["tokenId"]) == tid:
                steps.append(("Retire (redemption)", f"{e['wh'] / 1000:.1f} kWh bởi {addr_name.get(e['holder'])}; "
                              f"thụ hưởng: {e['beneficiary']}; mục đích: {e['purpose']}; nơi tiêu thụ: "
                              f"{e['consumptionLocation']}; kỳ: {e['reportingPeriod']}", True))
        if not iss:
            st.warning("Chưa có chứng chỉ cho (thiết bị, ngày) này.")
        st.dataframe(pd.DataFrame(steps, columns=["bước", "chi tiết", "kiểm được"]), hide_index=True,
                     use_container_width=True)
        if lot:
            with st.expander("Mở file gốc của 4 oracle (theo data_root)"):
                for x in roots:
                    st.write(f"`{x.hex()}`", "✔ khớp hash" if chain.store.verify(x) else "✘ thiếu file hoặc bị sửa")

# ---------------------------------------------------------------- hàng đợi REVIEW
with tab_review:
    resolved = {bytes(e["lotKey"]) for e in ev["LotResolved"]}
    queue = [e for e in ev["LotReview"] if bytes(e["lotKey"]) not in resolved]
    st.write(f"**{len(queue)} lô đang chờ Production Auditor** (đã phân xử: {len(resolved)})")
    for e in queue:
        key = bytes(e["lotKey"])
        lo = next(x for x in ev["LotEvidenced"] if bytes(x["lotKey"]) == key)
        d = int(lo["day"])
        st.subheader(f"Lô {s32(lo['cpId'])} · {day_date(d)}")
        st.write(f"Cờ: **{flags_text(int(e['flags']))}** · O1 = {lo['o1Wh'] / 1000:.1f} kWh")
        reason_file = chain.store.root / f"{bytes(e['reasonsHash']).hex()}.json"
        if reason_file.exists():
            st.json(json.loads(reason_file.read_text(encoding="utf-8")), expanded=False)
        series = {}
        for name, x in zip(("O1 công tơ", "O2 tổng inverter"), lo["dataRoots"][:2]):
            try:
                doc = chain.store.get(bytes(x))
                series[name] = pd.Series(doc["values"], index=pd.to_datetime(doc["slot_ends"]) if doc["slot_ends"]
                                         else None) / 1000 * 4
            except Exception:  # noqa: BLE001 – file thiếu hoặc bị sửa
                st.error(f"File {name} thiếu hoặc không khớp hash")
        if series:
            df = pd.DataFrame(series)
            # Giờ đồng hồ của nhà máy, ghi như UTC để biểu đồ không đổi theo múi giờ của trình duyệt.
            df.index = df.index.tz_convert(PLANT_TZ).tz_localize(None).tz_localize("UTC")
            long = df.reset_index(names="t").melt("t", var_name="nguồn", value_name="kW").dropna()
            chart = alt.Chart(long).mark_line(strokeWidth=2).encode(
                x=alt.X("utchoursminutes(t):T", title="Giờ địa phương của nhà máy"), y=alt.Y("kW:Q", title="kW"),
                color=alt.Color("nguồn:N", scale=alt.Scale(range=["#2a78d6", "#eb6834"])),
                tooltip=["nguồn", alt.Tooltip("utchoursminutes(t):T", title="giờ"),
                         alt.Tooltip("kW:Q", format=".1f")])
            st.altair_chart(chart, use_container_width=True)
        b1, b2, _ = st.columns([1, 1, 6])
        for btn, approve in ((b1, True), (b2, False)):
            if btn.button("Duyệt" if approve else "Bác", key=f"{key.hex()}-{approve}"):
                tx = chain.gate.functions.resolveReview(key, approve, Web3.keccak(text="dashboard")).transact(
                    {"from": chain.dep["roles"]["auditor"], "gas": 300_000, "gasPrice": 0})
                chain.w3.eth.wait_for_transaction_receipt(tx)
                st.success("Đã ghi LotResolved on-chain. Issuer gửi lại yêu cầu của lô để được MINT (nếu duyệt).")
                st.cache_data.clear()
                st.rerun()

# ---------------------------------------------------------------- nhật ký công khai
with tab_log:
    st.write("**Yêu cầu bị REJECT** (lý do lưu on-chain, I-REC §8.7)")
    rej = pd.DataFrame([{"yêu cầu": s32(e["reqId"]), "thiết bị": s32(e["deviceId"]), "ngày": day_date(int(e["day"])),
                         "lý do": REASONS[int(e["reason"])].value, "block": e["block"]} for e in ev["IssueRejected"]])
    st.dataframe(rej, hide_index=True, use_container_width=True)
    st.write("**Thao tác của Code Manager** (I-REC §11; luôn công khai, kèm lý do)")
    cm = [{"thao tác": "tạm khóa" if e["active"] else "mở khóa", "tokenId": hex(int(e["tokenId"]))[:18] + "…",
           "lượng (kWh)": "", "lý do": e["reason"], "block": e["block"]} for e in ev["Suspended"]]
    cm += [{"thao tác": "rút", "tokenId": hex(int(e["tokenId"]))[:18] + "…", "lượng (kWh)": e["wh"] / 1000,
            "lý do": e["reason"], "block": e["block"]} for e in ev["Withdrawn"]]
    st.dataframe(pd.DataFrame(cm), hide_index=True, use_container_width=True)
    if ev["O1Conflict"]:
        st.write("**O1 xung đột với O1 đã lưu**")
        st.dataframe(pd.DataFrame(ev["O1Conflict"]), hide_index=True, use_container_width=True)
    st.write("**Phân xử của auditor**")
    st.dataframe(pd.DataFrame([{"lô": bytes(e["lotKey"]).hex()[:16] + "…", "kết quả": "duyệt" if e["approved"] else "bác",
                                "auditor": addr_name.get(e["auditor"], e["auditor"]), "block": e["block"]}
                               for e in ev["LotResolved"]]), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- lineage
with tab_lin:
    lin = lineage(chain, chain.store)
    st.metric("Lineage completeness", f"{lin['complete'].mean():.1%}" if len(lin) else "—",
              help="% chứng chỉ dựng lại được đủ chuỗi chỉ từ event on-chain và kho file")
    st.dataframe(lin, hide_index=True, use_container_width=True)
