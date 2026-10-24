"""Dashboard (FLOW.md mục 12): mỗi vai một trang, đọc event on-chain và kho file theo `data_root`.

- Công khai: tổng quan, tra mọi chứng chỉ, nhật ký công khai, lineage completeness;
- Nhà máy: sản xuất theo ngày (công tơ, inverter, bức xạ, kết cục từng thiết bị), chứng chỉ đang giữ (được MINT thẳng
  vào địa chỉ nhà máy), yêu cầu bị từ chối / bị giữ, chuyển nhượng cho người mua và lịch sử đã chuyển, retire;
- Người mua: chứng chỉ đang giữ, chứng chỉ trên hệ thống (nhà máy còn giữ bao nhiêu), lịch sử nhận, chuyển tiếp,
  retire kèm tuyên bố (I-REC §10), xem lại các tuyên bố đã ghi;
- Issuer: yêu cầu phát hành bị giữ vì lô REVIEW, gửi lại sau khi auditor duyệt;
- Production Auditor: chứng chỉ chờ phát hành đang bị giữ (bấm vào để xem bằng chứng rồi duyệt / bác cả lô), mọi lô
  đã gửi, yêu cầu bị từ chối, lô đã phân xử, chứng chỉ đang bị Code Manager tạm khóa.
Mọi bảng có cột thời điểm theo giờ nhà máy (Hardhat cục bộ: đồng hồ mô phỏng; Sepolia: giờ thật).

Chạy sau khi dựng chain demo:
    python -m rec.experiments.demo                  (Hardhat cục bộ)
    python -m rec.experiments.testnet deploy, demo  (Sepolia; xem rec/experiments/testnet.py)
    streamlit run dashboard/app.py
Thanh bên chọn chain. Hardhat cục bộ: giao dịch ký bằng tài khoản đã mở khóa của node. Sepolia: ký tại máy bằng khóa
suy ra từ TESTNET_MNEMONIC trong contracts/.env; URL RPC (chứa API key) không bao giờ hiện trên trang.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import altair as alt
import pandas as pd
import streamlit as st
from eth_utils import keccak
from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rec import config  # noqa: E402
from rec.experiments.e3 import lineage  # noqa: E402
from rec.experiments.testnet import load_env  # noqa: E402
from rec.oracles.signer import hardhat_account  # noqa: E402
from rec.oracles.store import FileStore  # noqa: E402
from rec.registry.chain_registry import REASONS, ROLES, _artifact  # noqa: E402
from rec.schema import Flag  # noqa: E402
from rec.timeutil import PLANT_TZ, day_date  # noqa: E402

ZERO = "0x" + "0" * 40
STATUS = ["chưa có bằng chứng", "sạch", "REVIEW", "đã duyệt", "bị bác"]
ROLES = ["Công khai", "Nhà máy", "Người mua", "Issuer", "Production Auditor"]

st.set_page_config(page_title="Registry I-REC – demo", layout="wide")


# ====================================================================== kết nối và dữ liệu

def s32(b) -> str:
    return bytes(b).rstrip(b"\0").decode("ascii", "replace")


def b32(s: str) -> bytes:
    return s.encode("ascii").ljust(32, b"\0")


def flags_text(f: int) -> str:
    names = [n for n, v in (("không nhất quán", Flag.INCONSISTENT), ("thiếu báo cáo", Flag.MISSING_REPORT),
                            ("vượt trần", Flag.OVER_CEILING)) if f & int(v)]
    return ", ".join(names) or "—"


SOURCES = {"Hardhat cục bộ": ("demo", "deployment.json"), "Sepolia (testnet)": ("testnet", "deployment.json")}
LOG_CHUNK = 2_000  # số block mỗi lần eth_getLogs; tự hạ xuống LOG_CHUNK_MIN nếu nhà cung cấp RPC từ chối
LOG_CHUNK_MIN = 10  # Alchemy gói miễn phí chỉ cho khoảng 10 block mỗi lần


@st.cache_resource
def connect(source: str):
    dep_path = config.resolve_path("artifacts").joinpath(*SOURCES[source])
    if not dep_path.exists():
        return None
    dep = json.loads(dep_path.read_text(encoding="utf-8"))
    env = load_env() if dep.get("network") == "sepolia" else {}
    url = env.get("SEPOLIA_RPC_URL") if env else dep["url"]
    if not url:
        return None
    w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 60}))
    c = {name: w3.eth.contract(address=addr, abi=_artifact(name)["abi"]) for name, addr in dep["contracts"].items()}
    errors = {}
    for name in c:
        for item in _artifact(name)["abi"]:
            if item["type"] == "error":
                sig = f"{item['name']}(" + ",".join(i["type"] for i in item["inputs"]) + ")"
                errors["0x" + keccak(text=sig)[:4].hex()] = item["name"]
    mnemonic = env.get("TESTNET_MNEMONIC", "")
    return SimpleNamespace(w3=w3, dep=dep, devices=c["DeviceRegistry"], certs=c["CertificateRegistry"],
                           gate=c["DecisionGate"], store=FileStore(Path(dep["store"])), errors=errors,
                           public=dep.get("network") == "sepolia", explorer=dep.get("explorer"),
                           key_of=lambda role: hardhat_account(ROLES.index(role), mnemonic))


def redact(text: str) -> str:
    """Bỏ URL khỏi thông báo lỗi (URL của Alchemy chứa API key)."""
    return re.sub(r"https?://\S+", "<RPC>", str(text))


@st.cache_resource
def log_store(source: str) -> dict:
    """Log thô đã đọc của mỗi chain, cộng dồn qua các lần tải trang: chỉ đọc thêm block mới."""
    return {"next": None, "chunk": LOG_CHUNK, "logs": []}


def fetch_logs(source: str, latest: int) -> list:
    """eth_getLogs cho cả 3 contract trong một lệnh mỗi khúc block; tự thu nhỏ khúc nếu RPC từ chối."""
    store = log_store(source)
    if store["next"] is None:
        store["next"] = int(chain.dep.get("from_block", 0))
    addrs = [chain.devices.address, chain.certs.address, chain.gate.address]
    while store["next"] <= latest:
        end = min(store["next"] + store["chunk"] - 1, latest)
        try:
            store["logs"] += chain.w3.eth.get_logs({"fromBlock": store["next"], "toBlock": end, "address": addrs})
        except Exception:  # noqa: BLE001 – vượt giới hạn khoảng block của nhà cung cấp
            if store["chunk"] > LOG_CHUNK_MIN:
                store["chunk"] = LOG_CHUNK_MIN
                continue
            raise
        store["next"] = end + 1
    return store["logs"]


EVENT_NAMES = {"gate": ["LotEvidenced", "LotReview", "LotResolved", "O1Conflict", "Issued", "IssueRejected",
                         "IssueHeld"],
               "certs": ["TransferSingle", "Retired", "Suspended", "Withdrawn"],
               "devices": ["DeviceRegistered", "RegistrationTransferred", "RegistrationClosed"]}


def load_events(source: str, block: int) -> dict:
    """Giải mã log thô thành event theo tên; mỗi event thêm block và tx."""
    by_addr = {}
    for attr, names in EVENT_NAMES.items():
        contract = getattr(chain, attr)
        by_addr[contract.address.lower()] = [(n, getattr(contract.events, n)()) for n in names]
    out = {n: [] for names in EVENT_NAMES.values() for n in names}
    for lg in fetch_logs(source, block):
        for n, ev_ in by_addr.get(lg["address"].lower(), []):
            try:
                d = ev_.process_log(lg)
            except Exception:  # noqa: BLE001 – log của event khác cùng contract
                continue
            out[n].append(dict(d.args) | {"block": d.blockNumber,
                                          "tx": "0x" + bytes(d.transactionHash).hex()})
            break
    return out


def transact(fn, role: str):
    """Gửi giao dịch bằng vai `role`: node Hardhat ký hộ (tài khoản mở khóa); Sepolia ký tại máy bằng khóa từ mnemonic."""
    if not chain.public:
        tx = fn.transact({"from": chain.dep["roles"][role], "gas": 1_000_000, "gasPrice": 0})
        return chain.w3.eth.wait_for_transaction_receipt(tx)
    acct = chain.key_of(role)
    tx = fn.build_transaction({"from": acct.address, "nonce": chain.w3.eth.get_transaction_count(acct.address, "pending")})
    tx["gas"] = int(tx["gas"] * 1.2)
    h = chain.w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
    return chain.w3.eth.wait_for_transaction_receipt(h, timeout=600, poll_latency=2)


def tx_link(h: str) -> str:
    return f"[{h[:12]}…]({chain.explorer}/tx/{h})" if chain.explorer else f"{h[:18]}…"


def send(fn, role: str, done: str) -> None:
    """Gửi giao dịch bằng tài khoản của vai `role`; báo kết quả sau khi trang tải lại."""
    try:
        with st.spinner("Đang gửi giao dịch" + (" lên Sepolia (khoảng 12–30 giây)…" if chain.public else "…")):
            rcpt = transact(fn, role)
        h = "0x" + bytes(rcpt.transactionHash).hex()
        st.session_state["flash"] = ("success", f"{done} · block {rcpt.blockNumber}, gas {rcpt.gasUsed:,} · tx {tx_link(h)}")
    except Exception as e:  # noqa: BLE001 – contract revert
        text = str(getattr(e, "data", "")) + " " + str(e)
        name = next((chain.errors[s.lower()] for s in re.findall(r"0x[0-9a-fA-F]{8}", text)
                     if s.lower() in chain.errors), None)
        st.session_state["flash"] = ("error", f"Giao dịch bị từ chối: {name or redact(text)[:200]}")
    clear_selection()
    st.cache_data.clear()
    st.rerun()


def clear_selection() -> None:
    """Bỏ chọn mọi bảng sau một giao dịch, để dòng đang chọn không nhảy sang chứng chỉ hoặc lô khác."""
    for k in [k for k in st.session_state if k.endswith(("-certs", "-queue", "-done", "-locked", "-stmts", "-days",
                                                             "-sent", "-all", "-got", "-lots"))]:
        del st.session_state[k]


available = [k for k, v in SOURCES.items() if config.resolve_path("artifacts").joinpath(*v).exists()]
source = st.sidebar.selectbox("Chain", available or list(SOURCES))
try:
    chain = connect(source) if available else None
    connected = chain is not None and chain.w3.is_connected()
except Exception:  # noqa: BLE001
    chain, connected = None, False
if not connected:
    st.title("Registry chứng chỉ I-REC – điện mặt trời")
    st.error("Chưa kết nối được chain. Hardhat cục bộ: chạy `python -m rec.experiments.demo`. Sepolia: chạy "
             "`python -m rec.experiments.testnet deploy` rồi `demo`, và kiểm tra `contracts/.env`.")
    st.stop()
try:
    block = chain.w3.eth.block_number
    ev = load_events(source, block)
except Exception as e:  # noqa: BLE001 – lỗi RPC: hiện thông báo đã bỏ URL, không hiện traceback
    st.error(f"Lỗi khi đọc chain: {type(e).__name__}: {redact(e)[:300]}")
    st.stop()
addr_name = {v: k for k, v in chain.dep["roles"].items()}
name_of = lambda a: addr_name.get(a, a[:10] + "…")  # noqa: E731
PLANT = chain.dep["roles"]["plant"]
CP = next(iter(s32(e["cpId"]) for e in ev["DeviceRegistered"]), "CP-1")
REASON_TEXT = {"key": "trùng (thiết bị, ngày) đã phát hành", "budget": "vượt sản lượng công tơ của CP",
               "capacity": "vượt công suất thiết bị hoặc CP", "period": "kỳ phát hành sai quy định (§8.2)",
               "oracle": "lô chưa có bằng chứng oracle", "lot_rejected": "auditor đã bác lô",
               "not_issuer": "người gửi không phải issuer của thiết bị", "not_registered": "thiết bị chưa đăng ký"}


@st.cache_resource
def block_times(source: str) -> dict:
    return {}


def when(n: int) -> str:
    """Thời điểm của block theo giờ nhà máy (Hardhat cục bộ: đồng hồ mô phỏng; Sepolia: giờ thật)."""
    cache = block_times(source)
    if n not in cache:
        ts = chain.w3.eth.get_block(n)["timestamp"]
        cache[n] = pd.Timestamp(ts, unit="s", tz="UTC").tz_convert(PLANT_TZ).strftime("%Y-%m-%d %H:%M")
    return cache[n]


def reason_of(e: dict) -> str:
    code = REASONS[int(e["reason"])].value
    return f"{code}: {REASON_TEXT.get(code, '')}"


def tx_url(h: str) -> str | None:
    return f"{chain.explorer}/tx/{h}" if chain.explorer else None


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
            cfg[c] = st.column_config.LinkColumn(c, display_text="Etherscan") if chain.explorer else \
                st.column_config.TextColumn(c)
    return cfg


def show(df: pd.DataFrame, hide: tuple = ()) -> None:
    if df.empty:
        st.info("Không có dòng nào.")
        return
    view = df.drop(columns=[c for c in hide if c in df])
    st.dataframe(view, hide_index=True, use_container_width=True, column_config=column_config(view))


def pick(df: pd.DataFrame, key: str, hide: tuple = ("tokenId",)) -> int | None:
    """Bảng bấm chọn một dòng; trả chỉ số dòng được chọn."""
    if df.empty:
        st.info("Không có dòng nào.")
        return None
    view = df.drop(columns=[c for c in hide if c in df])
    sel = st.dataframe(view, hide_index=True, use_container_width=True, on_select="rerun",
                       selection_mode="single-row", key=key, column_config=column_config(view))
    rows = sel.selection.rows
    return rows[0] if rows else None


def section(options: list[str], key: str) -> str:
    """Thanh chọn mục giữ nguyên khi trang tải lại (st.tabs quay về tab đầu sau mỗi lần chọn dòng)."""
    return st.radio("Mục", options, horizontal=True, key=key, label_visibility="collapsed")


def tok(tid: int) -> str:
    """tokenId đầy đủ: 0x + 64 chữ số hex (giữ số 0 ở đầu), đúng như trên Etherscan."""
    return f"0x{int(tid):064x}"


def mwh(wh: float) -> str:
    return f"{wh / 1e6:,.2f} MWh"


# ====================================================================== bảng dữ liệu

def cert_of() -> dict[int, tuple[str, int]]:
    return {int(e["tokenId"]): (s32(e["deviceId"]), int(e["day"])) for e in ev["Issued"]}


def certificates() -> pd.DataFrame:
    """Một dòng mỗi chứng chỉ (thiết bị-ngày) đã phát hành, kèm lượng đã retire / đã rút và trạng thái khóa."""
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
    bal = chain.certs.functions.balanceOfBatch([addr] * len(df), [int(t) for t in df["tokenId"]]).call()
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
    for e in sorted(ev["TransferSingle"], key=lambda x: -x["block"]):
        if e["from"] == ZERO or e["to"] == ZERO or (e["from"] if outgoing else e["to"]) != addr:
            continue
        dev, day = cmap.get(int(e["id"]), ("?", 0))
        rows.append({"tokenId": int(e["id"]), "tokenId (hex)": tok(int(e["id"])), "thời điểm": when(e["block"]),
                     ("người nhận" if outgoing else "người chuyển"): name_of(e["to"] if outgoing else e["from"]),
                     "thiết bị": dev, "ngày sản xuất": day_date(day).isoformat() if day else "",
                     "lượng (kWh)": e["value"] / 1000, "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"})
    return pd.DataFrame(rows)


def requests_of_cp(cp: str) -> pd.DataFrame:
    """Mọi yêu cầu phát hành bị từ chối hoặc đang bị giữ tại CP, kèm thời điểm và lý do."""
    devs = {s32(e["deviceId"]): name_of(e["issuer"]) for e in ev["DeviceRegistered"] if s32(e["cpId"]) == cp}
    held_info = {r["req_id"]: r for r in chain.dep.get("held_requests", [])}
    lots = {bytes(e["lotKey"]): e for e in ev["LotEvidenced"]}
    rows = []
    for e in ev["IssueRejected"]:
        dev = s32(e["deviceId"])
        if dev in devs:
            rows.append({"thời điểm": when(e["block"]), "kết cục": "bị từ chối", "thiết bị": dev, "issuer": devs[dev],
                         "ngày sản xuất": day_date(int(e["day"])).isoformat(), "lý do": reason_of(e),
                         "yêu cầu": s32(e["reqId"]), "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"})
    seen = set()
    for e in ev["IssueHeld"]:
        rid, key = s32(e["reqId"]), bytes(e["lotKey"])
        status = chain.gate.functions.lotState(key).call()[4] if key in lots else 0
        if rid in seen or status != 2:  # chỉ yêu cầu của lô còn REVIEW
            continue
        seen.add(rid)
        info = held_info.get(rid, {})
        rows.append({"thời điểm": when(e["block"]), "kết cục": "bị giữ (chờ auditor)",
                     "thiết bị": info.get("device", "—"), "issuer": info.get("issuer", "—"),
                     "ngày sản xuất": day_date(int(lots[key]["day"])).isoformat(),
                     "lý do": "lô bị lớp B đánh dấu: " + flags_text(int(lots[key]["flags"])),
                     "yêu cầu": rid, "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"})
    return pd.DataFrame(rows).sort_values("thời điểm", ascending=False).reset_index(drop=True) if rows else \
        pd.DataFrame()


def production_by_day(cp: str) -> pd.DataFrame:
    """Mỗi ngày sản xuất: sản lượng công tơ (O1), lượng đã phát hành, số yêu cầu bị giữ / bị từ chối."""
    devs = {s32(e["deviceId"]) for e in ev["DeviceRegistered"] if s32(e["cpId"]) == cp}
    issued, n_cert, rejected = {}, {}, {}
    for e in ev["Issued"]:
        if s32(e["deviceId"]) in devs:
            d = int(e["day"])
            issued[d] = issued.get(d, 0) + e["wh"]
            n_cert[d] = n_cert.get(d, 0) + 1
    for e in ev["IssueRejected"]:
        if s32(e["deviceId"]) in devs:
            rejected[int(e["day"])] = rejected.get(int(e["day"]), 0) + 1
    rows = []
    for e in ev["LotEvidenced"]:
        if s32(e["cpId"]) != cp:
            continue
        d = int(e["day"])
        status = chain.gate.functions.lotState(bytes(e["lotKey"])).call()[4]
        rows.append({"day": d, "ngày sản xuất": day_date(d).isoformat(), "công tơ O1 (kWh)": e["o1Wh"] / 1000,
                     "đã phát hành (kWh)": issued.get(d, 0) / 1000, "chứng chỉ": n_cert.get(d, 0),
                     "yêu cầu bị từ chối": rejected.get(d, 0), "cờ lớp B": flags_text(int(e["flags"])),
                     "trạng thái lô": STATUS[status], "gửi bằng chứng lúc": when(e["block"])})
    return pd.DataFrame(rows).sort_values("day").reset_index(drop=True) if rows else pd.DataFrame()


# ====================================================================== thành phần chi tiết

def lot_of(cp: str, day: int):
    key = bytes(chain.gate.functions.lotKeyOf(b32(cp), day).call())
    lot = next((e for e in ev["LotEvidenced"] if bytes(e["lotKey"]) == key), None)
    return key, lot


def series_chart(roots: list[bytes], names: tuple, scale: float, unit: str, colors: list[str]) -> None:
    series = {}
    for name, x in zip(names, roots):
        try:
            doc = chain.store.get(x)
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
        use_container_width=True)


def evidence_block(key: bytes, lot: dict) -> None:
    """Bằng chứng của lô: 4 báo cáo theo data_root (kiểm hash), cờ, reason code, biểu đồ 15 phút."""
    status = chain.gate.functions.lotState(key).call()[4]
    roots = [bytes(x) for x in lot["dataRoots"]]
    files = []
    for name, unit, x in zip(("O1 công tơ", "O2 tổng 24 inverter", "O3 bức xạ tại chỗ", "O4 bức xạ vệ tinh NSRDB"),
                             ("kWh", "kWh", "kWh/m²", "kWh/m²"), roots):
        try:
            doc = chain.store.get(x)
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
    c3.metric("Trạng thái lô", STATUS[status])
    st.caption(f"Bằng chứng gửi lúc {when(lot['block'])} (giờ nhà máy). Số liệu từng inverter không đưa lên chain; "
               "O2 là tổng 24 inverter của 6 thiết bị.")
    st.dataframe(pd.DataFrame(files), hide_index=True, use_container_width=True)
    rv = next((e for e in ev["LotReview"] if bytes(e["lotKey"]) == key), None)
    if rv is not None:
        f = chain.store.root / f"{bytes(rv['reasonsHash']).hex()}.json"
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
    show(pd.DataFrame([{"thời điểm": when(b), "bước": s, "chi tiết": d, "giao dịch": tx_url(h) or h[:18] + "…"}
                       for b, s, d, h in sorted(steps, key=lambda x: x[0])]))
    if lot:
        with st.expander("Bằng chứng của lô (4 báo cáo oracle, file gốc, biểu đồ)"):
            evidence_block(key, lot)


def statement(e: dict) -> None:
    """Tuyên bố retire (redemption statement) dựng lại từ event `Retired`."""
    tid = int(e["tokenId"])
    iss = next((x for x in ev["Issued"] if int(x["tokenId"]) == tid), None)
    st.markdown("#### Tuyên bố sử dụng chứng chỉ (redemption statement)")
    st.table(pd.DataFrame({"": [
        name_of(e["holder"]), e["beneficiary"], e["purpose"], e["consumptionLocation"], e["reportingPeriod"],
        f"{e['wh'] / 1000:,.3f} kWh",
        f"{s32(iss['deviceId'])}, ngày {day_date(int(iss['day']))}" if iss else "—",
        tok(tid), when(e["block"]), e["tx"]]},
        index=["Người retire", "Người thụ hưởng", "Mục đích", "Nơi tiêu thụ", "Kỳ báo cáo", "Lượng",
               "Nguồn (thiết bị, ngày sản xuất)", "tokenId", "Thời điểm retire", "Giao dịch"]))
    if chain.explorer:
        st.markdown(f"[Xem giao dịch retire trên Etherscan]({tx_url(e['tx'])})")
    st.caption("Tuyên bố không sửa được và không đảo ngược được (I-REC §10); phần chứng chỉ được retire đã bị đốt.")


def transfer_and_retire(holder_role: str, row: pd.Series, others: list[str]) -> None:
    """Hai form thao tác trên một chứng chỉ đang giữ: chuyển nhượng và retire."""
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


# ====================================================================== khung trang

st.sidebar.title("Registry I-REC")
role = st.sidebar.radio("Vai trò", ROLES)
net = "Sepolia" if chain.public else chain.dep["url"]
st.sidebar.caption(f"{net} · block {block}\n\nLớp B: {chain.dep['profile']} ({chain.dep['variant']})")
if chain.public:
    st.sidebar.markdown(f"[Contract chứng chỉ trên Etherscan]({chain.explorer}/token/{chain.certs.address})")
    st.sidebar.info("Sepolia: giao dịch ký tại máy bằng khóa suy ra từ TESTNET_MNEMONIC (contracts/.env); mỗi giao "
                    "dịch tốn ETH test và ghi công khai.")
else:
    st.sidebar.info("Demo: giao dịch ký bằng tài khoản mở khóa của node Hardhat; thời điểm theo đồng hồ mô phỏng. "
                    "Thực tế mỗi bên ký bằng ví riêng.")
if "flash" in st.session_state:
    kind, msg = st.session_state.pop("flash")
    (st.success if kind == "success" else st.error)(msg)

# ---------------------------------------------------------------------- công khai
if role == "Công khai":
    st.title("Registry chứng chỉ I-REC – điện mặt trời")
    sec = section(["Tổng quan", "Tra chứng chỉ", "Nhật ký công khai", "Lineage completeness"], "pub-sec")
    if sec == "Tổng quan":
        issued = sum(e["wh"] for e in ev["Issued"])
        retired = sum(e["wh"] for e in ev["Retired"])
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Đã phát hành", mwh(issued))
        c2.metric("Đã retire", mwh(retired))
        c3.metric("Yêu cầu bị từ chối", len(ev["IssueRejected"]))
        c4.metric("Lô bị REVIEW", len(ev["LotReview"]))
        c5.metric("Code Manager", f"{len(ev['Suspended']) + len(ev['Withdrawn'])} thao tác")
        prod = production_by_day(CP)
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
                tooltip=["ngày sản xuất", "loại", alt.Tooltip("MWh:Q", format=".3f")]), use_container_width=True)
    elif sec == "Tra chứng chỉ":
        st.caption("Bấm vào một dòng để xem chuỗi truy vết của chứng chỉ.")
        certs = certificates()
        i = pick(certs, "pub-certs")
        if i is not None:
            certificate_detail(int(certs.iloc[i]["tokenId"]))
    elif sec == "Nhật ký công khai":
        st.markdown("**Yêu cầu bị từ chối** (lý do lưu on-chain, I-REC §8.7)")
        show(pd.DataFrame([{"thời điểm": when(e["block"]), "yêu cầu": s32(e["reqId"]), "thiết bị": s32(e["deviceId"]),
                            "ngày sản xuất": day_date(int(e["day"])).isoformat(), "lý do": reason_of(e),
                            "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"}
                           for e in sorted(ev["IssueRejected"], key=lambda x: -x["block"])]))
        st.markdown("**Thao tác của Code Manager** (I-REC §11; luôn công khai, kèm lý do)")
        cmap = cert_of()
        cm = [{"thời điểm": when(e["block"]), "thao tác": "tạm khóa" if e["active"] else "mở khóa",
               "chứng chỉ": " · ".join(map(str, cmap.get(int(e["tokenId"]), ("?", "")))), "tokenId (hex)": tok(e["tokenId"]),
               "lượng (kWh)": None,
               "lý do": e["reason"], "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"} for e in ev["Suspended"]]
        cm += [{"thời điểm": when(e["block"]), "thao tác": "rút",
                "chứng chỉ": " · ".join(map(str, cmap.get(int(e["tokenId"]), ("?", "")))), "tokenId (hex)": tok(e["tokenId"]),
                "lượng (kWh)": e["wh"] / 1000,
                "lý do": e["reason"], "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"} for e in ev["Withdrawn"]]
        show(pd.DataFrame(cm))
        st.markdown("**Phân xử của Production Auditor**")
        lots = {bytes(x["lotKey"]): x for x in ev["LotEvidenced"]}
        show(pd.DataFrame([{"thời điểm": when(e["block"]),
                            "ngày sản xuất của lô": day_date(int(lots[bytes(e["lotKey"])]["day"])).isoformat(),
                            "kết quả": "duyệt" if e["approved"] else "bác", "auditor": name_of(e["auditor"]),
                            "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"} for e in ev["LotResolved"]]))
    else:
        lin = lineage(chain, chain.store)
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

# ---------------------------------------------------------------------- nhà máy
elif role == "Nhà máy":
    st.title(f"Nhà máy · {CP}")
    st.caption("Chứng chỉ được MINT thẳng vào địa chỉ của nhà máy khi lô qua lớp A và lớp B. Nhà máy bán cho người mua "
               "bằng cách chuyển nhượng (thanh toán nằm ngoài hệ thống), hoặc tự retire nếu tự dùng điện.")
    prod = production_by_day(CP)
    mine = holdings(PLANT)
    sent = transfers(PLANT, outgoing=True)
    pending = requests_of_cp(CP)
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
            key, lot = lot_of(CP, d)
            st.markdown(f"#### Ngày sản xuất {day_date(d)}")
            held_info = {r["req_id"]: r for r in chain.dep.get("held_requests", [])}
            rows = [{"thiết bị": s32(e["deviceId"]), "kết cục": "đã phát hành", "lượng (kWh)": e["wh"] / 1000,
                     "lý do": "", "thời điểm": when(e["block"]), "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"}
                    for e in ev["Issued"] if int(e["day"]) == d]
            rows += [{"thiết bị": s32(e["deviceId"]), "kết cục": "bị từ chối", "lượng (kWh)": None,
                      "lý do": reason_of(e), "thời điểm": when(e["block"]),
                      "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"}
                     for e in ev["IssueRejected"] if int(e["day"]) == d]
            done = {(r["thiết bị"]) for r in rows if r["kết cục"] == "đã phát hành"}
            rows += [{"thiết bị": held_info[s32(e["reqId"])]["device"], "kết cục": "bị giữ (chờ auditor)",
                      "lượng (kWh)": held_info[s32(e["reqId"])]["wh"] / 1000, "lý do": "lô bị lớp B đánh dấu",
                      "thời điểm": when(e["block"]), "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"}
                     for e in ev["IssueHeld"] if bytes(e["lotKey"]) == key and s32(e["reqId"]) in held_info
                     and held_info[s32(e["reqId"])]["device"] not in done]
            day_df = pd.DataFrame(rows).sort_values(["thiết bị", "thời điểm"]) if rows else pd.DataFrame()
            if len(day_df):  # yêu cầu bị từ chối không có lượng on-chain: hiện "—" thay vì "None"
                day_df["lượng"] = [f"{v:,.1f} kWh" if pd.notna(v) else "—" for v in day_df.pop("lượng (kWh)")]
                day_df = day_df[["thiết bị", "kết cục", "lượng", "lý do", "thời điểm", "giao dịch"]]
            show(day_df)
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

# ---------------------------------------------------------------------- người mua
elif role == "Người mua":
    buyer = st.sidebar.selectbox("Tài khoản", ["buyer1", "buyer2", "buyer3"])
    st.title(f"Người mua · {buyer}")
    st.caption("Người mua nhận chứng chỉ qua chuyển nhượng, có thể chuyển tiếp, và retire khi dùng để tuyên bố "
               "điện tái tạo. Retire ghi người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo; không đảo ngược được.")
    addr = chain.dep["roles"][buyer]
    mine = holdings(addr)
    got = transfers(addr, outgoing=False)
    mine_r = sorted((e for e in ev["Retired"] if e["holder"] == addr), key=lambda e: -e["block"])
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
            transfer_and_retire(buyer, row, [b for b in ("buyer1", "buyer2", "buyer3") if b != buyer])
            certificate_detail(int(row["tokenId"]))
    elif sec == "Chứng chỉ trên hệ thống":
        st.caption("Mọi chứng chỉ đã phát hành. Cột \"nhà máy còn giữ\" là lượng chưa bán; muốn mua thì liên hệ nhà máy "
                   "(thanh toán ngoài hệ thống), nhà máy chuyển nhượng sang tài khoản của bạn.")
        allc = balances(balances(certificates(), PLANT, "nhà máy còn giữ (kWh)"), addr, "bạn đang giữ (kWh)", 7)
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
        table = pd.DataFrame([{"thời điểm": when(e["block"]), "chứng chỉ": " · ".join(map(str, cert_of().get(
            int(e["tokenId"]), ("?", "")))), "tokenId (hex)": tok(e["tokenId"]), "lượng (kWh)": e["wh"] / 1000,
            "thụ hưởng": e["beneficiary"],
            "mục đích": e["purpose"], "kỳ": e["reportingPeriod"]} for e in mine_r])
        i = pick(table, f"{buyer}-stmts")
        if i is not None:
            statement(mine_r[i])

# ---------------------------------------------------------------------- issuer
elif role == "Issuer":
    issuer = st.sidebar.selectbox("Tài khoản", ["issuerA", "issuerB"])
    st.title(f"Issuer · {issuer}")
    st.caption("Yêu cầu của lô REVIEW bị giữ, không được lưu on-chain; issuer gửi lại sau khi auditor duyệt.")
    rows = []
    for r in chain.dep.get("held_requests", []):
        if r["issuer"] != issuer:
            continue
        key, _ = lot_of(CP, r["day"])
        status = chain.gate.functions.lotState(key).call()[4]
        done = chain.certs.functions.keyUsed(b32(r["device"]), r["day"]).call()
        rows.append({**r, "lô": STATUS[status], "đã phát hành": done})
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
    devs = {s32(e["deviceId"]) for e in ev["DeviceRegistered"] if e["issuer"] == chain.dep["roles"][issuer]}
    show(pd.DataFrame([{"thời điểm": when(e["block"]), "yêu cầu": s32(e["reqId"]), "thiết bị": s32(e["deviceId"]),
                        "ngày sản xuất": day_date(int(e["day"])).isoformat(), "lý do": reason_of(e),
                        "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"}
                       for e in sorted(ev["IssueRejected"], key=lambda x: -x["block"]) if s32(e["deviceId"]) in devs]))

# ---------------------------------------------------------------------- production auditor
else:
    st.title("Production Auditor")
    st.caption("Lớp B đánh dấu theo lô (cả nhà máy trong một ngày). Mọi chứng chỉ của lô bị giữ cho tới khi auditor "
               "phân xử; quyết định áp dụng cho cả lô. Khóa auditor chỉ đổi trạng thái lô, không mint được.")
    wh_of = {r["req_id"]: r for r in chain.dep.get("held_requests", [])}
    lots = {bytes(e["lotKey"]): e for e in ev["LotEvidenced"]}
    issued_by_req = {s32(e["reqId"]): e for e in ev["Issued"]}
    rows, seen = [], set()
    for e in ev["IssueHeld"]:
        rid, key = s32(e["reqId"]), bytes(e["lotKey"])
        if rid in seen:  # issuer gửi lại khi lô vẫn REVIEW thì có thêm một IssueHeld trùng
            continue
        seen.add(rid)
        lot = lots[key]
        status = chain.gate.functions.lotState(key).call()[4]
        r = wh_of.get(rid) or ({"device": s32(issued_by_req[rid]["deviceId"]), "wh": issued_by_req[rid]["wh"]}
                               if rid in issued_by_req else {})
        rows.append({"key": key, "yêu cầu": rid, "thiết bị": r.get("device", "—"),
                     "ngày sản xuất": day_date(int(lot["day"])).isoformat(), "lượng xin (kWh)": r.get("wh", 0) / 1000,
                     "cờ lớp B": flags_text(int(lot["flags"])), "O1 của lô (kWh)": lot["o1Wh"] / 1000,
                     "trạng thái lô": STATUS[status], "bị giữ lúc": when(e["block"])})
    allq = pd.DataFrame(rows)
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
            lot = lots[key]
            st.markdown(f"#### {row['yêu cầu']} · thiết bị {row['thiết bị']} · ngày sản xuất {row['ngày sản xuất']}")
            st.write(f"Chứng chỉ này xin **{row['lượng xin (kWh)']:,.1f} kWh**. Cả lô có "
                     f"{int((queue['key'] == key).sum())} chứng chỉ chờ, tổng "
                     f"{queue.loc[queue['key'] == key, 'lượng xin (kWh)'].sum():,.1f} kWh.")
            evidence_block(key, lot)
            with st.form(f"resolve-{key.hex()}"):
                note = st.text_input("Lý do (ghi hash on-chain, nội dung lưu ở hồ sơ auditor)",
                                     "Đã đối chiếu hóa đơn điện lực")
                c1, c2 = st.columns(2)
                approve = c1.form_submit_button("Duyệt cả lô", type="primary")
                reject = c2.form_submit_button("Bác cả lô")
                if approve or reject:
                    send(chain.gate.functions.resolveReview(key, bool(approve), Web3.keccak(text=note)), "auditor",
                         ("Đã duyệt" if approve else "Đã bác") + " lô ngày " + str(row["ngày sản xuất"]) +
                         (". Issuer gửi lại yêu cầu để được MINT." if approve else
                          ". Mọi yêu cầu của lô sẽ bị REJECT (LOT_REJECTED)."))
    elif sec == "Mọi lô đã gửi":
        st.caption("Mọi bằng chứng của lô đã gửi lên chain, kể cả lô sạch. Bấm vào một lô để xem 4 báo cáo oracle và "
                   "biểu đồ 15 phút.")
        all_lots = pd.DataFrame([{"key": bytes(e["lotKey"]), "gửi lúc": when(e["block"]), "CP": s32(e["cpId"]),
                                  "ngày sản xuất": day_date(int(e["day"])).isoformat(), "O1 (kWh)": e["o1Wh"] / 1000,
                                  "cờ lớp B": flags_text(int(e["flags"])),
                                  "trạng thái lô": STATUS[chain.gate.functions.lotState(bytes(e["lotKey"])).call()[4]],
                                  "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"}
                                 for e in sorted(ev["LotEvidenced"], key=lambda x: int(x["day"]))])
        status_filter = st.multiselect("Lọc theo trạng thái lô", STATUS[1:], default=STATUS[1:])
        if len(all_lots):
            all_lots = all_lots[all_lots["trạng thái lô"].isin(status_filter)].reset_index(drop=True)
        i = pick(all_lots, "audit-lots", hide=("key",))
        if i is not None:
            evidence_block(all_lots.iloc[i]["key"], lots[all_lots.iloc[i]["key"]])
    elif sec == "Yêu cầu bị từ chối":
        st.caption("Yêu cầu bị lớp A từ chối tự động (không qua auditor), kèm lý do lưu on-chain.")
        show(pd.DataFrame([{"thời điểm": when(e["block"]), "yêu cầu": s32(e["reqId"]), "thiết bị": s32(e["deviceId"]),
                            "ngày sản xuất": day_date(int(e["day"])).isoformat(), "lý do": reason_of(e),
                            "giao dịch": tx_url(e["tx"]) or e["tx"][:18] + "…"}
                           for e in sorted(ev["IssueRejected"], key=lambda x: -x["block"])]))
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
