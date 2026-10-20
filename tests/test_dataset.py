import numpy as np
import pandas as pd

from rec import config
from rec.data.dataset import INVERTERS, build_days, build_slots, outage_slots
from rec.timeutil import PLANT_TZ, day_number

DEVICES = config.load("scenarios")["plant"]["devices"]
RULE = config.load("scenarios")["inverter_outage"]
DAY_TYPES = config.load("scenarios")["day_types"]


def _inputs(n_days: int = 2):
    start = pd.Timestamp("2021-07-01 00:15", tz=PLANT_TZ)
    end = pd.Timestamp("2021-07-01", tz=PLANT_TZ) + pd.Timedelta(days=n_days)
    idx = pd.date_range(start, end, freq="15min").tz_convert("UTC")
    local = idx.tz_convert(PLANT_TZ)
    hour = local.hour + local.minute / 60
    sunny = (hour > 6) & (hour <= 18)
    df15 = pd.DataFrame({c: np.where(sunny, 20.0, -0.1) for c in INVERTERS}, index=idx)
    df15["meter"] = np.where(sunny, 472.0, -0.5)  # ban đêm công tơ nhận điện nhỏ
    df15["poa"] = np.where(sunny, 800.0, 0.0)
    n15 = pd.DataFrame({"o4_poa": np.where(sunny, 820.0, 0.0), "ghi": np.where(sunny, 700.0, 0.0),
                        "ghi_clearsky": np.where(sunny, 760.0, 0.0), "nsrdb_temp_c": 25.0, "wind_ms": 2.0},
                       index=idx)
    zenith = pd.Series(np.where(sunny, 40.0, 100.0), index=idx)
    site_temp = pd.Series(24.0, index=idx)
    days = pd.DataFrame({"day": [day_number(pd.Timestamp("2021-07-01").date()) + k for k in range(n_days)],
                         "date": [f"2021-07-0{k + 1}" for k in range(n_days)], "split": "val"})
    return df15, site_temp, n15, zenith, days


def test_units_and_clipping_of_negative_values():
    df15, site_temp, n15, zenith, days = _inputs()
    slots = build_slots(df15, site_temp, n15, zenith, set(days["day"]), DEVICES)
    day_slots = slots[slots["sun"]]
    assert (day_slots["o1_wh"] == 472.0 * 250).all()
    assert (day_slots["o2_wh"] == 24 * 20.0 * 250).all()
    assert (day_slots["wh_B1"] == 4 * 20.0 * 250).all()
    assert (day_slots["o3_poa_whm2"] == 800.0 * 0.25).all()
    assert (slots.loc[~slots["sun"], "o1_wh"] == 0).all()  # công tơ âm ban đêm bị cắt về 0
    assert slots.groupby("day")["slot"].max().tolist() == [95, 95]


def test_missing_inverter_makes_o2_slot_missing_not_zero():
    df15, site_temp, n15, zenith, days = _inputs()
    first_sun = df15.index[zenith.to_numpy() < 90][0]
    df15.loc[first_sun, "inv05"] = np.nan
    slots = build_slots(df15, site_temp, n15, zenith, set(days["day"]), DEVICES)
    assert np.isnan(slots.loc[first_sun, "o2_wh"])
    assert np.isnan(slots.loc[first_sun, "wh_B2"])
    assert slots.loc[first_sun, "wh_B1"] == 4 * 20.0 * 250


def test_days_table_features_and_outage():
    df15, site_temp, n15, zenith, days = _inputs()
    day2_sun = (df15.index.tz_convert(PLANT_TZ).day == 2) & (zenith.to_numpy() < 90)
    df15.loc[day2_sun, "inv07"] = 0.0  # ngày 02/07: inv07 ngừng phát cả ngày
    slots = build_slots(df15, site_temp, n15, zenith, set(days["day"]), DEVICES)
    out = build_days(slots, days, outage_slots(df15, slots, RULE), 806.0, DAY_TYPES, RULE)
    assert out["sun_slots"].tolist() == [48, 48]
    assert out["outage"].tolist() == [False, True]
    assert out["day_type"].tolist() == ["clear", "clear"]  # 700 / 760 ≈ 0,92
    assert out["poa_clip_hours"].tolist() == [12.0, 12.0]  # 820 W/m² ≥ 806 suốt 12 giờ nắng
    assert out["present_o1"].tolist() == [48, 48]
    assert out.loc[0, "y_wh"] == 48 * 472.0 * 250
