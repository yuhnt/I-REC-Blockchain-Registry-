"""Đọc NSRDB GOES CONUS v4 (5 phút, UTC) và tính bức xạ trên mặt tấm pin bằng pvlib (nguồn của O4)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pvlib

COLUMNS = ["GHI", "DNI", "DHI", "Clearsky GHI", "Temperature", "Wind Speed", "Surface Albedo"]


def read_nsrdb(directory: Path) -> pd.DataFrame:
    files = sorted(directory.glob("nsrdb_conus_v4_2107_*_5min.csv"))
    if not files:
        raise FileNotFoundError(f"không thấy file NSRDB trong {directory}")
    n = pd.concat([pd.read_csv(f, skiprows=2) for f in files])
    n.index = pd.to_datetime(n[["Year", "Month", "Day", "Hour", "Minute"]]).dt.tz_localize("UTC")
    n = n[~n.index.duplicated()].sort_index()
    return n[COLUMNS]


def poa_global(n: pd.DataFrame, latitude: float, longitude: float, tilt: float, azimuth: float) -> pd.Series:
    """Bức xạ tổng trên mặt phẳng tấm pin (W/m²) từ GHI, DNI, DHI của NSRDB."""
    sp = pvlib.solarposition.get_solarposition(n.index, latitude, longitude)
    poa = pvlib.irradiance.get_total_irradiance(tilt, azimuth, sp["apparent_zenith"], sp["azimuth"],
                                                n["DNI"], n["GHI"], n["DHI"], albedo=n["Surface Albedo"])
    return poa["poa_global"].clip(lower=0).rename("poa")


def to_slots(n: pd.DataFrame, poa: pd.Series) -> pd.DataFrame:
    """Gom về slot 15 phút nhãn cuối kỳ (trung bình các mẫu 5 phút trong (t − 15 phút, t])."""
    df = pd.DataFrame({
        "o4_poa": poa,
        "ghi": n["GHI"],
        "ghi_clearsky": n["Clearsky GHI"],
        "nsrdb_temp_c": n["Temperature"],
        "wind_ms": n["Wind Speed"],
    })
    return df.resample("15min", label="right", closed="right").mean()


def solar_zenith(slot_ends: pd.DatetimeIndex, latitude: float, longitude: float) -> pd.Series:
    """Góc thiên đỉnh tại giữa mỗi slot; < 90° nghĩa là slot ban ngày (SPEC mục 1)."""
    mid = slot_ends - pd.Timedelta("7min 30s")
    sp = pvlib.solarposition.get_solarposition(mid, latitude, longitude)
    return pd.Series(sp["zenith"].to_numpy(), index=slot_ends, name="zenith")
