"""Chỉ số của E2 (SPEC mục 7–8): recall, OIR, tỉ lệ REVIEW nhầm, precision theo tỷ lệ gian lận, LMAX.

Đơn vị là lô (một ngày của CP). Một lô bị tấn công coi là "bắt được" nếu bị REVIEW hoặc có yêu cầu bị REJECT.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from rec.checks.consistency import STATS

PREVALENCE = (0.01, 0.05, 0.20)
SLOT_HOURS = 0.25


def decide(feat: pd.DataFrame, profile, tau_cons: dict, base: np.ndarray | None, tau_ceiling: float | None,
           min_cov: float) -> pd.DataFrame:
    """Quyết định của một cấu hình cho mọi ca: cờ lớp B, phát hiện, lượng mint."""
    flag = np.zeros(len(feat), dtype=bool)
    if profile.completeness:
        flag |= feat["cov_min"].to_numpy() < min_cov
    if profile.consistency:
        for s in STATS:
            flag |= feat[s].to_numpy() > tau_cons[s]
    if profile.ceiling is not None:
        flag |= feat["o1_day"].to_numpy() > base * (1 + tau_ceiling)
    minted = np.where(flag, 0, feat["minted_a_wh"].to_numpy())
    return pd.DataFrame({"flag_b": flag, "detected": flag | feat["a_reject"].to_numpy(), "minted_wh": minted},
                        index=feat.index)


def summarize(feat: pd.DataFrame, dec: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(bảng theo kịch bản và tham số, bảng phía người trung thực)."""
    df = feat[["case_id", "scenario", "params", "seed", "day", "y_wh"]].join(dec)
    df = df.merge(labels[["case_id", "kind", "excess_wh_true", "scenario"]].rename(columns={"scenario": "label"}),
                  on="case_id")
    honest = df[df["scenario"] == "honest"]
    fpr = float(honest["detected"].mean())
    held = float(honest.loc[honest["detected"], "y_wh"].sum() / honest["y_wh"].sum())
    by_neg = honest.groupby("label")["detected"].agg(["mean", "size"]).rename(columns={"mean": "review_rate",
                                                                                        "size": "lots"})
    honest_tbl = by_neg.reset_index().rename(columns={"label": "neg_type"})
    honest_tbl.loc[len(honest_tbl)] = {"neg_type": "all", "review_rate": fpr, "lots": len(honest)}
    honest_tbl["mwh_held_share"] = held

    att = df[df["scenario"] != "honest"].copy()
    att["minted_excess"] = np.maximum(0, att["minted_wh"] - att["y_wh"])
    g = att.groupby(["scenario", "params"])
    tbl = g.agg(cases=("case_id", "size"), days=("day", "nunique"), recall=("detected", "mean"),
                minted_excess=("minted_excess", "sum"), y=("y_wh", "sum")).reset_index()
    tbl["oir"] = tbl["minted_excess"] / tbl["y"]
    for pi in PREVALENCE:
        tbl[f"precision_{int(pi * 100)}"] = pi * tbl["recall"] / (pi * tbl["recall"] + (1 - pi) * fpr)
    return tbl.drop(columns=["minted_excess", "y"]), honest_tbl


def lmax_scale(day: pd.DataFrame, k: int, tau_cons: dict, profile, base: np.ndarray | None,
               tau_ceiling: float | None, min_cov: float, cp_cap_w: float,
               base_fn: Callable[[np.ndarray], np.ndarray] | None = None) -> np.ndarray:
    """Hệ số nhân lớn nhất s* mà kẻ gian thích nghi (sửa k nguồn) áp lên chuỗi thật mà mọi kiểm tra vẫn qua.

    Trả 0 nếu lô không thể mint ở bất kỳ s nào (ví dụ lô trung thực đã bị cờ bởi kiểm tra kẻ gian không sửa được).
    """
    y = day["y_wh"].to_numpy(float)
    s = np.minimum(cp_cap_w * day["sun_slots"].to_numpy() * SLOT_HOURS / y,
                   cp_cap_w * SLOT_HOURS / day["o1_max"].to_numpy(float))
    blocked = np.zeros(len(day), dtype=bool)
    if profile.completeness:
        blocked |= day["cov_min"].to_numpy() < min_cov
    if profile.consistency:
        scaled = {"r12": k >= 2, "r13": k >= 3}  # đối tác của O1 trong thống kê có bị sửa cùng không
        for st in STATS:
            v = day[st].to_numpy(float)
            if scaled[st[:3]]:
                blocked |= v > tau_cons[st]  # tỷ số không đổi khi cả hai nguồn cùng bị nhân
            else:
                lim = (1 + tau_cons[st]) / (1 + v)
                s = np.where(np.isnan(v), s, np.minimum(s, lim))
    if profile.ceiling is not None:
        if base_fn is not None and k >= 3:  # A1: trần phụ thuộc O3, mà O3 cũng bị nhân
            s = np.minimum(s, _search_scale(day, base_fn, tau_ceiling, s))
        else:
            s = np.minimum(s, base * (1 + tau_ceiling) / y)
    return np.where(blocked, 0.0, s)


def _search_scale(day: pd.DataFrame, base_fn, tau: float, s_hi: np.ndarray, grid=np.arange(1.0, 3.0001, 0.002)
                  ) -> np.ndarray:
    y = day["y_wh"].to_numpy(float)
    best = np.full(len(day), 1.0)
    for g in grid:
        ok = g * y <= base_fn(g) * (1 + tau)
        best = np.where(ok & (g <= s_hi), np.maximum(best, g), best)
    return best


def lmax(y: np.ndarray, s: np.ndarray) -> float:
    return float(np.sum(y * np.clip(s - 1, 0, None)) / np.sum(y))


def bootstrap_diff(y: np.ndarray, s_a: np.ndarray, s_b: np.ndarray, n: int = 1000, seed: int = 0
                   ) -> tuple[float, float, float]:
    """Hiệu LMAX(a) − LMAX(b) và khoảng tin cậy 95% bằng bootstrap theo ngày."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(y), size=(n, len(y)))
    diffs = np.array([lmax(y[i], s_a[i]) - lmax(y[i], s_b[i]) for i in idx])
    return lmax(y, s_a) - lmax(y, s_b), float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))
