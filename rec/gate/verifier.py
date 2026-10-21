"""Verifier của issuer: chạy lớp B trên 4 báo cáo của một lô và ký `Verdict` (FLOW.md mục 3–4).

Tham số và ngưỡng đọc từ bản đã khóa `artifacts/model/<biến thể>/` (`layer_b.json`, `models.pkl`), không khớp lại.
Cờ được tính bằng đúng các hàm mà mô phỏng off-chain dùng (`rec.checks.consistency`, `rec.gate.sim`), nên test
parity chỉ còn phải kiểm phần contract.
"""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from eth_utils import keccak

from rec import config
from rec.checks.consistency import STATS, VARIANTS, ConsistencyModel, coverage, stats
from rec.data import pvdaq
from rec.gate.sim import CHECKED_ORACLES, PROFILES, Profile, o1_report
from rec.generator.common import INVERTER_MAX_W
from rec.model import ai
from rec.physics.pvwatts import expected_day_wh
from rec.schema import Flag, OracleId

CEILING_BASE = {"B2": "pv", "Proposed": "ai", "A2": "ai_linear"}  # A1 cần O3 của ca, không dùng cho verifier


@dataclass
class Verdict:
    flags: int
    ceiling_wh: int
    sun_slots: int
    reasons: dict
    model_hash: bytes


class Verifier:
    def __init__(self, profile: str = "Proposed", variant: str = "prereg", q_ceiling: float = 0.04,
                 artifacts: Path | None = None):
        if profile not in CEILING_BASE and profile != "B1":
            raise ValueError(f"verifier không hỗ trợ cấu hình {profile}")
        artifacts = artifacts or config.resolve_path("artifacts")
        mdir = artifacts / "model" / variant
        raw = (mdir / "layer_b.json").read_bytes()
        params = json.loads(raw)
        self.profile: Profile = PROFILES[profile]
        self.variant, self.q = variant, q_ceiling
        self.window = VARIANTS[variant]
        self.cons = ConsistencyModel(**params["consistency"])
        self.tau_cons = {k: (np.nan if v is None else float(v)) for k, v in params["tau_consistency"].items()}
        self.min_cov = config.load("thresholds")["completeness"]["min_daytime_coverage"]
        self.tau_ceiling = params["tau_ceiling"].get(f"{profile}@{q_ceiling}") if self.profile.ceiling else None
        self.base: dict[int, float] = {}
        if self.profile.ceiling:
            self.base = self._bases(artifacts, params, pickle.loads((mdir / "models.pkl").read_bytes()), profile)
        tag = json.dumps({"profile": profile, "variant": variant, "q": q_ceiling}, sort_keys=True).encode()
        self.model_hash = keccak(raw + (mdir / "models.pkl").read_bytes() + tag)

    def _bases(self, artifacts: Path, params: dict, models: dict, profile: str) -> dict[int, float]:
        days = pd.read_parquet(artifacts / "days.parquet").set_index("day")
        kind = CEILING_BASE[profile]
        if kind == "pv":
            slots = pd.read_parquet(artifacts / "slots.parquet")
            meta = pvdaq.read_metadata(config.resolve_path("pvdaq_2107"))
            cap_w = INVERTER_MAX_W * sum(len(v) for v in config.load("scenarios")["plant"]["devices"].values())
            base = params["pv_scale"] * expected_day_wh(slots, meta["dc_kw"], cap_w / 1000)
            return {int(d): float(v) for d, v in base.items()}
        pred = ai.predict(models[kind], ai.features(days))
        return {int(d): float(v) for d, v in zip(days.index, pred)}

    def evaluate(self, day: int, series: dict[OracleId, np.ndarray], sun: np.ndarray, temp: np.ndarray) -> Verdict:
        """Ba bước của lớp B theo cấu hình (SPEC mục 6.2). B1 chỉ đặt sunSlots."""
        o1_day, _ = o1_report(series[OracleId.O1])
        flags, reasons, ceiling = 0, {}, 0
        if self.profile.completeness:
            cov = coverage({o: series[o] for o in CHECKED_ORACLES}, sun)
            reasons["coverage"] = cov
            if min(cov.values()) < self.min_cov:
                flags |= int(Flag.MISSING_REPORT)
        if self.profile.consistency:
            st = stats(series, sun, temp, self.cons, self.window)
            reasons["consistency"] = {k: (None if np.isnan(v) else v) for k, v in st.items()}
            if any(st[s] > self.tau_cons[s] for s in STATS):  # NaN so sánh ra False
                flags |= int(Flag.INCONSISTENT)
        if self.profile.ceiling:
            limit = self.base[day] * (1 + self.tau_ceiling)
            ceiling = int(limit)
            reasons["ceiling"] = {"base_wh": self.base[day], "tau": self.tau_ceiling, "o1_wh": o1_day}
            if o1_day > limit:
                flags |= int(Flag.OVER_CEILING)
        reasons.update(profile=self.profile.name, variant=self.variant, q_ceiling=self.q, flags=flags)
        return Verdict(flags, ceiling, int(sun.sum()), reasons, self.model_hash)
