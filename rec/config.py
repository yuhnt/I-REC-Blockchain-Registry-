"""Đọc và kiểm tra tính nhất quán của các file đặc tả trong configs/ (SPEC.md)."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "configs"

REGIMES = {"R1", "R2"}
SPEC_FILES = ("split", "scenarios", "features", "thresholds")


class SpecError(ValueError):
    """Đặc tả mâu thuẫn hoặc thiếu."""


def load(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(key: str) -> Path:
    """Đường dẫn trong paths.yaml, tính từ thư mục source/."""
    return (ROOT / load("paths")[key]).resolve()


def _fail(msg: str) -> None:
    raise SpecError(msg)


def check_split(s: dict[str, Any]) -> None:
    splits = s["splits"]
    years = [y for name in ("train", "val", "test") for y in splits[name]]
    if len(years) != len(set(years)):
        _fail("một năm nằm ở hai tập")
    span = set(range(s["range"]["start"].year, s["range"]["end"].year + 1))
    if set(years) != span:
        _fail(f"các tập phải phủ đúng các năm {sorted(span)}")
    exp = s["expected_days"]
    if exp["train"] + exp["val"] + exp["test"] != exp["total"]:
        _fail("expected_days không cộng đúng tổng")
    if not 0 < s["valid_day"]["min_coverage"] <= 1:
        _fail("min_coverage phải trong (0, 1]")


def check_scenarios(s: dict[str, Any]) -> None:
    inverters = [i for blk in s["plant"]["devices"].values() for i in blk]
    if sorted(inverters) != list(range(1, 25)):
        _fail("6 thiết bị phải chia đúng 24 inverter, mỗi inverter một lần")
    if any(len(blk) != 4 for blk in s["plant"]["devices"].values()):
        _fail("mỗi thiết bị gồm 4 inverter")
    seeds = s["seeds"]["test"]
    if len(seeds) != 5 or len(set(seeds)) != 5:
        _fail("cần 5 seed khác nhau cho tập test")

    attacks = s["attacks"]
    for name, a in attacks.items():
        if not a["regimes"] or not set(a["regimes"]) <= REGIMES:
            _fail(f"{name}: regimes phải là tập con khác rỗng của {sorted(REGIMES)}")

    for exp_name, regime in (("E1", "R1"), ("E2a", "R2")):
        exp = s["experiments"][exp_name]
        if exp["regime"] != regime:
            _fail(f"{exp_name} phải chạy ở {regime}")
        for name in exp["attacks"]:
            if name not in attacks:
                _fail(f"{exp_name} dùng kịch bản chưa định nghĩa: {name}")
            if regime not in attacks[name]["regimes"]:
                _fail(f"{name} không khai báo chế độ {regime} nhưng có trong {exp_name}")

    # H2b: mọi mức f của D4b phải có mức α tương ứng trong M2.
    alphas = {round(a, 6) for a in attacks["M2"]["params"]["alpha"]}
    missing = {round(f, 6) for f in attacks["D4b"]["params"]["f"]} - alphas
    if missing:
        _fail(f"M2 thiếu α = f để kiểm chứng H2b: {sorted(missing)}")

    for k in (attacks["D4b"]["params"]["k"] + attacks["M2"]["params"]["k"]):
        if k not in (1, 2, 3):
            _fail("k phải thuộc {1, 2, 3}")

    for name in s["experiments"]["E1"]["attacks"]:
        if "blocked_at" not in attacks[name]:
            _fail(f"{name} trong E1 phải ghi điểm chặn (blocked_at)")

    # Mẫu âm lớp A (không được REJECT nhầm) đo ở E1; mẫu âm lớp B (REVIEW nhầm) đo ở E2a.
    negatives = s["negatives"]
    for exp_name, layer in (("E1", "A"), ("E2a", "B")):
        for name in s["experiments"][exp_name]["negatives"]:
            if negatives[name]["layer"] != layer:
                _fail(f"{name} thuộc lớp {negatives[name]['layer']}, không đo ở {exp_name}")
    used = set(s["experiments"]["E1"]["negatives"]) | set(s["experiments"]["E2a"]["negatives"])
    if used != set(negatives):
        _fail(f"mẫu âm chưa được đo ở thí nghiệm nào: {sorted(set(negatives) - used)}")


def check_features(f: dict[str, Any]) -> None:
    allowed = set(f["allowed_sources"])
    if not allowed <= {"O4", "static"}:
        _fail("mô hình AI chỉ được dùng O4 và thông số tĩnh")
    for name, spec in f["features"].items():
        if spec["source"] not in allowed:
            _fail(f"đặc trưng {name} lấy từ nguồn không được phép: {spec['source']}")
    assert_feature_columns(f["features"], f)
    if f["target"] in f["features"]:
        _fail("biến mục tiêu không được nằm trong đặc trưng")


def assert_feature_columns(columns: Iterable[str], f: dict[str, Any] | None = None) -> None:
    """Chặn rò rỉ: không cột nào của ma trận đặc trưng được mang tiền tố của O1–O3."""
    prefixes = tuple((f or load("features"))["forbidden_prefixes"])
    bad = [c for c in columns if c.lower().startswith(prefixes)]
    if bad:
        _fail(f"cột đặc trưng bị cấm (rò rỉ O1–O3): {bad}")


def check_thresholds(t: dict[str, Any]) -> None:
    if t["calibration"]["split"] != "val" or not t["calibration"]["honest_only"]:
        _fail("ngưỡng chỉ được chọn trên lô trung thực của val")
    if not t["consistency_a"]["one_sided"]:
        _fail("luật (a) chỉ được báo khi O1 cao hơn (một phía)")
    a = t["consistency_a"]["false_review"]
    ceiling = t["ceiling"]
    main, sweep = ceiling["false_review_main"], ceiling["false_review_sweep"]
    if main not in sweep:
        _fail("mức chính của trần phải nằm trong dãy quét")
    if sweep != sorted(sweep) or not all(0 < q < 1 for q in sweep):
        _fail("dãy quét tỉ lệ REVIEW nhầm phải tăng dần, trong (0, 1)")
    if not 0 < a < main:
        _fail("luật (a) phải được phần REVIEW nhầm nhỏ hơn trần")
    if t["completeness"]["min_daytime_coverage"] <= 0.5:
        _fail("độ phủ tối thiểu của báo cáo quá thấp")
    if t["random_check"]["at_ceiling_false_review"] != main:
        _fail("kiểm tra ngẫu nhiên chạy ở mức chính của trần")


def check_all() -> None:
    check_split(load("split"))
    check_scenarios(load("scenarios"))
    check_features(load("features"))
    check_thresholds(load("thresholds"))
