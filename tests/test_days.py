import copy

import numpy as np
import pandas as pd

from rec import config
from rec.data.days import valid_days
from rec.timeutil import PLANT_TZ


def _days(n: int) -> pd.DataFrame:
    """n ngày từ 01/07/2021 (val), mỗi ngày 48 slot ban ngày từ 06:15 đến 18:00 giờ địa phương."""
    start = pd.Timestamp("2021-07-01 00:15", tz=PLANT_TZ)
    end = pd.Timestamp("2021-07-01", tz=PLANT_TZ) + pd.Timedelta(days=n)
    idx = pd.date_range(start, end, freq="15min").tz_convert("UTC")
    local = idx.tz_convert(PLANT_TZ)
    sunny = (local.hour + local.minute / 60 > 6) & (local.hour + local.minute / 60 <= 18)
    df = pd.DataFrame({f"inv{i:02d}": np.where(sunny, 20.0, 0.0) for i in range(1, 25)}, index=idx)
    df["meter"] = np.where(sunny, 470.0, 0.0)
    df["poa"] = np.where(sunny, 800.0, 0.0)
    return df


def _split_eta_on_val() -> dict:
    s = copy.deepcopy(config.load("split"))
    s["data_fault"]["eta_split"] = "val"  # dữ liệu giả chỉ có ngày 2021
    return s


def _on_day(df: pd.DataFrame, day: int) -> np.ndarray:
    return (df.index.tz_convert(PLANT_TZ).day == day) & (df["poa"] > 20).to_numpy()


def test_valid_days_requires_coverage_on_every_channel():
    df = _days(2)
    df.loc[_on_day(df, 2), "inv07"] = np.nan  # ngày 02/07 mất trọn một inverter
    days, dropped = valid_days(df, _split_eta_on_val())
    assert days["date"].tolist() == ["2021-07-01"]
    assert days["split"].tolist() == ["val"]
    assert days["daytime_slots"].tolist() == [48]
    assert dropped.empty


def test_small_gap_within_tolerance_is_kept():
    df = _days(2)
    df.loc[df.index[df["poa"] > 20][:2], "meter"] = np.nan  # thiếu 2/48 slot ≈ 4% < 5%
    days, _ = valid_days(df, _split_eta_on_val())
    assert len(days) == 2


def test_logger_reporting_zero_is_dropped():
    df = _days(4)
    df.loc[_on_day(df, 2), [f"inv{i:02d}" for i in range(1, 25)]] = 0.0  # bộ ghi inverter báo 0 cả ngày
    df.loc[_on_day(df, 3), "meter"] = 1000.0  # công tơ lệch hơn gấp đôi tổng inverter
    days, dropped = valid_days(df, _split_eta_on_val())
    assert days["date"].tolist() == ["2021-07-01", "2021-07-04"]
    assert dict(zip(dropped["date"], dropped["reason"])) == {
        "2021-07-02": "zero_source", "2021-07-03": "meter_inverter_dev"}
