"""Hash SHA-256 của các file thuộc một mốc protocol (SPEC.md mục 9).

Chạy:  python -m rec.manifest spec-v1          # ghi manifests/spec-v1.sha256
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
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build(name: str) -> str:
    return "".join(f"{digest(ROOT / rel)}  {rel}\n" for rel in MILESTONES[name])


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
