"""E2 (RQ2): khớp lớp B trên train, chọn ngưỡng trên val, đánh giá trên tập test đã khóa (testset-v1).

Chạy: python -m rec.experiments.e2
Ghi vào artifacts/model/ (mô hình, ngưỡng) và artifacts/results/ (e2a.csv, e2a_honest.csv, e2b.csv, e2b_rule.json).
Chạy off-chain qua rec/gate/sim.py; test parity với chain làm ở giai đoạn 5.
"""
from __future__ import annotations

import json
import pickle
import sys

import numpy as np
import pandas as pd

from rec import config
from rec.checks.consistency import STATS, coverage, fit, stats
from rec.data import pvdaq
from rec.gate.sim import CHECKED_ORACLES, PROFILES, device_caps, layer_a, o1_report
from rec.generator.cases_e2 import apply_case
from rec.generator.common import INVERTER_MAX_W, load_days
from rec.metrics.e2 import bootstrap_diff, decide, lmax, lmax_scale, summarize
from rec.model import ai
from rec.model.calibrate import ceiling_tau, consistency_thresholds
from rec.physics.pvwatts import expected_day_wh, fit_scale
from rec.schema import OracleId

SLOT_HOURS = 0.25
CEILING_BASE = {"B2": "pv", "Proposed": "ai", "A1": "ai_o3", "A2": "ai_linear"}


