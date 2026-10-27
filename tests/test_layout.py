"""Quy tắc phân lớp của codebase (docs/PLAN.md mục 2): gói ở lớp dưới không import gói ở lớp trên.

Cùng lớp được import nhau. Các thí nghiệm không import lẫn nhau: code dùng chung giữa E1–E3, demo và dashboard đặt
ở `rec/sim/` hoặc `rec/registry/`.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYER = {"schema": 0, "timeutil": 0, "config": 0, "manifest": 0,
         "data": 1, "physics": 1,
         "oracles": 2,
         "generator": 3,
         "checks": 4, "model": 4, "metrics": 4,
         "gate": 5,
         "registry": 6,
         "sim": 7,
         "experiments": 8, "deploy": 8,
         "dashboard": 9}
# Ngoại lệ đã biết: nút oracle dựng báo cáo ngày bằng đúng hàm của generator. generator nằm trong manifest testset-v1
# nên không dời hàm đó xuống rec/oracles/ được.
ALLOWED = {("rec/oracles/node.py", "generator")}


def _package(path: Path) -> str:
    rel = path.relative_to(ROOT).parts
    if rel[0] == "dashboard":
        return "dashboard"
    return rel[1].removesuffix(".py")


def _imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod == "rec":
                yield from (a.name for a in node.names)
            elif mod.startswith("rec."):
                yield mod.split(".")[1]
            elif mod.startswith("dashboard"):
                yield "dashboard"


def test_no_upward_imports():
    files = [p for p in (ROOT / "rec").rglob("*.py")] + [p for p in (ROOT / "dashboard").rglob("*.py")]
    bad = []
    for f in files:
        pkg = _package(f)
        rel = f.relative_to(ROOT).as_posix()
        for target in _imports(f):
            if target not in LAYER or pkg not in LAYER:
                continue
            if LAYER[target] > LAYER[pkg] and (rel, target) not in ALLOWED:
                bad.append(f"{rel} → rec.{target}")
            if pkg == "experiments" and target == "experiments" and not rel.endswith("run_all.py"):
                bad.append(f"{rel} → rec.experiments (dời phần dùng chung sang rec/sim hoặc rec/registry)")
    assert not bad, "\n".join(bad)


def test_every_package_has_a_layer():
    pkgs = {p.name for p in (ROOT / "rec").iterdir() if p.is_dir() and not p.name.startswith("__")}
    assert pkgs <= set(LAYER), pkgs - set(LAYER)
