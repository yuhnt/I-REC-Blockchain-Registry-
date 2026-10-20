"""Sinh tập test của mốc 2 (SPEC mục 11).

Chạy: python -m rec.generator.cli   (cần artifacts/days.parquet, slots.parquet từ rec.data.dataset)
Ghi vào artifacts/testset/:
  e1/honest_s<seed>.jsonl         dòng hợp lệ (6 thiết bị, có L3) trên các ngày test
  e1/honest_group_s<seed>.jsonl   dòng hợp lệ dạng Production Group (L4)
  e1/<kịch bản>_s<seed>.jsonl     sự kiện tấn công chèn chồng lên dòng hợp lệ cùng seed
  e1/<kịch bản>_s<seed>.removed.json   yêu cầu hợp lệ bị thay (D5)
  e1/labels.parquet               nhãn ẩn của E1
  e2/cases.parquet, e2/labels.parquet  bảng ca và nhãn ẩn của E2
  summary.json
Bộ kiểm tra generator phải qua hết thì mới ghi.
"""
from __future__ import annotations

import json
import sys

import pandas as pd

from rec import config
from rec.generator import checks
from rec.generator.attacks_e1 import e1_overlay
from rec.generator.cases_e2 import build_cases, labels_for
from rec.generator.common import load_days
from rec.generator.honest import honest_stream
from rec.generator.io import labels_frame, write_events


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252, không in được tiếng Việt
    scen = config.load("scenarios")
    plant = scen["plant"]
    devices = list(plant["devices"])
    seeds = scen["seeds"]["test"]
    out = config.resolve_path("artifacts") / "testset"
    (out / "e1").mkdir(parents=True, exist_ok=True)
    (out / "e2").mkdir(parents=True, exist_ok=True)

    days_df, data = load_days()
    test_days = sorted(int(d) for d in days_df.loc[days_df["split"] == "test", "day"])
    exp1 = scen["experiments"]["E1"]
    errors: list[str] = []
    label_frames = []
    summary = {"test_days": len(test_days), "seeds": seeds, "e1": {}, "e2": {}}

    for seed in seeds:
        for variant, name in (("devices", "honest"), ("group", "honest_group")):
            hs = honest_stream(test_days, data, plant, seed, scen["honest_stream"], variant=variant)
            errors += [f"{name} s{seed}: {e}" for e in checks.check_clean_stream(hs.events)]
            errors += [f"{name} s{seed}: {e}" for e in checks.check_time_order(hs.events)]
            stream = f"{name}_s{seed}"
            summary["e1"][stream] = write_events(out / "e1" / f"{stream}.jsonl", hs.events)
            label_frames.append(labels_frame(hs.labels, stream))
            if variant == "devices":
                honest = hs
        for attack in exp1["attacks"]:
            ov = e1_overlay(attack, honest, test_days, data, plant, scen["attacks"][attack]["params"],
                            exp1["cases_per_attack"], seed)
            stream = f"{attack}_s{seed}"
            summary["e1"][stream] = write_events(out / "e1" / f"{stream}.jsonl", ov.events)
            (out / "e1" / f"{stream}.removed.json").write_text(json.dumps(sorted(ov.removed)), encoding="utf-8")
            label_frames.append(labels_frame(ov.labels, stream))
            if len(ov.labels) == 0:
                errors.append(f"{stream}: không sinh được ca nào")

    cases = build_cases(test_days, data, scen["attacks"], seeds)
    labels = labels_for(cases, data, devices)
    errors += checks.check_cases(cases, labels, data, devices)
    summary["e2"] = cases.groupby("scenario").size().to_dict()
    summary["e2_days_per_scenario"] = cases.groupby("scenario")["day"].nunique().to_dict()

    if errors:
        print("GENERATOR KHONG QUA KIEM TRA:")
        for e in errors[:50]:
            print(" -", e)
        return 1

    pd.concat(label_frames, ignore_index=True).to_parquet(out / "e1" / "labels.parquet", index=False)
    cases.to_parquet(out / "e2" / "cases.parquet", index=False)
    labels.to_parquet(out / "e2" / "labels.parquet", index=False)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
