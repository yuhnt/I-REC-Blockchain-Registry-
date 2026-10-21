"""Hình kết quả cho báo cáo, vẽ lại từ các bảng trong artifacts/results/ (giai đoạn 6).

Chạy: python -m rec.experiments.figures [--variant prereg]
Ghi artifacts/results/figures/*.png. PNG không mang metadata thời gian, nên chạy lại ra cùng file.
Màu theo bảng tham chiếu của skill dataviz: mỗi cấu hình giữ một màu cố định ở mọi hình.
"""
from __future__ import annotations

import sys

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from rec import config  # noqa: E402

COLORS = {"B1": "#2a78d6", "B2": "#eb6834", "Proposed": "#1baf7a"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
DAY_TYPES = {"clear": "Trời quang", "partly": "Mây vừa", "cloudy": "Nhiều mây"}
plt.rcParams.update({"font.family": ["DejaVu Sans"], "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": INK,
                     "font.size": 10})


def _save(fig, path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def _bars(ax, groups: list[str], series: dict[str, list[float]], fmt="{:.1%}") -> None:
    n = len(series)
    width = 0.8 / n
    for i, (name, vals) in enumerate(series.items()):
        xs = [g + (i - (n - 1) / 2) * width for g in range(len(groups))]
        bars = ax.bar(xs, vals, width * 0.92, color=COLORS[name], label=name, zorder=2)
        for b, v in zip(bars, vals):
            ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, v), xytext=(0, 2), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylim(0, max(max(v) for v in series.values()) * 1.3)  # chừa chỗ cho chú giải phía trên các cột
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))  # mốc tròn, nhãn không bị làm tròn sai
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", color=GRID, zorder=0)
    ax.legend(frameon=False, ncol=n, loc="upper left")


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    variant = argv[argv.index("--variant") + 1] if "--variant" in argv else "prereg"
    res = config.resolve_path("artifacts") / "results"
    out = res / "figures"
    out.mkdir(parents=True, exist_ok=True)
    e2b = pd.read_csv(res / variant / "e2b.csv")
    main_q = config.load("thresholds")["ceiling"]["false_review_main"]
    cfgs = list(COLORS)
    m = e2b[(e2b["q_ceiling"] == main_q) & e2b["config"].isin(cfgs)]

    # 1. LMAX theo số nguồn bị sửa k.
    fig, ax = plt.subplots(figsize=(7, 3.8))
    _bars(ax, [f"k = {k}" for k in (1, 2, 3)],
          {c: [float(m[(m.config == c) & (m.k == k)]["lmax"].iloc[0]) for k in (1, 2, 3)] for c in cfgs})
    ax.set_ylabel("LMAX (khai khống tối đa còn lọt)")
    ax.set_title(f"LMAX theo số nguồn tại chỗ bị sửa, trần REVIEW nhầm {main_q:.0%} ({variant})", loc="left",
                 fontsize=10.5)
    _save(fig, out / "lmax_by_k.png")

    # 2. LMAX ở k = 3 theo loại ngày.
    k3 = m[m.k == 3]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    _bars(ax, list(DAY_TYPES.values()),
          {c: [float(k3[k3.config == c][f"lmax_{t}"].iloc[0]) for t in DAY_TYPES] for c in ("B2", "Proposed")})
    ax.set_ylabel("LMAX ở k = 3")
    ax.set_title("Trần AI chặt hơn ở ngày quang, lỏng hơn nhiều ở ngày nhiều mây", loc="left", fontsize=10.5)
    _save(fig, out / "lmax_by_day_type.png")

    # 3. LMAX ở k = 3 theo tỉ lệ REVIEW nhầm của trần.
    sw = e2b[(e2b.k == 3) & e2b["config"].isin(["B2", "Proposed"])]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for c in ("B2", "Proposed"):
        d = sw[sw.config == c].sort_values("q_ceiling")
        ax.plot(d["q_ceiling"], d["lmax"], color=COLORS[c], lw=2, marker="o", ms=6, label=c, zorder=3)
    ax.axvline(main_q, color=MUTED, lw=0.8, ls="--")
    ax.annotate("mức chính", (main_q, ax.get_ylim()[1]), xytext=(4, -12), textcoords="offset points", color=MUTED,
                fontsize=8.5)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
    ax.set_xlabel("Tỉ lệ REVIEW nhầm của riêng trần (chọn trên val)")
    ax.set_ylabel("LMAX ở k = 3")
    ax.grid(axis="y", color=GRID, zorder=0)
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("LMAX theo tỉ lệ REVIEW nhầm chấp nhận được", loc="left", fontsize=10.5)
    _save(fig, out / "lmax_by_review_rate.png")

    # 4. Kiểm tra ngẫu nhiên p.
    ps = [c for c in e2b.columns if c.startswith("lmax_p") and c[6:].isdigit()]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    _bars(ax, [f"p = {int(c[6:])}%" for c in ps], {c: [float(k3[k3.config == c][p].iloc[0]) for p in ps] for c in cfgs})
    ax.set_ylabel("LMAX ở k = 3 sau kiểm tra")
    ax.set_title("Kiểm tra ngẫu nhiên p% số lô đã MINT (Production Auditor)", loc="left", fontsize=10.5)
    _save(fig, out / "lmax_random_check.png")
    print("đã ghi", sorted(p.name for p in out.glob("*.png")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
