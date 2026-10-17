"""Quy ước thời gian của dự án (PLAN.md mục 3.1).

- Ngày là ngày địa phương của nhà máy, mã hóa thành số ngày kể từ 1970-01-01.
  Không dùng ngày UTC: ở California, sản lượng buổi chiều rơi sang ngày UTC hôm sau.
- Slot dài 15 phút, nhãn cuối kỳ: slot (23:45, 24:00] mang nhãn 00:00 nhưng thuộc ngày trước.
- Hàm nào nhận thời điểm đều đòi múi giờ tường minh; thời điểm "naive" bị từ chối.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# PVDAQ ghi giờ theo PST8PDT, cùng luật giờ mùa hè với America/Los_Angeles.
PLANT_TZ = ZoneInfo("America/Los_Angeles")
EPOCH = date(1970, 1, 1)
SLOT = timedelta(minutes=15)
SLOT_HOURS = 0.25

_EPOCH_TS = pd.Timestamp("1970-01-01")


def day_number(d: date) -> int:
    """Ngày lịch → số ngày kể từ 1970-01-01."""
    return (d - EPOCH).days


def day_date(n: int) -> date:
    """Số ngày → ngày lịch."""
    return EPOCH + timedelta(days=n)


def _require_aware(ts: datetime) -> None:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("thời điểm phải có múi giờ tường minh")


def local_day(ts: datetime) -> int:
    """Số ngày địa phương chứa thời điểm `ts`."""
    _require_aware(ts)
    return day_number(ts.astimezone(PLANT_TZ).date())


def slot_day(slot_end: datetime) -> int:
    """Số ngày địa phương của slot có nhãn cuối kỳ `slot_end`."""
    _require_aware(slot_end)
    return local_day(slot_end - SLOT)


def day_bounds_utc(n: int) -> tuple[datetime, datetime]:
    """Khoảng [nửa đêm địa phương, nửa đêm hôm sau) của ngày `n`, đổi sang UTC."""
    start = datetime.combine(day_date(n), time(0), tzinfo=PLANT_TZ)
    end = datetime.combine(day_date(n + 1), time(0), tzinfo=PLANT_TZ)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def slots_per_day(n: int) -> int:
    """96 slot thường ngày; 92 ngày chuyển sang giờ mùa hè, 100 ngày chuyển về."""
    start, end = day_bounds_utc(n)
    return (end - start) // SLOT


def slot_ends(n: int) -> list[datetime]:
    """Nhãn cuối kỳ (UTC) của mọi slot thuộc ngày `n`."""
    start, _ = day_bounds_utc(n)
    return [start + SLOT * (i + 1) for i in range(slots_per_day(n))]


def _require_aware_index(index: pd.DatetimeIndex) -> None:
    if index.tz is None:
        raise ValueError("DatetimeIndex phải có múi giờ tường minh")


def local_days(index: pd.DatetimeIndex) -> np.ndarray:
    """Bản vector hóa của `local_day`."""
    _require_aware_index(index)
    local = index.tz_convert(PLANT_TZ).normalize().tz_localize(None)
    return (local - _EPOCH_TS).days.to_numpy()


def slot_days(index: pd.DatetimeIndex) -> np.ndarray:
    """Bản vector hóa của `slot_day` cho chỉ mục nhãn cuối kỳ."""
    _require_aware_index(index)
    return local_days(index - pd.Timedelta(SLOT))


def localize_plant(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Gắn múi giờ nhà máy cho thời điểm naive của PVDAQ.

    Giờ lặp (đổi về giờ chuẩn) và giờ không tồn tại (sang giờ mùa hè) trở thành NaT,
    giống cách analysis/check_nsrdb_vs_pvdaq.py đã làm.
    """
    if index.tz is not None:
        raise ValueError("chỉ mục đã có múi giờ")
    return index.tz_localize(PLANT_TZ, ambiguous="NaT", nonexistent="NaT")
