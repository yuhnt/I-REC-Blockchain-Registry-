"""Dataset cho 4 oracle, theo slot 15 phút và theo ngày, trên các ngày hợp lệ (SPEC mục 2–3, 5).

Chạy: python -m rec.data.dataset   (cần chạy `python -m rec.data.days` trước)
Ghi artifacts/slots.parquet (một dòng mỗi slot) và artifacts/days.parquet (một dòng mỗi ngày).

Quy ước đơn vị: O1, O2 là Wh của slot (kW trung bình × 0,25 h); O3, O4 là Wh/m² của slot.
Giá trị âm (công tơ nhận điện ban đêm, nhiễu cảm biến) bị cắt về 0; slot thiếu giữ NaN, không điền 0.
"""
from __future__ import annotations

import sys
from typing import Any

import numpy as np
import pandas as pd

from rec import config
from rec.data import nsrdb, pvdaq
from rec.timeutil import day_date, slot_days

WH_PER_KW_SLOT = 250.0  # 1 kW trong 15 phút = 250 Wh
SLOT_HOURS = 0.25
INVERTERS = [f"inv{i:02d}" for i in range(1, 25)]


def _nonneg(s: pd.Series | pd.DataFrame):
    return s.clip(lower=0)


def build_slots(df15: pd.DataFrame, site_temp: pd.Series, nsrdb15: pd.DataFrame, zenith: pd.Series,
                valid_days: set[int], devices: dict[str, list[int]]) -> pd.DataFrame:
    """Một dòng mỗi slot của các ngày hợp lệ, chỉ mục UTC nhãn cuối kỳ."""
    days = slot_days(df15.index)
    keep = np.isin(days, list(valid_days))
    df15, days = df15[keep], days[keep]
    idx = df15.index
    inv = _nonneg(df15[INVERTERS])
    n = nsrdb15.reindex(idx)

    out = pd.DataFrame(index=idx)
    out["day"] = days
    out["slot"] = out.groupby("day").cumcount()
    out["o1_wh"] = _nonneg(df15["meter"]) * WH_PER_KW_SLOT
    out["o2_wh"] = inv.sum(axis=1, min_count=len(INVERTERS)) * WH_PER_KW_SLOT
    for name, members in devices.items():
        cols = [f"inv{i:02d}" for i in members]
        out[f"wh_{name}"] = inv[cols].sum(axis=1, min_count=len(cols)) * WH_PER_KW_SLOT
    out["o3_poa_whm2"] = _nonneg(df15["poa"]) * SLOT_HOURS
    out["site_temp_c"] = site_temp.reindex(idx)
    out["o4_poa_whm2"] = n["o4_poa"] * SLOT_HOURS
    out["ghi_whm2"] = n["ghi"] * SLOT_HOURS
    out["ghi_clearsky_whm2"] = n["ghi_clearsky"] * SLOT_HOURS
    out["nsrdb_temp_c"] = n["nsrdb_temp_c"]
    out["wind_ms"] = n["wind_ms"]
    out["zenith"] = zenith.reindex(idx)
    out["sun"] = out["zenith"] < 90
    return out


def outage_slots(df15: pd.DataFrame, slots: pd.DataFrame, rule: dict[str, Any]) -> pd.Series:
    """Mỗi ngày: số slot ban ngày nhiều nhất mà một inverter ngừng phát trong khi các inverter khác vẫn phát."""
    sun = slots[slots["sun"]]
    inv = df15.loc[sun.index, INVERTERS]
    others_on = inv.median(axis=1) > rule["others_median_kw"]
    off = inv.lt(rule["off_kw"]).mul(others_on, axis=0)
    return off.groupby(sun["day"].to_numpy()).sum().max(axis=1)


