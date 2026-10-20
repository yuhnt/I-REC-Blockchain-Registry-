"""Phần dùng chung của generator: dữ liệu theo ngày, đồng hồ mô phỏng, chia sản lượng, dựng báo cáo oracle."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from rec import config
from rec.oracles.encoding import MISSING, data_root, to_ints
from rec.schema import OracleId, OracleReport
from rec.timeutil import day_bounds_utc

ORACLE_COLUMNS = {OracleId.O1: "o1_wh", OracleId.O2: "o2_wh", OracleId.O3: "o3_poa_whm2", OracleId.O4: "o4_poa_whm2"}
INVERTER_MAX_W = 30_000

# Đồng hồ mô phỏng (SPEC mục 1): báo cáo của ngày d lúc 00:30, bằng chứng của lô 00:45, yêu cầu 01:00 ngày d + 1.
REPORT_AT = 30 * 60
EVIDENCE_AT = 45 * 60
REQUEST_AT = 60 * 60
NOON = 12 * 3600


def local_t(day: int, seconds: int = 0) -> int:
    """Giây UTC của thời điểm `seconds` sau nửa đêm địa phương của ngày `day`."""
    start, _ = day_bounds_utc(day)
    return int(start.timestamp()) + seconds


@dataclass
class DayData:
    """Chuỗi 15 phút của một ngày (mọi oracle ở mức CP) và sản lượng theo khối."""

    day: int
    series: dict[OracleId, np.ndarray]   # float, NaN = slot thiếu
    sun: np.ndarray                      # bool, slot ban ngày theo vị trí mặt trời
    block_wh: dict[str, float]           # sản lượng inverter của từng khối trong ngày
    y_wh: int                            # sản lượng thật tại công tơ (tổng các slot đã làm tròn)
    day_type: str
    outage: bool


def load_days(artifacts: Path | None = None) -> tuple[pd.DataFrame, dict[int, DayData]]:
    artifacts = artifacts or config.resolve_path("artifacts")
    days = pd.read_parquet(artifacts / "days.parquet")
    slots = pd.read_parquet(artifacts / "slots.parquet")
    blocks = [c for c in days if c.startswith("wh_")]
    data = {}
    for d, g in slots.groupby("day", sort=True):
        row = days.loc[days["day"] == d].iloc[0]
        series = {o: g[c].to_numpy(dtype=float) for o, c in ORACLE_COLUMNS.items()}
        o1 = to_ints(series[OracleId.O1])
        data[int(d)] = DayData(
            day=int(d), series=series, sun=g["sun"].to_numpy(dtype=bool),
            block_wh={b[3:]: float(row[b]) for b in blocks},
            y_wh=sum(v for v in o1 if v != MISSING), day_type=str(row["day_type"]), outage=bool(row["outage"]))
    return days, data


def allocate(total_wh: int, weights: dict[str, float]) -> dict[str, int]:
    """Chia số công tơ cho các thiết bị theo tỷ lệ sản lượng inverter, làm tròn xuống: tổng không vượt `total_wh`."""
    clean = {k: (w if np.isfinite(w) and w > 0 else 0.0) for k, w in weights.items()}
    s = sum(clean.values())
    if total_wh <= 0 or s <= 0:
        return {k: 0 for k in weights}
    return {k: int(total_wh * w // s) for k, w in clean.items()}


def report(oracle: OracleId, cp_id: str, day: int, values: np.ndarray, sun: np.ndarray) -> OracleReport:
    """Báo cáo ngày của một oracle từ chuỗi 15 phút (giá trị đã làm tròn, slot thiếu = MISSING)."""
    ints = to_ints(values)
    present = [v for v in ints if v != MISSING]
    in_sun = sum(1 for v, s in zip(ints, sun) if s and v != MISSING)
    return OracleReport(oracle=oracle, subject=cp_id, day=day, wh_day=sum(present),
                        max_slot_wh=max(present, default=0), slots_present=in_sun, data_root=data_root(values))


def reports_for(dd: DayData, cp_id: str, series: dict[OracleId, np.ndarray] | None = None) -> list[OracleReport]:
    series = series or dd.series
    return [report(o, cp_id, dd.day, series[o], dd.sun) for o in OracleId]
