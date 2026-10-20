"""Đọc PVDAQ hệ 2107 về slot 15 phút, nhãn cuối kỳ (chuyển từ analysis/trackA_01_prep.py).

PVDAQ ghi giờ địa phương dạng naive. Các bước gom slot làm trên giờ naive như bản sơ bộ,
rồi mới gắn múi giờ nhà máy và đổi sang UTC; giờ lặp lúc đổi về giờ chuẩn bị loại.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from rec.timeutil import localize_plant

ELECTRICAL = "2107_electrical_data_v1.csv"
METER = "2107_meter_15m_data.csv"
IRRADIANCE = "2107_irradiance_data.csv"
ENVIRONMENT = "2107_environment_data.csv"
METADATA = "2107_system_metadata.json"


def read_metadata(directory: Path) -> dict[str, float]:
    """Tọa độ, góc nghiêng, hướng và công suất DC của nhà máy, lấy từ metadata của PVDAQ."""
    m = json.loads((directory / METADATA).read_text(encoding="utf-8"))
    mount = next(iter(m["Mount"].values()))
    return {
        "latitude": float(m["Site"]["latitude"]),
        "longitude": float(m["Site"]["longitude"]),
        "tilt": float(mount["tilt"]),
        "azimuth": float(mount["azimuth"]),
        "dc_kw": float(m["System"]["power(kW DC)"]),
    }


def read_site_temperature(directory: Path) -> pd.Series:
    """Nhiệt độ không khí tại chỗ (°C), trung bình 15 phút, chỉ mục UTC nhãn cuối kỳ.

    Cảm biến ghi bằng °F (đã kiểm: sau khi đổi, lệch NSRDB trung vị 0,8 °C).
    """
    e = pd.read_csv(directory / ENVIRONMENT, parse_dates=["measured_on"]).set_index("measured_on")
    e = e[~e.index.duplicated()].sort_index()
    t = ((e.iloc[:, 0] - 32) / 1.8).rename("site_temp_c")
    t = t.resample("15min", label="right", closed="right").mean()
    idx = localize_plant(t.index)
    keep = idx.notna()
    t = t[keep]
    t.index = idx[keep].tz_convert("UTC")
    return t

_INV_AC_POWER = re.compile(r"inv_(\d\d)_ac_power_")


def _to_slots(df: pd.DataFrame) -> pd.core.resample.Resampler:
    return df.resample("15min", label="right", closed="right")


def read_inverters(directory: Path, min_samples: int = 3) -> pd.DataFrame:
    """Công suất AC trung bình (kW) của 24 inverter; slot thiếu mẫu 5 phút thành NaN."""
    path = directory / ELECTRICAL
    header = pd.read_csv(path, nrows=0).columns
    cols = {c: f"inv{m.group(1)}" for c in header if (m := _INV_AC_POWER.match(c))}
    parts = []
    for chunk in pd.read_csv(path, usecols=["measured_on", *cols], parse_dates=["measured_on"],
                             dtype={c: "float32" for c in cols}, chunksize=400_000):
        parts.append(chunk.rename(columns=cols).set_index("measured_on"))
    inv5 = pd.concat(parts).sort_index()
    inv5 = inv5[~inv5.index.duplicated()]
    inv15 = _to_slots(inv5).mean()
    return inv15.where(_to_slots(inv5).count() >= min_samples)


def read_meter(directory: Path) -> pd.Series:
    """Công suất trung bình 15 phút (kW) tại công tơ; nhãn gốc đầu kỳ nên dịch +15 phút."""
    m = pd.read_csv(directory / METER, parse_dates=["measured_on"]).set_index("measured_on")
    m.index = m.index + pd.Timedelta("15min")
    s = m.iloc[:, 0].rename("meter").astype("float32")
    return s[~s.index.duplicated()]


def read_poa(directory: Path) -> pd.Series:
    """Bức xạ POA tại chỗ (W/m²), trung bình 15 phút."""
    p = pd.read_csv(directory / IRRADIANCE, parse_dates=["measured_on"]).set_index("measured_on")
    p = p[~p.index.duplicated()]
    return _to_slots(p.iloc[:, 0].rename("poa")).mean().astype("float32")


def load_15m(directory: Path, start: str, end: str, min_samples: int = 3) -> pd.DataFrame:
    """Bảng slot 15 phút (chỉ mục UTC, nhãn cuối kỳ): inv01–inv24, meter (kW), poa (W/m²)."""
    df = read_inverters(directory, min_samples).join(read_meter(directory), how="outer")
    df = df.join(read_poa(directory), how="outer").loc[start:f"{end} 23:59"]
    idx = localize_plant(df.index)
    keep = idx.notna()
    df = df[keep]
    df.index = idx[keep].tz_convert("UTC")
    return df
