"""Mã hóa chuỗi 15 phút của một báo cáo oracle và tính data_root (FLOW.md mục 2).

data_root = keccak256 của dãy giá trị theo thứ tự slot, mỗi giá trị là int64 big-endian; slot thiếu ghi -1.
Contract và Python phải cho cùng kết quả, nên mọi bên dùng đúng hàm này.
"""
from __future__ import annotations

import math
from collections.abc import Iterable

from eth_utils import keccak

MISSING = -1


def to_ints(values: Iterable[float | None]) -> list[int]:
    """Làm tròn về số nguyên; None hoặc NaN thành MISSING. Giá trị âm (trừ MISSING) không hợp lệ."""
    out = []
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(MISSING)
            continue
        iv = int(round(v))
        if iv < 0:
            raise ValueError(f"giá trị slot âm: {v}")
        out.append(iv)
    return out


def encode(values: Iterable[float | None]) -> bytes:
    return b"".join(v.to_bytes(8, "big", signed=True) for v in to_ints(values))


def data_root(values: Iterable[float | None]) -> bytes:
    return keccak(encode(values))
