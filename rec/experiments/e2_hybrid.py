"""Cải tiến hậu kiểm cho ngưỡng MWh (manifests/CHANGES.md, mục 12/11/2026): hai ứng viên, chọn trên val.

- hybrid: ngưỡng = min(ngưỡng B2, ngưỡng Proposed), hai τ ở cùng mức phân vị trên val, hợp hai cờ ≤ 4%.
- ratio:  GBM phân vị 0,95 học tỉ số công tơ / nền PVWatts; ngưỡng = nền PVWatts · tỉ số dự đoán · (1 + τ).

Chạy: python -m rec.experiments.e2_hybrid            # chỉ chọn trên val, ghi selection.json
      python -m rec.experiments.e2_hybrid --test     # chạy test đúng một lần cho ứng viên đã chọn
      python -m rec.experiments.e2_hybrid --sweep    # mô tả: LMAX và REVIEW nhầm trên test theo dãy q của SPEC
Ghi artifacts/results/hybrid/.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from rec import config
from rec.checks.consistency import VARIANTS
from rec.gate.sim import PROFILES
from rec.metrics.e2 import bootstrap_diff, lmax, lmax_scale
from rec.model import ai
from rec.model.calibrate import ceiling_tau
from rec.sim.layer_b import fit_and_calibrate

Q = 0.04
PROF = PROFILES["Proposed"]  # đủ báo cáo + nhất quán + một ngưỡng MWh


def _hybrid_taus(y: np.ndarray, pv: np.ndarray, aib: np.ndarray, target: float) -> tuple[float, float, float, float]:
    """(τ_pv, τ_ai, q′, tỉ lệ hợp hai cờ trên val): q′ lớn nhất mà hợp hai cờ ≤ ⌊target · n⌋ ngày."""
    limit = int(np.floor(target * len(y)))
    best = None
    for q in np.linspace(0.0, target, 401):
        tp, _ = ceiling_tau(y, pv, q)
        ta, _ = ceiling_tau(y, aib, q)
        n = int(np.sum(y > np.minimum(pv * (1 + tp), aib * (1 + ta))))
        if n <= limit:
            best = (tp, ta, float(q), n / len(y))
    return best


def candidates(ctx: dict, q_target: float = Q) -> dict[str, dict]:
    """Ngưỡng MWh theo ngày của từng ứng viên, tham số chỉ từ train (khớp) và val (τ)."""
    sp, days = ctx["split"], ctx["days_df"]
    y = ctx["hs"]["y_wh"].astype(float)
    pv, aib = ctx["base_day"]["pv"], ctx["base_day"]["ai"]
    yv = y.loc[sp["val"]].to_numpy()
    tp, ta, q_h, rate_h = _hybrid_taus(yv, pv.loc[sp["val"]].to_numpy(), aib.loc[sp["val"]].to_numpy(), q_target)
    X = ai.features(days)
    rs = config.load("features")["model"]["random_state"]
    ratio_model = ai.train(X.loc[sp["train"]], (y / pv).loc[sp["train"]], "gbm",
                           ctx["thr"]["ceiling"]["ai"]["base_quantile"], rs)
    rbase = pv * pd.Series(ai.predict(ratio_model, X), index=days.index)
    tr, rate_r = ceiling_tau(yv, rbase.loc[sp["val"]].to_numpy(), q_target)
    tau_b2, tau_pr = ctx["tau_ceil"][("B2", q_target)], ctx["tau_ceil"][("Proposed", q_target)]
    return {"B2": {"ceiling": pv * (1 + tau_b2), "params": {"tau": tau_b2}},
            "Proposed": {"ceiling": aib * (1 + tau_pr), "params": {"tau": tau_pr}},
            "hybrid": {"ceiling": np.minimum(pv * (1 + tp), aib * (1 + ta)),
                       "params": {"tau_pv": tp, "tau_ai": ta, "q": q_h, "val_rate": rate_h}},
            "ratio": {"ceiling": rbase * (1 + tr),
                      "params": {"tau": tr, "val_rate": rate_r, "model_hash": ai.model_hash(ratio_model)}}}


def evaluate(ctx: dict, ceiling: pd.Series, split: str) -> dict:
    ids = ctx["split"][split]
    hs = ctx["hs"].loc[ids]
    y, c = hs["y_wh"].to_numpy(float), ceiling.loc[ids].to_numpy(float)
    day_type = ctx["days_df"].loc[ids, "day_type"].to_numpy()
    scales = {k: lmax_scale(hs, k, ctx["tau_cons"], PROF, c, 0.0, ctx["min_cov"], ctx["cp_cap_w"]) for k in (1, 2, 3)}
    flag = (hs["cov_min"].to_numpy(float) < ctx["min_cov"]) | (y > c)
    for st, tau in ctx["tau_cons"].items():
        flag |= hs[st].to_numpy(float) > tau
    rec = {f"lmax_k{k}": lmax(y, s) for k, s in scales.items()}
    for t in ("clear", "partly", "cloudy"):
        m = day_type == t
        rec[f"lmax_k3_{t}"] = lmax(y[m], scales[3][m])
        rec[f"review_{t}"] = float(flag[m].mean())
    rec.update(review_rate=float(flag.mean()), review_ceiling=float((y > c).mean()),
               mwh_held_share=float(y[flag].sum() / y.sum()))
    return {"metrics": rec, "y": y, "s3": scales[3]}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ctx = fit_and_calibrate(VARIANTS["prereg"])
    cand = candidates(ctx)
    out = config.resolve_path("artifacts") / "results" / "hybrid"
    out.mkdir(parents=True, exist_ok=True)
    val = {n: evaluate(ctx, c["ceiling"], "val") for n, c in cand.items()}
    score = {n: val[n]["metrics"]["lmax_k3"] for n in ("hybrid", "ratio")}
    best = min(score, key=score.get)
    improved = score[best] < min(val["B2"]["metrics"]["lmax_k3"], val["Proposed"]["metrics"]["lmax_k3"])
    sel = {"criterion": "manifests/CHANGES.md, mục 12/11/2026", "q_ceiling": Q,
           "params": {n: c["params"] for n, c in cand.items()},
           "val": {n: v["metrics"] for n, v in val.items()}, "chosen": best if improved else None}
    (out / "selection.json").write_text(json.dumps(sel, indent=2, ensure_ascii=False), encoding="utf-8")
    print("VAL:")
    print(pd.DataFrame({n: v["metrics"] for n, v in val.items()}).round(4).to_string())
    print("Chọn:", sel["chosen"])
    if not ({"--test", "--sweep"} & set(argv)) or not improved:
        return 0
    test = {n: evaluate(ctx, cand[n]["ceiling"], "test") for n in ("B2", "Proposed", best)}
    res = {"chosen": best, "test": {n: v["metrics"] for n, v in test.items()}, "diff_k3": {}}
    for ref in ("B2", "Proposed"):
        d, lo, hi = bootstrap_diff(test[ref]["y"], test[ref]["s3"], test[best]["s3"])
        res["diff_k3"][f"{ref}_minus_{best}"] = {"diff": d, "ci95": [lo, hi]}
    (out / "test.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nTEST:")
    print(pd.DataFrame(res["test"]).round(4).to_string())
    print(json.dumps(res["diff_k3"], indent=2))
    if "--sweep" in argv:  # không chọn gì ở đây: chỉ xem ứng viên nằm đâu trên đường đánh đổi của B2 và Proposed
        rows = []
        for q in ctx["sweep"]:
            cq = candidates(ctx, q)
            for n in ("B2", "Proposed", best):
                m = evaluate(ctx, cq[n]["ceiling"], "test")["metrics"]
                rows.append({"config": n, "q_ceiling": q, "lmax_k3": m["lmax_k3"], "review_rate": m["review_rate"],
                             "mwh_held_share": m["mwh_held_share"]})
        sweep = pd.DataFrame(rows)
        sweep.to_csv(out / "sweep_test.csv", index=False)
        print("\nSWEEP (test):")
        print(sweep.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
