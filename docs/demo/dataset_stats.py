"""Bảng thống kê dữ liệu theo tập train / val / test cho báo cáo (docs/demo/DEMO.md mục 1).

Cần artifacts/days.parquet (python -m rec.data.dataset).
Chạy: python docs/demo/dataset_stats.py
"""
from __future__ import annotations

import pandas as pd

from rec import config


def main() -> None:
    d = pd.read_parquet(config.resolve_path("artifacts") / "days.parquet")
    d["mwh"] = d["y_wh"] / 1e6
    rows = []
    for split in ["train", "val", "test"]:
        x = d[d["split"] == split]
        types = x["day_type"].value_counts()
        years = pd.to_datetime(x["date"])
        rows.append({
            "tập": split, "năm": f"{years.min().year}–{years.max().year}", "số ngày": len(x),
            "quang": int(types.get("clear", 0)), "mây vừa": int(types.get("partly", 0)),
            "nhiều mây": int(types.get("cloudy", 0)),
            "MWh/ngày TB": round(x["mwh"].mean(), 2), "độ lệch chuẩn": round(x["mwh"].std(), 2),
            "min": round(x["mwh"].min(), 2), "max": round(x["mwh"].max(), 2), "tổng MWh": round(x["mwh"].sum()),
            "% ngày inverter báo 0": round(100 * x["outage"].mean(), 1),
            "O1/O2 trung vị": round((x["y_wh"] / x["o2_wh"]).median(), 4),
        })
    df = pd.DataFrame(rows).astype(str)
    print("| " + " | ".join(df.columns) + " |")
    print("|" + "---|" * len(df.columns))
    for r in df.itertuples(index=False):
        print("| " + " | ".join(r) + " |")


if __name__ == "__main__":
    main()
