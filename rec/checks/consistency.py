"""Bước ① (đủ báo cáo) và ② (nhất quán một phía) của lớp B (SPEC mục 6.2).

Thống kê của một lô:
- r12_day  = ΣO1 / (η · ΣO2) − 1 trên các slot ban ngày cả hai cùng có số liệu;
- r12_slot = max theo slot của O1 / (η · O2) − 1, chỉ xét slot có O2 ≥ 5% công suất slot;
- r13_day, r13_slot: tương tự với E₃ (sản lượng kỳ vọng từ POA và nhiệt độ tại chỗ).
Luật chỉ một phía: REVIEW khi một thống kê vượt ngưỡng dương (O1 cao hơn). NaN = không đủ dữ liệu để so.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from rec.schema import OracleId

STATS = ("r12_day", "r12_slot", "r13_day", "r13_slot")


@dataclass
class ConsistencyModel:
    eta: float          # công tơ / tổng inverter
    beta: float         # Wh của slot trên mỗi Wh/m² POA
    gamma: float        # hệ số nhiệt (1/°C)
    cap_slot_wh: float  # công suất AC của CP × 0,25 h
    min_frac: float = 0.05

    def e3(self, poa_whm2: np.ndarray, temp_c: np.ndarray) -> np.ndarray:
        t = np.where(np.isnan(temp_c), 25.0, temp_c)  # thiếu nhiệt độ thì bỏ hiệu chỉnh nhiệt
        return np.minimum(self.cap_slot_wh, self.beta * poa_whm2 * (1 + self.gamma * (t - 25.0)))

    def to_dict(self) -> dict:
        return asdict(self)


def fit(series_by_day: dict, sun_by_day: dict, temp_by_day: dict, days: list[int], cap_slot_wh: float
        ) -> ConsistencyModel:
    """Khớp η, β, γ trên các ngày cho trước (ngày trung thực của train)."""
    o1s, o2s, x1, x2, ys = [], [], [], [], []
    for d in days:
        s, sun, t = series_by_day[d], sun_by_day[d], temp_by_day[d]
        o1, o2, o3 = s[OracleId.O1], s[OracleId.O2], s[OracleId.O3]
        both = sun & ~np.isnan(o1) & ~np.isnan(o2)
        o1s.append(o1[both].sum())
        o2s.append(o2[both].sum())
        ok = sun & ~np.isnan(o1) & ~np.isnan(o3) & ~np.isnan(t) & (o1 < 0.95 * cap_slot_wh) & (o3 > 0)
        x1.append(o3[ok])
        x2.append(o3[ok] * (t[ok] - 25.0))
        ys.append(o1[ok])
    eta = float(np.median(np.array(o1s) / np.maximum(np.array(o2s), 1e-9)))
    X = np.column_stack([np.concatenate(x1), np.concatenate(x2)])
    coef, *_ = np.linalg.lstsq(X, np.concatenate(ys), rcond=None)
    return ConsistencyModel(eta=eta, beta=float(coef[0]), gamma=float(coef[1] / coef[0]), cap_slot_wh=cap_slot_wh)


def _ratio_stats(num: np.ndarray, den: np.ndarray, mask: np.ndarray, big: float, window: int | None
                 ) -> tuple[float, float]:
    """(tỷ số theo ngày − 1, max theo cửa sổ `window` slot − 1).

    Cửa sổ chỉ được xét khi đủ `window` slot có số liệu và mẫu số ≥ big × window.
    window = 1 là cách tính đăng ký trước (spec-v1); None bỏ thống kê theo slot (manifests/CHANGES.md).
    """
    if not mask.any() or den[mask].sum() <= 0:
        return np.nan, np.nan
    day = float(num[mask].sum() / den[mask].sum() - 1)
    if window is None:
        return day, np.nan
    k = np.ones(window)
    ns = np.convolve(np.where(mask, num, 0.0), k, "valid")
    ds = np.convolve(np.where(mask, den, 0.0), k, "valid")
    cs = np.convolve(mask.astype(float), k, "valid")
    ok = (cs == window) & (ds >= big * window)
    slot = float(np.max(ns[ok] / ds[ok]) - 1) if ok.any() else np.nan
    return day, slot


def stats(series: dict, sun: np.ndarray, temp: np.ndarray, m: ConsistencyModel, window: int | None = 1
          ) -> dict[str, float]:
    o1, o2, o3 = series[OracleId.O1], series[OracleId.O2], series[OracleId.O3]
    big = m.min_frac * m.cap_slot_wh
    m12 = sun & ~np.isnan(o1) & ~np.isnan(o2)
    r12d, r12s = _ratio_stats(o1, m.eta * np.nan_to_num(o2), m12, big, window)
    e3 = m.e3(o3, temp)
    m13 = sun & ~np.isnan(o1) & ~np.isnan(e3)
    r13d, r13s = _ratio_stats(o1, np.nan_to_num(e3), m13, big, window)
    return {"r12_day": r12d, "r12_slot": r12s, "r13_day": r13d, "r13_slot": r13s}


VARIANTS = {"prereg": 1, "hour": 4, "day_only": None}  # cửa sổ của thống kê theo slot


def coverage(series: dict, sun: np.ndarray) -> dict[str, float]:
    """Tỉ lệ slot ban ngày có số liệu của từng oracle (bước ①)."""
    n = max(int(sun.sum()), 1)
    return {o.value: float((~np.isnan(v[sun])).sum() / n) for o, v in series.items()}
