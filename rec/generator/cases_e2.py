"""Các ca của E2 (chế độ R2): M1, M2, M3, D4b, D5 và lô trung thực (SPEC mục 4.1).

Generator chỉ ghi **bảng ca** (kịch bản, tham số, seed, ngày). Chuỗi đã bị sửa được dựng lại bằng
`apply_case`, một hàm tất định theo (seed, case_id), nên runner và metrics luôn thấy cùng một dữ liệu.
Bảng ca, nhãn và mã generator cùng được hash ở mốc 2.

Ở R2 kẻ gian giữ khóa của k nguồn tại chỗ, luôn gồm O1: k = 1 {O1}, k = 2 {O1, O2}, k = 3 {O1, O2, O3}.
"""
from __future__ import annotations

import itertools
import json
import zlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from rec.generator.common import DayData, allocate
from rec.oracles.encoding import MISSING, to_ints
from rec.schema import LabelKind, OracleId

SOURCES = {1: (OracleId.O1,), 2: (OracleId.O1, OracleId.O2), 3: (OracleId.O1, OracleId.O2, OracleId.O3)}
ISSUER_A, ISSUER_B = "issuerA", "issuerB"
FAULT_ORACLES = {"O1": OracleId.O1, "O2": OracleId.O2, "O3": OracleId.O3}


@dataclass
class Applied:
    series: dict[OracleId, np.ndarray]
    requests: list[tuple[str, str, int]]  # (issuer, device_id, wh)
    excess_wh: int                         # phần xin vượt sản lượng thật tại (CP, ngày)
    source_day: int | None = None


def _neg_type(dd: DayData) -> str:
    if dd.outage or dd.day_type == "cloudy":
        return "L5"
    return "L2" if dd.day_type == "clear" else "honest"


def _d5_target(dd: DayData, kind: str) -> bool:
    return dd.day_type == "cloudy" if kind == "cloudy" else (dd.day_type == "clear" and dd.outage)


def _d5_sources(day: int, data: dict[int, DayData]) -> list[int]:
    """Ngày đã phát hành trước ngày đích, sản lượng cao hơn, cùng số slot (ngày đổi giờ có 92/100 slot)."""
    dd = data[day]
    n = len(dd.sun)
    return [x for x in sorted(data) if x < day and data[x].y_wh > dd.y_wh and len(data[x].sun) == n]


def build_cases(test_days: list[int], data: dict[int, DayData], attacks: dict, seeds: list[int]) -> pd.DataFrame:
    """Bảng ca: lô trung thực (một lần) và mỗi tổ hợp kịch bản × tham số × seed × ngày đủ điều kiện."""
    rows = [{"case_id": f"H-{d}", "seed": 0, "day": d, "scenario": "honest", "params": "{}"} for d in test_days]

    def add(seed: int, scenario: str, params: dict, days: list[int]):
        tag = "-".join(str(v) for v in params.values())
        for d in days:
            rows.append({"case_id": f"s{seed}-{scenario}-{tag}-{d}", "seed": seed, "day": d,
                         "scenario": scenario, "params": json.dumps(params, sort_keys=True)})

    p = {name: attacks[name]["params"] for name in ("M1", "M2", "M3", "D4b", "D5")}
    for seed in seeds:
        for k, s, w in itertools.product(p["M1"]["k"], p["M1"]["s"], p["M1"]["window_min"]):
            add(seed, "M1", {"k": k, "s": s, "window_min": w}, test_days)
        for k, a in itertools.product(p["M2"]["k"], p["M2"]["alpha"]):
            add(seed, "M2", {"k": k, "alpha": a}, test_days)
        for o in p["M3"]["oracle"]:
            for fault in p["M3"]["fault"]:
                values = p["M3"]["shift_min"] if fault == "clock_shift" else p["M3"]["duration_h"]
                for v in values:
                    add(seed, "M3", {"oracle": o, "fault": fault, "amount": v}, test_days)
        for f, k in itertools.product(p["D4b"]["f"], p["D4b"]["k"]):
            add(seed, "D4b", {"f": f, "k": k}, test_days)
        for target, sigma, k in itertools.product(p["D5"]["target_day"], p["D5"]["sigma"], p["D5"]["k"]):
            eligible = [d for d in test_days if _d5_target(data[d], target) and _d5_sources(d, data)]
            add(seed, "D5", {"target_day": target, "sigma": sigma, "k": k}, eligible)
    return pd.DataFrame(rows)