def _lot_row(series: dict, dd, temp: np.ndarray, cons) -> dict:
    o1_day, o1_max = o1_report(series[OracleId.O1])
    cov = coverage({o: series[o] for o in CHECKED_ORACLES}, dd.sun)
    row = {"o1_day": o1_day, "o1_max": o1_max, "sun_slots": int(dd.sun.sum()), "cov_min": min(cov.values()),
           "o3_total": float(np.nansum(series[OracleId.O3])), "y_wh": dd.y_wh}
    row.update(stats(series, dd.sun, temp, cons))
    return row


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    scen, thr = config.load("scenarios"), config.load("thresholds")
    plant = scen["plant"]
    devices = list(plant["devices"])
    caps = device_caps(plant["devices"], INVERTER_MAX_W)
    cp_cap_w = INVERTER_MAX_W * sum(len(v) for v in plant["devices"].values())
    min_cov = thr["completeness"]["min_daytime_coverage"]
    artifacts = config.resolve_path("artifacts")
    (artifacts / "model").mkdir(exist_ok=True)
    (artifacts / "results").mkdir(exist_ok=True)

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
    hs = pd.DataFrame({d: _lot_row(data[d].series, data[d], temps[d], cons) for d in data}).T
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
    params = {"consistency": cons.to_dict(), "tau_consistency": tau_cons, "q_consistency": q_cons,
              "consistency_val_rate": cons_rate, "pv_scale": pv_scale,
              "tau_ceiling": {f"{c}@{q}": v for (c, q), v in tau_ceil.items()},
              "ceiling_val_rate": {f"{c}@{q}": v for (c, q), v in ceil_rate.items()},
              "model_hash": {k: ai.model_hash(m) for k, m in models.items()}}
    (artifacts / "model" / "layer_b.json").write_text(json.dumps(params, indent=2), encoding="utf-8")
    (artifacts / "model" / "models.pkl").write_bytes(pickle.dumps(models))

    # 3. E2a: mọi ca của tập test đã khóa.
    cases = pd.read_parquet(artifacts / "testset" / "e2" / "cases.parquet")
    labels = pd.read_parquet(artifacts / "testset" / "e2" / "labels.parquet")
    rows = []
    for row in cases.to_dict("records"):
        applied = apply_case(row, data, devices)
        dd = data[int(row["day"])]
        lot = _lot_row(applied.series, dd, temps[dd.day], cons)
        reasons = layer_a(applied.requests, lot["o1_day"], lot["o1_max"], lot["sun_slots"], caps, cp_cap_w)
        lot["minted_a_wh"] = sum(wh for (_, _, wh), r in zip(applied.requests, reasons) if r is None)
        lot["a_reject"] = any(r is not None for r in reasons)
        rows.append(lot)
    feat = pd.concat([cases.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    case_days = feat["day"].to_numpy()
    case_base = {b: base_day[b].reindex(case_days).to_numpy() for b in ("pv", "ai", "ai_linear")}
    case_base["ai_o3"] = ai.predict(models["ai_o3"], ai.features_a1(days_df.loc[case_days],
                                                                    feat["o3_total"].to_numpy()))
    tables, honest_tables = [], []
    for q in (thr["ceiling"]["false_review_main"], min(sweep)):
        for name, prof in PROFILES.items():
            base = case_base[CEILING_BASE[name]] if prof.ceiling else None
            dec = decide(feat, prof, tau_cons, base, tau_ceil.get((name, q)), min_cov)
            tbl, honest = summarize(feat, dec, labels)
            for t in (tbl, honest):
                t.insert(0, "q_ceiling", q)
                t.insert(0, "config", name)
            for p in thr["random_check"]["p"]:
                tbl[f"oir_p{int(p * 100)}"] = (1 - p) * tbl["oir"]
            tables.append(tbl)
            honest_tables.append(honest)
    e2a = pd.concat(tables, ignore_index=True)
    e2a_honest = pd.concat(honest_tables, ignore_index=True)
    e2a.to_csv(artifacts / "results" / "e2a.csv", index=False)
    e2a_honest.to_csv(artifacts / "results" / "e2a_honest.csv", index=False)

    # 4. E2b: LMAX giải tích trên lô trung thực của test.
    test = hs.loc[split["test"]]
    day_type = days_df.loc[split["test"], "day_type"].to_numpy()
    yt = test["y_wh"].to_numpy(float)
    o3t = test["o3_total"].to_numpy(float)
    a1_fn = lambda g: ai.predict(models["ai_o3"], ai.features_a1(days_df.loc[split["test"]], g * o3t))
    lrows, scales = [], {}
    for q in sweep:
        for name, prof in PROFILES.items():
            base = base_day[CEILING_BASE[name]].loc[split["test"]].to_numpy() if prof.ceiling else None
            for k in (1, 2, 3):
                s = lmax_scale(test, k, tau_cons, prof, base, tau_ceil.get((name, q)), min_cov, cp_cap_w,
                               base_fn=a1_fn if name == "A1" else None)
                scales[(name, q, k)] = s
                rec = {"config": name, "q_ceiling": q, "k": k, "lmax": lmax(yt, s)}
                for t in ("clear", "partly", "cloudy"):
                    m = day_type == t
                    rec[f"lmax_{t}"] = lmax(yt[m], s[m])
                lrows.append(rec)
    e2b = pd.DataFrame(lrows)
    e2b.to_csv(artifacts / "results" / "e2b.csv", index=False)
    rule = {}
    for q in (thr["ceiling"]["false_review_main"], min(sweep)):
        d, lo, hi = bootstrap_diff(yt, scales[("B2", q, 3)], scales[("Proposed", q, 3)])
        rule[str(q)] = {"lmax_B2_minus_Proposed_k3": d, "ci95": [lo, hi]}
    (artifacts / "results" / "e2b_rule.json").write_text(json.dumps(rule, indent=2), encoding="utf-8")

    print("Ngưỡng nhất quán (q =", round(q_cons, 4), ", REVIEW nhầm trên val =", round(cons_rate, 4), "):",
          {k: round(v, 4) for k, v in tau_cons.items()})
    print("η =", round(cons.eta, 4), "| β =", round(cons.beta, 2), "| γ =", round(cons.gamma, 5),
          "| hệ số pvlib =", round(pv_scale, 4))
    print("τ trần ở 4%:", {c: round(tau_ceil[(c, 0.04)], 4) for c in CEILING_BASE})
    print("\nE2b – LMAX (k = 3):")
    print(e2b[e2b["k"] == 3].pivot(index="config", columns="q_ceiling", values="lmax").round(4).to_string())
    print("\nE2b – LMAX theo k ở mức trần 4%:")
    print(e2b[e2b["q_ceiling"] == 0.04].pivot(index="config", columns="k", values="lmax").round(4).to_string())
    print("\nQuy tắc kết luận (B2 − Proposed, k = 3):", json.dumps(rule))
    print("\nREVIEW nhầm trên test (tất cả lô trung thực), mức trần 4%:")
    h = e2a_honest[(e2a_honest["neg_type"] == "all") & (e2a_honest["q_ceiling"] == 0.04)]
    print(h[["config", "review_rate", "mwh_held_share"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
