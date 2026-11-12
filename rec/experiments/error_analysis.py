"""Error analysis của lớp B: ngày nào ngưỡng MWh của AI lỏng hơn ngưỡng vật lý, và vì sao.

Chỉ đọc và thống kê; không chọn tham số nào. Mô hình và ngưỡng lấy đúng như lần chạy đăng ký trước
(khớp trên train, chọn ngưỡng trên val, mức REVIEW nhầm của ngưỡng MWh 4%). Val và test báo cáo tách riêng:
mọi quyết định cải tiến về sau chỉ được dựa vào cột val.

Chạy: python -m rec.experiments.error_analysis
Ghi artifacts/results/error_analysis/ (days.csv, by_day_type.csv, by_outage.csv, satellite.csv, worst_days.csv).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from rec import config
from rec.checks.consistency import STATS, VARIANTS
from rec.gate.sim import PROFILES
from rec.metrics.e2 import lmax, lmax_scale
from rec.sim.layer_b import fit_and_calibrate

Q = 0.04                 # mức REVIEW nhầm chính của ngưỡng MWh
LOGGING_OUTAGE = 0.10    # ngày inverter báo 0 mà công tơ cao hơn η · tổng inverter trên 10%: coi là ngừng ghi số liệu
BASES = {"B2": "pv", "Proposed": "ai"}


def day_table(ctx: dict, split: str) -> pd.DataFrame:
    """Một dòng mỗi ngày trung thực của `split`: ngưỡng, khoảng hở, hệ số khai tăng lớn nhất còn lọt (k = 3)."""
    ids = ctx["split"][split]
    hs, days = ctx["hs"].loc[ids], ctx["days_df"].loc[ids]
    y = hs["y_wh"].to_numpy(float)
    out = pd.DataFrame({"day": ids, "date": days["date"].astype(str).to_numpy(), "split": split, "y_wh": y,
                        "day_type": days["day_type"].to_numpy(), "outage": days["outage"].to_numpy(bool),
                        "r12_day": hs["r12_day"].to_numpy(float),
                        "clearsky_index": days["clearsky_index"].to_numpy(float),
                        "sat_vs_site": days["o4_whm2"].to_numpy(float) / days["o3_whm2"].to_numpy(float) - 1})
    out["outage_kind"] = np.where(~out["outage"], "không", np.where(out["r12_day"] > LOGGING_OUTAGE, "ngừng ghi",
                                                                   "ngừng phát"))
    cons_flag = np.zeros(len(ids), dtype=bool)
    for st in STATS:
        cons_flag |= hs[st].to_numpy(float) > ctx["tau_cons"][st]
    out["flag_consistency"] = cons_flag
    out["flag_missing"] = hs["cov_min"].to_numpy(float) < ctx["min_cov"]
    for name, b in BASES.items():
        base = ctx["base_day"][b].loc[ids].to_numpy(float)
        tau = ctx["tau_ceil"][(name, Q)]
        ceil = base * (1 + tau)
        s = lmax_scale(hs, 3, ctx["tau_cons"], PROFILES[name], base, tau, ctx["min_cov"], ctx["cp_cap_w"])
        out[f"base_{name}"] = base
        out[f"headroom_{name}"] = ceil / y - 1          # mức khai tăng mà riêng ngưỡng MWh còn cho qua
        out[f"flag_ceiling_{name}"] = y > ceil
        out[f"s_{name}"] = s
        out[f"leak_wh_{name}"] = y * np.clip(s - 1, 0, None)
    return out


def _lmax(g: pd.DataFrame, name: str) -> float:
    return lmax(g["y_wh"].to_numpy(float), g[f"s_{name}"].to_numpy(float))


def by_group(t: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for (split, key), g in t.groupby(["split", col], sort=False):
        tot = t[t["split"] == split]
        rec = {"split": split, col: key, "days": len(g), "share_y": g["y_wh"].sum() / tot["y_wh"].sum()}
        for name in BASES:
            rec[f"lmax_{name}"] = _lmax(g, name)
            rec[f"leak_share_{name}"] = g[f"leak_wh_{name}"].sum() / tot[f"leak_wh_{name}"].sum()
            rec[f"headroom_med_{name}"] = g[f"headroom_{name}"].median()
            rec[f"headroom_p90_{name}"] = g[f"headroom_{name}"].quantile(0.9)
            rec[f"review_{name}"] = (g["flag_missing"] | g["flag_consistency"] | g[f"flag_ceiling_{name}"]).mean()
            rec[f"review_ceiling_{name}"] = g[f"flag_ceiling_{name}"].mean()
        rec["review_consistency"] = g["flag_consistency"].mean()
        rows.append(rec)
    return pd.DataFrame(rows)


def satellite(t: pd.DataFrame, ctx: dict) -> pd.DataFrame:
    """Sai lệch bức xạ vệ tinh so với cảm biến tại chỗ, và độ rộng của dự đoán, theo loại ngày."""
    n_train = ctx["days_df"].loc[ctx["split"]["train"], "day_type"].value_counts()
    rows = []
    for (split, dt), g in t.groupby(["split", "day_type"], sort=False):
        err = g["sat_vs_site"].abs()
        rows.append({"split": split, "day_type": dt, "days": len(g), "train_days": int(n_train.get(dt, 0)),
                     "sat_abs_err_med": err.median(), "sat_abs_err_p90": err.quantile(0.9),
                     "sat_bias_med": g["sat_vs_site"].median(),
                     "y_over_base_med_B2": (g["y_wh"] / g["base_B2"]).median(),
                     "y_over_base_p05_B2": (g["y_wh"] / g["base_B2"]).quantile(0.05),
                     "y_over_base_med_Proposed": (g["y_wh"] / g["base_Proposed"]).median(),
                     "y_over_base_p05_Proposed": (g["y_wh"] / g["base_Proposed"]).quantile(0.05),
                     "corr_headroom_saterr_Proposed": g["headroom_Proposed"].corr(-g["sat_vs_site"], method="spearman"),
                     "corr_headroom_saterr_B2": g["headroom_B2"].corr(-g["sat_vs_site"], method="spearman")})
    return pd.DataFrame(rows)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ctx = fit_and_calibrate(VARIANTS["prereg"])
    t = pd.concat([day_table(ctx, s) for s in ("val", "test")], ignore_index=True)
    out = config.resolve_path("artifacts") / "results" / "error_analysis"
    out.mkdir(parents=True, exist_ok=True)
    tables = {"by_day_type": by_group(t, "day_type"), "by_outage": by_group(t, "outage_kind"),
              "satellite": satellite(t, ctx)}
    worst = (t[t["split"] == "test"].assign(extra_wh=lambda d: d["leak_wh_Proposed"] - d["leak_wh_B2"])
             .sort_values("extra_wh", ascending=False).head(15))
    tables["worst_days"] = worst[["date", "day_type", "outage_kind", "y_wh", "clearsky_index", "sat_vs_site",
                                  "headroom_B2", "headroom_Proposed", "extra_wh"]]
    t.to_csv(out / "days.csv", index=False)
    pd.set_option("display.width", 250)
    for name, tbl in tables.items():
        tbl.to_csv(out / f"{name}.csv", index=False)
        print(f"\n== {name} ==")
        print(tbl.round(4).to_string(index=False))
    for split in ("val", "test"):
        g = t[t["split"] == split]
        print(f"\nLMAX k = 3 trên {split}: B2 {_lmax(g, 'B2'):.4f} | Proposed {_lmax(g, 'Proposed'):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