def _rng(seed: int, case_id: str) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([seed, zlib.crc32(case_id.encode())]))


def _window(dd: DayData, slots: int, rng) -> np.ndarray:
    sun = np.flatnonzero(dd.sun)
    slots = min(slots, len(sun))
    start = int(rng.integers(len(sun) - slots + 1))
    return sun[start:start + slots]


def _o1_total(values: np.ndarray) -> int:
    return sum(v for v in to_ints(values) if v != MISSING)


def apply_case(row: dict, data: dict[int, DayData], devices: list[str]) -> Applied:
    """Dựng chuỗi 15 phút (đã bị sửa nếu là tấn công) và các yêu cầu phát hành của một ca."""
    dd = data[int(row["day"])]
    params = json.loads(row["params"]) if isinstance(row["params"], str) else row["params"]
    scenario = row["scenario"]
    rng = _rng(int(row["seed"]), row["case_id"])
    s = {o: v.copy() for o, v in dd.series.items()}
    source_day = None
    extra: list[tuple[str, str, int]] = []

    if scenario == "M1":
        idx = _window(dd, params["window_min"] // 15, rng)
        for o in SOURCES[params["k"]]:
            s[o][idx] *= params["s"]
    elif scenario == "M2":
        for o in SOURCES[params["k"]]:
            s[o] *= 1 + params["alpha"]
    elif scenario == "M3":
        o = FAULT_ORACLES[params["oracle"]]
        if params["fault"] == "clock_shift":
            n = params["amount"] // 15
            s[o] = np.concatenate([np.full(n, np.nan), s[o][:-n]])
        else:
            idx = _window(dd, params["amount"] * 4, rng)
            if params["fault"] == "missing":
                s[o][idx] = np.nan
            else:  # kẹt: lặp lại giá trị hợp lệ đầu tiên trong cửa sổ
                valid = s[o][idx][~np.isnan(s[o][idx])]
                if len(valid):
                    s[o][idx] = valid[0]
    elif scenario == "D4b":
        for o in SOURCES[params["k"]]:
            s[o] *= 1 + params["f"]
        m = max(1, round(len(devices) * params["f"]))
        true_shares = allocate(dd.y_wh, {b: dd.block_wh.get(b, 0.0) for b in devices})
        extra.append((ISSUER_B, f"XD4b-{m}", sum(true_shares[b] for b in devices[:m])))
    elif scenario == "D5":
        sources = _d5_sources(dd.day, data)
        source_day = sources[int(rng.integers(len(sources)))]
        src = data[source_day]
        for o in SOURCES[params["k"]]:
            noise = 1 + params["sigma"] * rng.standard_normal(len(src.sun))
            s[o] = np.clip(src.series[o] * noise, 0, None)
    elif scenario != "honest":
        raise ValueError(f"kịch bản E2 không xác định: {scenario}")

    if scenario == "D4b":
        base = allocate(dd.y_wh, {b: dd.block_wh.get(b, 0.0) for b in devices})
    else:
        base = allocate(_o1_total(s[OracleId.O1]), {b: dd.block_wh.get(b, 0.0) for b in devices})
    requests = [(ISSUER_A, b, wh) for b, wh in base.items() if wh > 0] + extra
    excess = max(0, sum(wh for _, _, wh in requests) - dd.y_wh)
    return Applied(s, requests, excess, source_day)


def labels_for(cases: pd.DataFrame, data: dict[int, DayData], devices: list[str]) -> pd.DataFrame:
    """Nhãn ẩn của từng ca: kịch bản, loại (honest / L / M / D), phần vượt sản lượng thật nếu được mint."""
    rows = []
    for row in cases.to_dict("records"):
        dd = data[int(row["day"])]
        scenario = row["scenario"]
        if scenario == "honest":
            neg = _neg_type(dd)
            kind = LabelKind.HONEST if neg == "honest" else LabelKind.L
            rows.append({"case_id": row["case_id"], "scenario": neg, "kind": kind.value, "excess_wh_true": 0,
                         "day_type": dd.day_type, "outage": dd.outage})
            continue
        applied = apply_case(row, data, devices)
        kind = LabelKind.D if scenario in ("D4b", "D5") else LabelKind.M
        rows.append({"case_id": row["case_id"], "scenario": scenario, "kind": kind.value,
                     "excess_wh_true": applied.excess_wh, "day_type": dd.day_type, "outage": dd.outage})
    return pd.DataFrame(rows)