def build_days(slots: pd.DataFrame, days: pd.DataFrame, outage: pd.Series, clip_poa_wm2: float,
               day_types: dict[str, dict[str, float]], outage_rule: dict[str, Any]) -> pd.DataFrame:
    """Một dòng mỗi ngày hợp lệ: sản lượng thật, giá trị ngày của 4 oracle, đặc trưng O4, loại ngày, cờ sự cố."""
    g = slots.groupby("day")
    sun = slots[slots["sun"]]
    gs = sun.groupby("day")
    d = days.set_index("day")[["date", "split"]].copy()

    d["y_wh"] = g["o1_wh"].sum(min_count=1)  # sản lượng thật tại công tơ (ground truth)
    d["o2_wh"] = g["o2_wh"].sum(min_count=1)
    d["o3_whm2"] = g["o3_poa_whm2"].sum(min_count=1)
    d["o4_whm2"] = g["o4_poa_whm2"].sum(min_count=1)
    d["max_slot_o1_wh"] = g["o1_wh"].max()
    for name in [c for c in slots if c.startswith("wh_")]:
        d[name] = g[name].sum(min_count=1)

    d["sun_slots"] = gs.size()
    for col, oracle in (("o1_wh", "o1"), ("o2_wh", "o2"), ("o3_poa_whm2", "o3"), ("o4_poa_whm2", "o4")):
        d[f"present_{oracle}"] = gs[col].count()

    # Đặc trưng của mô hình AI (configs/features.yaml): chỉ từ O4 và thông số tĩnh.
    d["poa_energy_nsrdb_whm2"] = d["o4_whm2"]
    d["clearsky_index"] = g["ghi_whm2"].sum() / g["ghi_clearsky_whm2"].sum().replace(0, np.nan)
    d["temp_mean_c"] = gs["nsrdb_temp_c"].mean()
    d["temp_max_c"] = g["nsrdb_temp_c"].max()
    d["wind_mean_ms"] = gs["wind_ms"].mean()
    clipping = (sun["o4_poa_whm2"] / SLOT_HOURS) >= clip_poa_wm2
    d["poa_clip_hours"] = clipping.groupby(sun["day"]).sum() * SLOT_HOURS
    doy = pd.to_datetime(d["date"]).dt.dayofyear.to_numpy()
    d["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    d["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    d["site_temp_mean_c"] = gs["site_temp_c"].mean()
    csi = d["clearsky_index"]
    d["day_type"] = np.select(
        [csi >= day_types["clear"]["min"], csi >= day_types["partly"]["min"]], ["clear", "partly"], "cloudy")
    d["max_off_slots"] = outage.reindex(d.index).fillna(0).astype(int)
    d["outage"] = d["max_off_slots"] >= outage_rule["min_slots"]
    return d.reset_index()


def main() -> int:
    split = config.load("split")
    scenarios = config.load("scenarios")
    pv_dir = config.resolve_path("pvdaq_2107")
    artifacts = config.resolve_path("artifacts")
    meta = pvdaq.read_metadata(pv_dir)

    path15 = artifacts / "p2107_15m.parquet"
    if path15.exists():
        df15 = pd.read_parquet(path15)
    else:
        df15 = pvdaq.load_15m(pv_dir, str(split["range"]["start"]), str(split["range"]["end"]),
                              split["valid_day"]["min_samples_per_slot"])
    days = pd.read_csv(config.ROOT / split["days_file"])

    n = nsrdb.read_nsrdb(config.resolve_path("nsrdb"))
    poa = nsrdb.poa_global(n, meta["latitude"], meta["longitude"], meta["tilt"], meta["azimuth"])
    n15 = nsrdb.to_slots(n, poa)
    zenith = nsrdb.solar_zenith(df15.index, meta["latitude"], meta["longitude"])
    site_temp = pvdaq.read_site_temperature(pv_dir)

    plant = scenarios["plant"]
    slots = build_slots(df15, site_temp, n15, zenith, set(days["day"]), plant["devices"])
    rule = scenarios["inverter_outage"]
    outage = outage_slots(df15, slots, rule)
    # Bức xạ ứng với clipping: công suất AC tối đa / công suất DC × 1000 W/m² (bỏ qua tổn thất và nhiệt độ).
    ac_kw = plant["inverter_max_ac_kw"] * len(INVERTERS)
    clip_poa = ac_kw / meta["dc_kw"] * 1000
    out = build_days(slots, days, outage, clip_poa, scenarios["day_types"], rule)

    slots.to_parquet(artifacts / "slots.parquet")
    out.to_parquet(artifacts / "days.parquet", index=False)

    print("so slot:", len(slots), "| so ngay:", len(out))
    print("loai ngay theo split:", out.groupby(["split", "day_type"]).size().unstack(fill_value=0).to_dict("index"))
    ratio = (out["y_wh"] / out["o2_wh"]).median()
    print(f"cong to / tong inverter (trung vi): {ratio:.4f}")
    cov = {o: float((out[f"present_{o}"] / out["sun_slots"]).median()) for o in ("o1", "o2", "o3", "o4")}
    print("do phu ban ngay (trung vi):", {k: round(v, 3) for k, v in cov.items()})
    print(f"nguong clipping POA: {clip_poa:.0f} W/m2 | ngay co inverter ngung phat: {int(out['outage'].sum())}"
          f" / {len(out)}")
    print("ngay dau, ngay cuoi:", day_date(int(out['day'].min())), day_date(int(out['day'].max())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
