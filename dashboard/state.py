"""Ngữ cảnh của lần tải trang hiện tại: chain đang đọc, event đã giải mã, block mới nhất, tên các vai.

Module Python chỉ được nạp một lần cho mọi phiên trình duyệt, nên ngữ cảnh nằm trong `st.session_state`: hai người
mở dashboard cùng lúc (ví dụ một người xem Hardhat, một người xem Sepolia) không giẫm lên nhau.
Dùng: `from dashboard import state as S`, rồi `S.chain`, `S.ev`, `S.source`, `S.block`, `S.PLANT`, `S.CP`.
"""
from __future__ import annotations

import streamlit as st

_KEY = "_dashboard_ctx"


def set_context(**kw) -> None:
    st.session_state[_KEY] = st.session_state.get(_KEY, {}) | kw


def __getattr__(name: str):
    ctx = st.session_state.get(_KEY, {})
    if name in ctx:
        return ctx[name]
    raise AttributeError(name)


def name_of(addr: str) -> str:
    """Tên vai của một địa chỉ (plant, buyer1, …); địa chỉ lạ thì rút gọn."""
    return __getattr__("addr_name").get(addr, addr[:10] + "…")
