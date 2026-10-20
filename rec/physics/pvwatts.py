"""Sản lượng kỳ vọng theo vật lý từ bức xạ vệ tinh (O4): nền của trần B2 (SPEC mục 6.2).

PVWatts: công suất DC = pdc0 · POA/1000 · (1 + γ (T_cell − 25)), nhiệt độ cell theo mô hình Faiman
từ nhiệt độ không khí và gió của NSRDB; AC = min(0,96 · DC, công suất AC tối đa). Hệ số thang đo cuối
cùng khớp trên ngày trung thực của train (bù tổn thất, bám bẩn, sai lệch vệ tinh trung bình).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib

GAMMA_PDC = -0.004       # hệ số nhiệt điển hình của module c-Si (%/°C)
INVERTER_EFF = 0.96
SLOT_HOURS = 0.25


def expected_slot_wh(slots: pd.DataFrame, dc_kw: float, ac_max_kw: float) -> pd.Series:
    """Wh AC kỳ vọng của từng slot, chỉ dùng cột của O4 (POA, nhiệt độ, gió NSRDB)."""
    poa = (slots["o4_poa_whm2"] / SLOT_HOURS).fillna(0.0)
    t_air = slots["nsrdb_temp_c"].fillna(slots["nsrdb_temp_c"].median())
    wind = slots["wind_ms"].fillna(1.0)
    t_cell = pvlib.temperature.faiman(poa, t_air, wind)
    pdc = pvlib.pvsystem.pvwatts_dc(poa, t_cell, dc_kw * 1000.0, GAMMA_PDC)
    pac = np.minimum(np.clip(pdc * INVERTER_EFF, 0, None), ac_max_kw * 1000.0)
    return pd.Series(pac * SLOT_HOURS, index=slots.index, name="pv_wh")


def expected_day_wh(slots: pd.DataFrame, dc_kw: float, ac_max_kw: float) -> pd.Series:
    return expected_slot_wh(slots, dc_kw, ac_max_kw).groupby(slots["day"]).sum().rename("pv_wh")


def fit_scale(pv_day: pd.Series, y_day: pd.Series, train_days: list[int]) -> float:
    """Hệ số thang đo = trung vị (sản lượng công tơ / PVWatts) trên ngày train."""
    r = (y_day.reindex(train_days) / pv_day.reindex(train_days)).replace([np.inf, -np.inf], np.nan).dropna()
    return float(r.median())
