"""Hash SHA-256 của các file thuộc một mốc protocol (SPEC.md mục 9).

Chạy:  python -m rec.manifest spec-v1          # ghi manifests/spec-v1.sha256 (tương tự testset-v1, results-v1)
       python -m rec.manifest spec-v1 --check  # so file hiện tại với manifest đã ghi
Nội dung được chuẩn hóa CRLF → LF trước khi hash, để kết quả giống nhau trên Windows và macOS/Linux.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from rec.config import ROOT

MANIFEST_DIR = ROOT / "manifests"

MILESTONES: dict[str, list[str]] = {
    "spec-v1": [
        "SPEC.md",
        "COMPLIANCE.md",
        "configs/split.yaml",
        "configs/scenarios.yaml",
        "configs/features.yaml",
        "configs/thresholds.yaml",
        "configs/days.csv",
        "configs/days_dropped.csv",
    ],
    # Mốc 2: mã generator (trong repo) và tập test đã sinh (trong artifacts/, không commit, chỉ commit hash).
    "testset-v1": [
        "rec/generator/*.py",
        "rec/oracles/encoding.py",
        "rec/data/dataset.py",
        "artifacts/days.parquet",
        "artifacts/slots.parquet",
        "artifacts/testset/summary.json",
        "artifacts/testset/e1/*",
        "artifacts/testset/e2/*",
    ],
    # Giai đoạn 6: kết quả tất định (chạy lại phải ra cùng byte). Không gồm độ trễ của E3 (đo theo đồng hồ thật),
    # nhật ký chạy và mô hình dạng pickle; tham số lớp B đã khóa có trong layer_b.json.
    "results-v1": [
        "artifacts/model/*/layer_b.json",
        "artifacts/results/selection.json",
        "artifacts/results/prereg/*",
        "artifacts/results/day_only/*",
        "artifacts/results/e1/summary.csv",
        "artifacts/results/e1/cases.csv",
        "artifacts/results/e1/false_reject.csv",
        "artifacts/results/e1/gas_s*.csv",
        "artifacts/results/e1/decisions/*/*.csv",
        "artifacts/results/parity/*",
        "artifacts/results/e3/gas.csv",
        "artifacts/results/e3/gas_summary.csv",
        "artifacts/results/e3/lineage.csv",
        "artifacts/results/e3/summary.json",
        "artifacts/results/figures/*.png",
    ],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def files(name: str) -> list[str]:
    """Đường dẫn của mốc; mục có ký tự đại diện được mở rộng và sắp xếp."""
    out = []
    for entry in MILESTONES[name]:
        if any(ch in entry for ch in "*?["):
            out += sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(entry) if p.is_file())
        else:
            out.append(entry)
    return out


def build(name: str) -> str:
    return "".join(f"{digest(ROOT / rel)}  {rel}\n" for rel in files(name))


def check(name: str) -> list[str]:
    """Danh sách file đã đổi so với manifest (rỗng nếu khớp)."""
    recorded = (MANIFEST_DIR / f"{name}.sha256").read_text(encoding="utf-8").splitlines()
    current = build(name).splitlines()
    return [line.split("  ", 1)[1] for line, now in zip(recorded, current, strict=True) if line != now]


def main(argv: list[str]) -> int:
    name = argv[0]
    if "--check" in argv:
        changed = check(name)
        print("khop" if not changed else f"da doi: {changed}")
        return 1 if changed else 0
    MANIFEST_DIR.mkdir(exist_ok=True)
    (MANIFEST_DIR / f"{name}.sha256").write_text(build(name), encoding="utf-8", newline="\n")
    print(build(name), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
