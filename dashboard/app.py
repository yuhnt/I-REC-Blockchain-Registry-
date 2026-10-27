"""Dashboard (FLOW.md mục 12): mỗi vai một trang, đọc event on-chain và kho file theo `data_root`.

- Công khai: tổng quan, tra mọi chứng chỉ, nhật ký công khai, lineage completeness;
- Truy vết kịch bản: mỗi kịch bản demo, điểm chặn kỳ vọng so với kết quả on-chain (cho người trình bày);
- Nhà máy: sản xuất theo ngày, chứng chỉ đang giữ (chuyển nhượng, retire), yêu cầu bị từ chối / bị giữ;
- Người mua: chứng chỉ đang giữ, chứng chỉ trên hệ thống, lịch sử nhận, retire kèm tuyên bố (I-REC §10);
- Issuer: yêu cầu bị giữ vì lô REVIEW, gửi lại sau khi auditor duyệt;
- Production Auditor: chứng chỉ chờ duyệt (xem bằng chứng rồi duyệt / bác cả lô), mọi lô, lô đã phân xử.
Mã của từng trang ở dashboard/views/; bảng dữ liệu ở tables.py, khối hiển thị chung ở components.py, kết nối chain
và gửi giao dịch ở onchain.py.

Chạy sau khi dựng chain demo:
    python -m rec.deploy.demo                  (Hardhat cục bộ)
    python -m rec.deploy.testnet deploy, demo  (Sepolia; xem rec/deploy/testnet.py)
    streamlit run dashboard/app.py
Thanh bên chọn chain. Hardhat cục bộ: giao dịch ký bằng tài khoản đã mở khóa của node. Sepolia: ký tại máy bằng khóa
suy ra từ TESTNET_MNEMONIC trong contracts/.env; URL RPC (chứa API key) không bao giờ hiện trên trang.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard import state as S  # noqa: E402
from dashboard.onchain import available_sources, connect, load_events, redact, s32  # noqa: E402
from dashboard.views import auditor, buyer, cases, issuer, plant, public  # noqa: E402

PAGES = {"Công khai": public, "Truy vết kịch bản": cases, "Nhà máy": plant, "Người mua": buyer, "Issuer": issuer,
         "Production Auditor": auditor}

st.set_page_config(page_title="Registry I-REC – demo", layout="wide")

available = available_sources()
source = st.sidebar.selectbox("Chain", available or ["Hardhat cục bộ"])
try:
    chain = connect(source) if available else None
    connected = False
    for i in range(3):  # RPC công khai có thể trả 429 (quá nhiều lời gọi) trong chốc lát
        connected = chain is not None and chain.w3.is_connected()
        if connected or chain is None:
            break
        time.sleep(2 * (i + 1))
except Exception:  # noqa: BLE001
    chain, connected = None, False
if not connected:
    st.title("Registry chứng chỉ I-REC – điện mặt trời")
    st.error("Chưa kết nối được chain. Hardhat cục bộ: chạy `python -m rec.deploy.demo`. Sepolia: chạy "
             "`python -m rec.deploy.testnet deploy` rồi `demo`, và kiểm tra `contracts/.env`.")
    st.stop()
try:
    block = chain.w3.eth.block_number
    ev = load_events(chain, source, block)
except Exception as e:  # noqa: BLE001 – lỗi RPC: hiện thông báo đã bỏ URL, không hiện traceback
    st.error(f"Lỗi khi đọc chain: {type(e).__name__}: {redact(e)[:300]}")
    st.stop()
S.set_context(chain=chain, ev=ev, source=source, block=block, addr_name={v: k for k, v in chain.dep["roles"].items()},
              PLANT=chain.dep["roles"]["plant"], CP=next(iter(s32(e["cpId"]) for e in ev["DeviceRegistered"]), "CP-1"))

st.sidebar.title("Registry I-REC")
role = st.sidebar.radio("Vai trò", list(PAGES))
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

PAGES[role].render()
