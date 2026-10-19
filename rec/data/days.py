"""Lọc ngày hợp lệ và chia train/val/test theo năm (SPEC.md mục 2).

Chạy: python -m rec.data.days
Ghi configs/days.csv và configs/days_dropped.csv (thuộc mốc 1),
cùng artifacts/p2107_15m.parquet (dùng lại ở giai đoạn 2).
"""
from __future__ import annotations

import sys
from typing import Any

import pandas as pd

from rec import config
from rec.data.pvdaq import load_15m
from rec.timeutil import day_date, slot_days


def _with_split(days: pd.Index, split: dict[str, Any]) -> pd.DataFrame:
    year_to_split = {y: name for name, years in split["splits"].items() for y in years}
    dates = [day_date(int(n)) for n in days]
    return pd.DataFrame({
        "day": days.astype(int),
        "date": [d.isoformat() for d in dates],
        "split": [year_to_split[d.year] for d in dates],
    })


def covered_days(df15: pd.DataFrame, split: dict[str, Any]) -> pd.Series:
    """Số slot ban ngày của mỗi ngày đủ độ phủ dữ liệu ở mọi kênh."""
    rule = split["valid_day"]
    daytime = df15[df15["poa"] > rule["daytime_poa_wm2"]]
    groups = daytime.groupby(slot_days(daytime.index))
    need = groups.size()
    coverage = groups.count().div(need, axis=0)
    ok = (coverage >= rule["min_coverage"]).all(axis=1) & (need >= rule["min_daytime_slots"])
    return need[ok]


def fault_days(df15: pd.DataFrame, days: pd.DataFrame, split: dict[str, Any]) -> pd.DataFrame:
    """Ngày lỗi dữ liệu rõ ràng trong `days`: một nguồn cả ngày ≤ 0, hoặc công tơ lệch tổng inverter quá ngưỡng."""
    rule = split["data_fault"]
    inv = [c for c in df15 if c.startswith("inv")]
    groups = df15.groupby(slot_days(df15.index))
    meter = (groups["meter"].sum() * 0.25).reindex(days["day"]).to_numpy()
    inverters = (groups[inv].sum().sum(axis=1) * 0.25).reindex(days["day"]).to_numpy()
    zero = (meter <= 0) | (inverters <= 0)
    ratio = pd.Series(meter, dtype=float).where(~zero) / pd.Series(inverters, dtype=float).where(~zero)
    base = ratio[(days["split"] == rule["eta_split"]).to_numpy()]
    eta = base[(base / base.median() - 1).abs() <= rule["max_meter_inverter_dev"]].median()
    dev = (ratio / eta - 1).to_numpy()
    bad = zero | (abs(dev) > rule["max_meter_inverter_dev"])
    out = days[bad].copy()
    out["meter_kwh"] = meter[bad].round(1)
    out["inverter_kwh"] = inverters[bad].round(1)
    out["reason"] = ["zero_source" if z else "meter_inverter_dev" for z in zero[bad]]
    return out


def valid_days(df15: pd.DataFrame, split: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(ngày hợp lệ, ngày bị loại vì lỗi dữ liệu). Ngày hợp lệ có cột day, date, split, daytime_slots."""
    need = covered_days(df15, split)
    days = _with_split(need.index, split)
    days["daytime_slots"] = need.to_numpy()
    dropped = fault_days(df15, days, split)
    return days[~days["day"].isin(dropped["day"])].reset_index(drop=True), dropped.reset_index(drop=True)


def main() -> int:
    split = config.load("split")
    df15 = load_15m(config.resolve_path("pvdaq_2107"), str(split["range"]["start"]),
                    str(split["range"]["end"]), split["valid_day"]["min_samples_per_slot"])
    days, dropped = valid_days(df15, split)

    counts = days["split"].value_counts().to_dict()
    counts["total"] = len(days)
    print("so ngay hop le:", counts)
    print("so ngay bi loai vi loi du lieu:", dropped["split"].value_counts().to_dict(),
          "| ly do:", dropped["reason"].value_counts().to_dict())
    mismatch = {k: (counts.get(k, 0), v) for k, v in split["expected_days"].items() if counts.get(k, 0) != v}
    if mismatch:
        print("LECH so voi expected_days (thuc te, ky vong):", mismatch)

    days.to_csv(config.ROOT / split["days_file"], index=False)
    dropped.to_csv(config.ROOT / split["data_fault"]["dropped_file"], index=False)
    artifacts = config.resolve_path("artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)
    df15.to_parquet(artifacts / "p2107_15m.parquet")
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
