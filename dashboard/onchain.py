"""Kết nối chain, đọc event, gửi giao dịch.

Log được đọc cộng dồn (chỉ block mới) và chia khúc, vì nhà cung cấp RPC công khai giới hạn khoảng block mỗi lần
`eth_getLogs`. URL RPC chứa API key nên không bao giờ hiện trên trang (`redact`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st
from eth_utils import keccak
from web3 import Web3

from dashboard import state as S
from rec import config
from rec.deploy.testnet import load_env
from rec.oracles.signer import hardhat_account
from rec.oracles.store import FileStore
from rec.registry.chain_registry import ROLES, _artifact
from rec.timeutil import PLANT_TZ

SOURCES = {"Hardhat cục bộ": ("demo", "deployment.json"), "Sepolia (testnet)": ("testnet", "deployment.json")}
LOG_CHUNK = 2_000  # số block mỗi lần eth_getLogs; tự hạ xuống LOG_CHUNK_MIN nếu nhà cung cấp RPC từ chối
LOG_CHUNK_MIN = 10  # Alchemy gói miễn phí chỉ cho khoảng 10 block mỗi lần
EVENT_NAMES = {"gate": ["LotEvidenced", "LotReview", "LotResolved", "O1Conflict", "Issued", "IssueRejected",
                         "IssueHeld"],
               "certs": ["TransferSingle", "Retired", "Suspended", "Withdrawn"],
               "devices": ["DeviceRegistered", "RegistrationTransferred", "RegistrationClosed"]}


def s32(b) -> str:
    return bytes(b).rstrip(b"\0").decode("ascii", "replace")


def b32(s: str) -> bytes:
    return s.encode("ascii").ljust(32, b"\0")


def available_sources() -> list[str]:
    return [k for k, v in SOURCES.items() if config.resolve_path("artifacts").joinpath(*v).exists()]


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


def fetch_logs(chain, source: str, latest: int) -> list:
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


def load_events(chain, source: str, block: int) -> dict:
    """Giải mã log thô thành event theo tên; mỗi event thêm block và tx."""
    by_addr = {}
    for attr, names in EVENT_NAMES.items():
        contract = getattr(chain, attr)
        by_addr[contract.address.lower()] = [(n, getattr(contract.events, n)()) for n in names]
    out = {n: [] for names in EVENT_NAMES.values() for n in names}
    for lg in fetch_logs(chain, source, block):
        for n, ev_ in by_addr.get(lg["address"].lower(), []):
            try:
                d = ev_.process_log(lg)
            except Exception:  # noqa: BLE001 – log của event khác cùng contract
                continue
            out[n].append(dict(d.args) | {"block": d.blockNumber,
                                          "tx": "0x" + bytes(d.transactionHash).hex()})
            break
    return out


@st.cache_resource
def block_times(source: str) -> dict:
    return {}


def when(n: int) -> str:
    """Thời điểm của block theo giờ nhà máy (Hardhat cục bộ: đồng hồ mô phỏng; Sepolia: giờ thật)."""
    cache = block_times(S.source)
    if n not in cache:
        ts = S.chain.w3.eth.get_block(n)["timestamp"]
        cache[n] = pd.Timestamp(ts, unit="s", tz="UTC").tz_convert(PLANT_TZ).strftime("%Y-%m-%d %H:%M")
    return cache[n]


def tx_url(h: str) -> str | None:
    return f"{S.chain.explorer}/tx/{h}" if S.chain.explorer else None


def tx_cell(h: str) -> str:
    """Ô "giao dịch" của bảng: liên kết Etherscan trên Sepolia, hash rút gọn trên Hardhat."""
    return tx_url(h) or h[:18] + "…"


def tx_link(h: str) -> str:
    return f"[{h[:12]}…]({S.chain.explorer}/tx/{h})" if S.chain.explorer else f"{h[:18]}…"


def transact(fn, role: str):
    """Gửi giao dịch bằng vai `role`: node Hardhat ký hộ (tài khoản mở khóa); Sepolia ký tại máy bằng khóa từ mnemonic."""
    chain = S.chain
    if not chain.public:
        tx = fn.transact({"from": chain.dep["roles"][role], "gas": 1_000_000, "gasPrice": 0})
        return chain.w3.eth.wait_for_transaction_receipt(tx)
    acct = chain.key_of(role)
    tx = fn.build_transaction({"from": acct.address, "nonce": chain.w3.eth.get_transaction_count(acct.address, "pending")})
    tx["gas"] = int(tx["gas"] * 1.2)
    h = chain.w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
    return chain.w3.eth.wait_for_transaction_receipt(h, timeout=600, poll_latency=2)


def send(fn, role: str, done: str) -> None:
    """Gửi giao dịch bằng tài khoản của vai `role`; báo kết quả sau khi trang tải lại."""
    try:
        with st.spinner("Đang gửi giao dịch" + (" lên Sepolia (khoảng 12–30 giây)…" if S.chain.public else "…")):
            rcpt = transact(fn, role)
        h = "0x" + bytes(rcpt.transactionHash).hex()
        st.session_state["flash"] = ("success", f"{done} · block {rcpt.blockNumber}, gas {rcpt.gasUsed:,} · tx {tx_link(h)}")
    except Exception as e:  # noqa: BLE001 – contract revert
        text = str(getattr(e, "data", "")) + " " + str(e)
        name = next((S.chain.errors[s.lower()] for s in re.findall(r"0x[0-9a-fA-F]{8}", text)
                     if s.lower() in S.chain.errors), None)
        st.session_state["flash"] = ("error", f"Giao dịch bị từ chối: {name or redact(text)[:200]}")
    clear_selection()
    st.cache_data.clear()
    st.rerun()


def clear_selection() -> None:
    """Bỏ chọn mọi bảng sau một giao dịch, để dòng đang chọn không nhảy sang chứng chỉ hoặc lô khác."""
    for k in [k for k in st.session_state if k.endswith(("-certs", "-queue", "-done", "-locked", "-stmts", "-days",
                                                             "-sent", "-all", "-got", "-lots", "-cases"))]:
        del st.session_state[k]
