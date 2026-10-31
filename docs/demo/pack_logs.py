"""Đóng gói kết quả và nhật ký thí nghiệm để nộp kèm báo cáo (artifacts/ không nằm trong git).

Gói gồm artifacts/results/ (E1, E2 đăng ký trước và hậu kiểm, E3, parity, hình, run_all.log, nhật ký quyết định E1)
và manifests/ (hash để đối chiếu). Giải nén vào thư mục source/ rồi chạy
`python -m rec.manifest results-v1 --check` để kiểm từng file khớp hash đã commit.
Chạy: python docs/demo/pack_logs.py [--out ../final/logs/results-v1.zip]
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT.parent / "final" / "logs" / "results-v1.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in (ROOT / "artifacts" / "results").rglob("*") if p.is_file())
    files += sorted(p for p in (ROOT / "manifests").glob("*") if p.is_file())
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, p.relative_to(ROOT).as_posix())
    print(f"{len(files)} file → {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
