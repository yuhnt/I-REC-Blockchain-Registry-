"""Khớp lớp B trên train và chọn ngưỡng trên val (SPEC mục 6.2); dùng chung cho E2 và các phân tích bổ sung.

Không đụng tới tập test: chỉ đọc ngày trung thực của train (khớp) và val (chọn ngưỡng).
"""
from __future__ import annotations

import pandas as pd

from rec import config
from rec.checks.consistency import STATS, fit
from rec.data import pvdaq
from rec.gate.sim import device_caps, lot_row
from rec.generator.common import INVERTER_MAX_W, load_days
from rec.model import ai
from rec.model.calibrate import ceiling_tau, consistency_thresholds
from rec.physics.pvwatts import expected_day_wh, fit_scale

SLOT_HOURS = 0.25
CEILING_BASE = {"B2": "pv", "Proposed": "ai", "A1": "ai_o3", "A2": "ai_linear"}
CTX_KEYS = ("thr", "devices", "caps", "cp_cap_w", "min_cov", "artifacts", "days_df", "data", "temps", "split", "cons",
        "pv_scale", "models", "base_day", "hs", "tau_cons", "q_cons", "cons_rate", "sweep", "tau_ceil", "ceil_rate")


def fit_and_calibrate(window) -> dict:
    """Khớp lớp B trên train và chọn ngưỡng trên val; không đụng tới tập test."""
    scen, thr = config.load("scenarios"), config.load("thresholds")
    plant = scen["plant"]
    devices = list(plant["devices"])
    caps = device_caps(plant["devices"], INVERTER_MAX_W)
    cp_cap_w = INVERTER_MAX_W * sum(len(v) for v in plant["devices"].values())
    min_cov = thr["completeness"]["min_daytime_coverage"]
    artifacts = config.resolve_path("artifacts")

    days_df, data = load_days()
    days_df = days_df.set_index("day")
    slots = pd.read_parquet(artifacts / "slots.parquet")
    temps = {int(d): g["site_temp_c"].to_numpy(float) for d, g in slots.groupby("day", sort=True)}
    meta = pvdaq.read_metadata(config.resolve_path("pvdaq_2107"))
    split = {name: sorted(int(d) for d in days_df.index[days_df["split"] == name]) for name in ("train", "val", "test")}
    y = pd.Series({d: data[d].y_wh for d in data}, dtype=float)

    # 1. Khớp trên train (chỉ ngày trung thực).
    cons = fit({d: data[d].series for d in data}, {d: data[d].sun for d in data}, temps, split["train"],
               cp_cap_w * SLOT_HOURS)
    pv_day = expected_day_wh(slots, meta["dc_kw"], cp_cap_w / 1000)
    pv_scale = fit_scale(pv_day, y, split["train"])
    X, Xa1 = ai.features(days_df), ai.features_a1(days_df)
    rs = config.load("features")["model"]["random_state"]
    q_base = thr["ceiling"]["ai"]["base_quantile"]
    models = {"ai": ai.train(X.loc[split["train"]], y.loc[split["train"]], "gbm", q_base, rs),
              "ai_linear": ai.train(X.loc[split["train"]], y.loc[split["train"]], "linear", q_base, rs),
              "ai_o3": ai.train(Xa1.loc[split["train"]], y.loc[split["train"]], "gbm", q_base, rs)}
    base_day = {"pv": (pv_scale * pv_day).reindex(days_df.index),
                "ai": pd.Series(ai.predict(models["ai"], X), index=days_df.index),
                "ai_linear": pd.Series(ai.predict(models["ai_linear"], X), index=days_df.index),
                "ai_o3": pd.Series(ai.predict(models["ai_o3"], Xa1), index=days_df.index)}

    # 2. Thống kê của lô trung thực, chọn ngưỡng trên val.
    hs = pd.DataFrame({d: lot_row(data[d].series, data[d], temps[d], cons, window) for d in data}).T
    hs = hs.apply(pd.to_numeric)
    tau_cons, q_cons, cons_rate = consistency_thresholds(hs.loc[split["val"], list(STATS)],
                                                         thr["consistency_a"]["false_review"])
    sweep = thr["ceiling"]["false_review_sweep"]
    tau_ceil, ceil_rate = {}, {}
    for cfg, base in CEILING_BASE.items():
        for q in sweep:
            t, r = ceiling_tau(hs.loc[split["val"], "y_wh"].to_numpy(float), base_day[base].loc[split["val"]].to_numpy(),
                               q)
            tau_ceil[(cfg, q)], ceil_rate[(cfg, q)] = t, r
    return {k: v for k, v in locals().items() if k in CTX_KEYS}
