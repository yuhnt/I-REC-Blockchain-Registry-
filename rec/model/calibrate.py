"""Chọn ngưỡng của lớp B trên lô trung thực của val (SPEC mục 6.2, configs/thresholds.yaml).

- Nhất quán: τ của 4 thống kê là phân vị cùng mức q; chọn q nhỏ nhất sao cho hợp các cờ ≤ 1%.
- Trần: τ nhỏ nhất sao cho số lô trung thực có O1 > nền · (1 + τ) không vượt q_trần · n.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from rec.checks.consistency import STATS


def consistency_thresholds(val_stats: pd.DataFrame, target: float) -> tuple[dict[str, float], float, float]:
    """(τ theo thống kê, mức phân vị q, tỉ lệ hợp các cờ đạt được trên val)."""
    best = None
    for q in np.linspace(0.95, 1.0, 1001):
        tau = {s: float(np.nanquantile(val_stats[s], q)) for s in STATS}
        rate = float(flag_consistency(val_stats, tau).mean())
        if rate <= target:
            best = (tau, float(q), rate)
            break
    if best is None:
        raise RuntimeError("không tìm được ngưỡng nhất quán")
    return best


def flag_consistency(stats: pd.DataFrame, tau: dict[str, float]) -> pd.Series:
    flag = pd.Series(False, index=stats.index)
    for s in STATS:
        flag |= stats[s].to_numpy() > tau[s]  # NaN so sánh ra False: không đủ dữ liệu thì không báo
    return flag


def ceiling_tau(y: np.ndarray, base: np.ndarray, target: float) -> tuple[float, float]:
    """(τ, tỉ lệ đạt được) sao cho #(y > base · (1 + τ)) ≤ ⌊target · n⌋."""
    r = np.sort(y / base - 1)[::-1]
    k = int(np.floor(target * len(r)))
    tau = float(r[k]) if k < len(r) else float(r[-1])
    return tau, float(np.mean(y > base * (1 + tau)))
