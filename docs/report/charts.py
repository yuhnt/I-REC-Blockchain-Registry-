"""Vẽ biểu đồ cho báo cáo cuối kỳ từ kết quả đã chạy (không chạy lại thí nghiệm).

Chạy: python docs/report/charts.py <thư mục ảnh của báo cáo>
Đọc artifacts/results/{hybrid,error_analysis}/; ghi chart_lmax_k.png, chart_tradeoff.png, chart_day_type.png,
chart_inverter.png. Màu theo bảng categorical mặc định của skill dataviz, cố định theo cấu hình.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MultipleLocator  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "artifacts" / "results"
OUT = Path(sys.argv[1])

COLOR = {"B1": "#2a78d6", "B2": "#eb6834", "Proposed": "#1baf7a", "hybrid": "#eda100"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 11, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.titlesize": 12})


def pct(v: float) -> str:
    return f"{v * 100:.1f}%".replace(".", ",")


def _axes(ax, ylabel: str, step: float | None = None, decimals: int = 0) -> None:
    ax.set_ylabel(ylabel)
    if step:
        ax.yaxis.set_major_locator(MultipleLocator(step))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.{decimals}f}%".replace(".", ","))


def grouped(ax, groups: list[str], series: dict[str, list[float]], label_every: bool = True) -> None:
    n = len(series)
    w = 0.8 / n
    for i, (name, vals) in enumerate(series.items()):
        xs = [g + (i - (n - 1) / 2) * w for g in range(len(groups))]
        bars = ax.bar(xs, vals, w * 0.92, color=COLOR[name], label=name if name != "hybrid" else "hybrid (hậu kiểm)",
                      edgecolor="white", linewidth=1)
        if label_every:
            for b, v in zip(bars, vals):
                ax.annotate(pct(v), (b.get_x() + b.get_width() / 2, v), xytext=(0, 2), textcoords="offset points",
                            ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(groups)), groups)
    ax.legend(frameon=False, ncol=n, loc="upper left", fontsize=10)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    test = json.loads((RES / "hybrid" / "test.json").read_text(encoding="utf-8"))["test"]
    b1 = 0.15422  # B1 không có lớp B, LMAX bằng nhau ở mọi k (E2b, bản đăng ký trước)

    # 1. LMAX theo k
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    groups = ["k = 1", "k = 2", "k = 3"]
    series = {"B1": [b1] * 3}
    for c in ("B2", "Proposed", "hybrid"):
        series[c] = [test[c][f"lmax_k{k}"] for k in (1, 2, 3)]
    grouped(ax, groups, series)
    _axes(ax, "LMAX", 0.03)
    ax.set_ylim(0, 0.19)
    ax.set_xlabel("Số nguồn đo tại chỗ kẻ gian sửa được")
    fig.tight_layout()
    fig.savefig(OUT / "chart_lmax_k.png", dpi=220)
    plt.close(fig)

    # 2. Đánh đổi: LMAX (k = 3) theo tỉ lệ REVIEW nhầm đo trên test, mỗi điểm là một mức q chọn trên validation
    sw = pd.read_csv(RES / "hybrid" / "sweep_test.csv")
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for c in ("B2", "Proposed", "hybrid"):
        d = sw[sw["config"] == c].sort_values("review_rate")
        ax.plot(d["review_rate"], d["lmax_k3"], color=COLOR[c], linewidth=2, marker="o", markersize=6,
                markeredgecolor="white", markeredgewidth=1.2, label=c if c != "hybrid" else "hybrid (hậu kiểm)")
        last = d.iloc[-1]
        ax.annotate(c, (last["review_rate"], last["lmax_k3"]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=10, color=INK)
    _axes(ax, "LMAX ở k = 3", 0.005, 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    ax.set_xlabel("Tỉ lệ kỳ sản xuất trung thực bị REVIEW nhầm (đo trên test)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.legend(frameon=False, loc="upper right", fontsize=10)
    ax.set_xlim(0.02, 0.165)
    fig.tight_layout()
    fig.savefig(OUT / "chart_tradeoff.png", dpi=220)
    plt.close(fig)

    # 3. LMAX ở k = 3 theo loại ngày
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    types = [("clear", "Quang"), ("partly", "Mây vừa"), ("cloudy", "Nhiều mây")]
    series = {c: [test[c][f"lmax_k3_{t}"] for t, _ in types] for c in ("B2", "Proposed", "hybrid")}
    grouped(ax, [name for _, name in types], series)
    _axes(ax, "LMAX ở k = 3", 0.1)
    ax.set_ylim(0, 0.68)
    fig.tight_layout()
    fig.savefig(OUT / "chart_day_type.png", dpi=220)
    plt.close(fig)

    # 4. Theo tình trạng inverter (test): LMAX ở k = 3
    bo = pd.read_csv(RES / "error_analysis" / "by_outage.csv")
    bo = bo[bo["split"] == "test"].set_index("outage_kind")
    kinds = [("không", "Bình thường"), ("ngừng phát", "Ngừng phát thật"), ("ngừng ghi", "Ngừng ghi số liệu")]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    series = {c: [bo.loc[k, f"lmax_{c}"] for k, _ in kinds] for c in ("B2", "Proposed")}
    grouped(ax, [f"{name}\n({int(bo.loc[k, 'days'])} ngày)" for k, name in kinds], series)
    _axes(ax, "LMAX ở k = 3", 0.05)
    ax.set_ylim(0, 0.3)
    fig.tight_layout()
    fig.savefig(OUT / "chart_inverter.png", dpi=220)
    plt.close(fig)
    print("ok", OUT)


if __name__ == "__main__":
    main()
