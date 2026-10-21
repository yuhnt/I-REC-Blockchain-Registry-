"""Giai đoạn 6: sinh lại toàn bộ bảng và hình từ dữ liệu gốc và các mốc đã khóa.

Thứ tự:
  1. dữ liệu: rec.data.days → rec.data.dataset → rec.generator.cli, rồi kiểm `spec-v1` và `testset-v1`;
  2. E2: bản đăng ký trước (prereg), chọn biến thể hậu kiểm trên val, chạy biến thể đã chọn;
  3. E1: hai backend SQLite, chain chạy song song mỗi seed một node Hardhat, rồi tính chỉ số;
  4. parity chain – mô phỏng; E3; hình kết quả;
  5. manifest kết quả `results-v1`: ghi mới, hoặc với --check thì so với manifest đã commit.

Chạy: python -m rec.experiments.run_all [--skip-data] [--skip-chain] [--check]
Nhật ký ở artifacts/results/run_all.log. Cần dữ liệu gốc ở ../dataset và Node/Hardhat trong contracts/.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

from rec import config

PY = sys.executable


def _run(cmd: list[str], log) -> None:
    t0 = time.time()
    print("$", " ".join(cmd), flush=True)
    res = subprocess.run(cmd, cwd=config.ROOT, stdout=log, stderr=subprocess.STDOUT)
    print(f"  → mã {res.returncode}, {time.time() - t0:.0f} s", flush=True)
    if res.returncode != 0:
        raise SystemExit(f"bước thất bại: {' '.join(cmd)} (xem artifacts/results/run_all.log)")


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    artifacts = config.resolve_path("artifacts")
    (artifacts / "results").mkdir(parents=True, exist_ok=True)
    seeds = config.load("scenarios")["seeds"]["test"]
    t_all = time.time()
    with open(artifacts / "results" / "run_all.log", "w", encoding="utf-8") as log:
        def m(*args):
            _run([PY, "-m", *args], log)

        if "--skip-data" not in argv:
            m("rec.data.days")
            m("rec.data.dataset")
            m("rec.generator.cli")
        m("rec.manifest", "spec-v1", "--check")
        m("rec.manifest", "testset-v1", "--check")

        m("rec.experiments.e2", "--variant", "prereg")
        m("rec.experiments.e2", "--select")
        chosen = json.loads((artifacts / "results" / "selection.json").read_text(encoding="utf-8"))["chosen"]
        m("rec.experiments.e2", "--variant", chosen)

        m("rec.experiments.e1", "--backends", "b0_separate,b0_shared", "--run-only")
        if "--skip-chain" not in argv:
            print("$ E1 trên chain:", len(seeds), "seed song song", flush=True)
            t0 = time.time()
            procs = [subprocess.Popen([PY, "-m", "rec.experiments.e1", "--backends", "chain", "--seeds", str(s),
                                       "--run-only", "--port", str(8545 + i)], cwd=config.ROOT, stdout=log,
                                      stderr=subprocess.STDOUT) for i, s in enumerate(seeds)]
            codes = [p.wait() for p in procs]
            print(f"  → mã {codes}, {time.time() - t0:.0f} s", flush=True)
            if any(codes):
                raise SystemExit("E1 trên chain thất bại")
            m("rec.experiments.e1", "--metrics-only")
            m("rec.experiments.parity", "--per-scenario", "50")
            m("rec.experiments.e3")
        else:
            m("rec.experiments.e1", "--backends", "b0_separate,b0_shared", "--metrics-only")
        m("rec.experiments.figures", "--variant", "prereg")

        if "--check" in argv:
            m("rec.manifest", "results-v1", "--check")
        else:
            m("rec.manifest", "results-v1")
    print(f"xong sau {(time.time() - t_all) / 60:.1f} phút", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
