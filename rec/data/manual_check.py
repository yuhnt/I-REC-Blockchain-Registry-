"""Bộ hình kiểm tay các ngày "inverter ngừng phát" (SPEC mục 5; scenarios.yaml `inverter_outage.manual_check_days`).

Câu hỏi cần trả lời cho mỗi ngày: inverter bị đánh dấu **ngừng phát thật** (công tơ giảm theo), hay chỉ
**ngừng ghi số liệu** (inverter báo 0 nhưng công tơ vẫn đo được phần điện đó)?

Mẫu 50 ngày, lấy trong mọi ngày `outage` của train, val và test:
- 30 ngày bốc ngẫu nhiên (seed cố định): đại diện, dùng để ước lượng tỉ lệ ngừng ghi;
- 20 ngày có công tơ / (η · tổng inverter) − 1 cao nhất trong số còn lại: để thấy rõ hiện tượng.

Chỉ số gợi ý `gap_ratio` = trung vị theo slot ngừng của (công tơ − η · tổng inverter) / (η · phần inverter ngừng lẽ
ra phát). Gần 0 nghĩa là ngừng thật, gần 1 nghĩa là ngừng ghi; âm nhiều thường là lỗi công tơ. Đây chỉ là gợi ý; người
kiểm quyết định bằng hình.

Chạy: python -m rec.data.manual_check
Ghi artifacts/manual_check/: <ngày>.png, index.html (xem cả bộ trong trình duyệt), sample.csv.
Phiếu để nhóm điền: docs/kiem_tay/phieu_kiem_tay.csv (commit kết quả đã điền).
"""
from __future__ import annotations

import base64
import html
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from rec import config  # noqa: E402
from rec.data.dataset import INVERTERS  # noqa: E402
from rec.timeutil import PLANT_TZ, day_date, slot_days  # noqa: E402

N_RANDOM, N_TAIL, SEED = 30, 20, 2026
# Màu theo bảng tham chiếu của skill dataviz (slot 1, 2, 7); nền và chữ trung tính.
METER, INV_SUM, OFF_INV = "#2a78d6", "#eb6834", "#6250d6"
GRID, MUTED, TEXT = "#e4e3df", "#9c9a92", "#0b0b0b"
plt.rcParams.update({"font.family": ["DejaVu Sans"], "axes.edgecolor": MUTED, "axes.labelcolor": TEXT,
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "axes.spines.top": False,
                     "axes.spines.right": False})


def day_frame(df15: pd.DataFrame, slots: pd.DataFrame, day: int) -> pd.DataFrame:
    idx = slots.index[slots["day"] == day]
    f = df15.loc[idx, INVERTERS + ["meter"]].clip(lower=0).copy()
    f["sun"] = slots.loc[idx, "sun"].to_numpy()
    return f


def diagnose(f: pd.DataFrame, eta: float, rule: dict) -> dict:
    """Inverter bị đánh dấu ngừng, các slot ngừng, và chỉ số gợi ý."""
    sun = f[f["sun"]]
    inv = sun[INVERTERS]
    others_on = inv.median(axis=1) > rule["others_median_kw"]
    off = inv.lt(rule["off_kw"]).mul(others_on, axis=0)
    flagged = [c for c in INVERTERS if off[c].sum() >= rule["min_slots"]]
    off_any = off[flagged].any(axis=1) if flagged else pd.Series(False, index=sun.index)
    median_kw = inv.median(axis=1)
    missing = (off[flagged].sum(axis=1) * median_kw * eta)[off_any]  # phần lẽ ra phát của inverter ngừng
    gap = (sun["meter"] - eta * inv.sum(axis=1))[off_any]
    day_ratio = float(sun["meter"].sum() / (eta * inv.sum(axis=1).sum()) - 1)
    ok = missing > 1.0  # bỏ slot sáng sớm, chiều muộn: phần lẽ ra phát quá nhỏ, tỷ số nhiễu
    gap_ratio = float(np.median(gap[ok] / missing[ok])) if ok.any() else np.nan
    return {"flagged": flagged, "off_slots": int(off_any.sum()), "off_mask": off_any, "gap_ratio": gap_ratio,
            "day_ratio": day_ratio}


def plot_day(f: pd.DataFrame, info: dict, eta: float, title: str, path) -> None:
    t = f.index.tz_convert(PLANT_TZ)
    sun = f["sun"].to_numpy()
    inv = f[INVERTERS]
    fig, axes = plt.subplots(3, 1, figsize=(10, 8.6), sharex=True, gridspec_kw={"height_ratios": [1.2, 0.8, 1.2]})
    off = info["off_mask"].reindex(f.index, fill_value=False).to_numpy()
    for ax in axes:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        # tô các slot mà inverter bị đánh dấu đang ngừng
        for start, end in _runs(off):
            ax.axvspan(t[start] - pd.Timedelta(minutes=15), t[end], color="#f1efe8", zorder=0, linewidth=0)

    ax = axes[0]
    ax.plot(t, f["meter"], color=METER, lw=2, label="Công tơ (O1)")
    ax.plot(t, eta * inv.sum(axis=1), color=INV_SUM, lw=2, label=f"η × tổng 24 inverter (η = {eta:.3f})")
    ax.set_ylabel("kW")
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.set_title(title, loc="left", fontsize=10.5, color=TEXT)

    ax = axes[1]
    median_kw = inv.median(axis=1).where(sun)
    n_off = inv[info["flagged"]].lt(0.5).sum(axis=1) if info["flagged"] else 0
    ax.plot(t, (f["meter"] - eta * inv.sum(axis=1)).where(sun), color=METER, lw=2,
            label="Công tơ − η × tổng inverter")
    ax.plot(t, (eta * n_off * median_kw).where(pd.Series(off, index=f.index)), color=OFF_INV, lw=2, ls="--",
            label="Phần inverter ngừng lẽ ra phát (trung vị × số inverter ngừng)")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_ylabel("kW")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=8.5, borderaxespad=0.2)

    ax = axes[2]
    for c in INVERTERS:
        if c not in info["flagged"]:
            ax.plot(t, inv[c], color="#c9c7c0", lw=0.8)
    for c in info["flagged"]:
        ax.plot(t, inv[c], color=OFF_INV, lw=2)
    ax.plot([], [], color="#c9c7c0", lw=0.8, label="Các inverter khác")
    ax.plot([], [], color=OFF_INV, lw=2, label="Bị đánh dấu ngừng: " + ", ".join(info["flagged"]))
    ax.set_ylabel("kW mỗi inverter")
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    sun_t = t[sun]
    ax.set_xlim(sun_t.min() - pd.Timedelta(minutes=30), sun_t.max() + pd.Timedelta(minutes=15))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=PLANT_TZ))
    ax.set_xlabel("Giờ địa phương (vùng tô = slot inverter bị đánh dấu đang ngừng)")
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        if not m and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    artifacts = config.resolve_path("artifacts")
    rule = config.load("scenarios")["inverter_outage"]
    df15 = pd.read_parquet(artifacts / "p2107_15m.parquet")
    slots = pd.read_parquet(artifacts / "slots.parquet")
    days = pd.read_parquet(artifacts / "days.parquet").set_index("day")
    train = days[days["split"] == "train"]
    eta = float((train["y_wh"] / train["o2_wh"]).median())  # công tơ / tổng inverter, khớp trên train

    cand = days[days["outage"]].copy()
    diag = {d: diagnose(day_frame(df15, slots, d), eta, rule) for d in cand.index}
    cand["day_ratio"] = [diag[d]["day_ratio"] for d in cand.index]
    rng = np.random.default_rng(SEED)
    rand = sorted(int(d) for d in rng.choice(cand.index.to_numpy(), size=N_RANDOM, replace=False))
    tail = [int(d) for d in cand.drop(index=rand).sort_values("day_ratio", ascending=False).index[:N_TAIL]]

    out = artifacts / "manual_check"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for stratum, chosen in (("ngau_nhien", rand), ("duoi_cao", tail)):
        for d in chosen:
            info, r = diag[d], days.loc[d]
            date = day_date(d).isoformat()
            title = (f"{date} · {r['split']} · {r['day_type']} · inverter ngừng: {', '.join(info['flagged']) or '—'}"
                     f" ({info['off_slots']} slot)\ncông tơ / (η·tổng inverter) − 1 cả ngày = {info['day_ratio']:+.1%}"
                     f" · gợi ý gap_ratio = {info['gap_ratio']:.2f} (≈ 0: ngừng thật, ≈ 1: ngừng ghi)")
            plot_day(day_frame(df15, slots, d), info, eta, title, out / f"{date}.png")
            rows.append({"ngay": date, "day": d, "nhom_mau": stratum, "split": r["split"], "loai_ngay": r["day_type"],
                         "inverter_ngung": " ".join(info["flagged"]), "so_slot_ngung": info["off_slots"],
                         "lech_ca_ngay": round(info["day_ratio"], 4), "goi_y_gap_ratio": round(info["gap_ratio"], 3)})
    sample = pd.DataFrame(rows)
    sample.to_csv(out / "sample.csv", index=False)

    form = config.ROOT / "docs" / "kiem_tay" / "phieu_kiem_tay.csv"
    form.parent.mkdir(parents=True, exist_ok=True)
    if not form.exists():  # không ghi đè phiếu nhóm đã điền
        sample.assign(nguoi_kiem_1="", ket_luan_1="", nguoi_kiem_2="", ket_luan_2="", ket_luan_chot="",
                      ghi_chu="").to_csv(form, index=False, encoding="utf-8-sig")
    _index_html(sample, out, eta, len(cand), len(days))
    print(f"η = {eta:.4f} | ngày outage: {len(cand)} / {len(days)} | mẫu: {len(sample)} → {out}")
    print(sample.groupby("nhom_mau")["goi_y_gap_ratio"].describe().round(2).to_string())
    return 0


def _index_html(sample: pd.DataFrame, out, eta: float, n_outage: int, n_days: int) -> None:
    cards = []
    for i, r in enumerate(sample.itertuples(), 1):
        img = base64.b64encode((out / f"{r.ngay}.png").read_bytes()).decode()
        cards.append(f'<section id="d{r.day}"><h2>{i}. {r.ngay} <small>{html.escape(r.nhom_mau)} · {r.split} · '
                     f'{r.loai_ngay} · {html.escape(r.inverter_ngung)} · gợi ý {r.goi_y_gap_ratio:.2f}</small></h2>'
                     f'<img alt="Ngày {r.ngay}" src="data:image/png;base64,{img}"></section>')
    page = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Kiểm tay inverter ngừng phát</title>
<style>
:root {{ --bg:#fcfcfb; --fg:#0b0b0b; --muted:#52514e; --line:#e4e3df; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1a1a19; --fg:#f0efec; --muted:#c3c2b7; --line:#3a3a37; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; margin:0 auto; max-width:1040px;
       padding:16px; }}
h1 {{ font-size:22px; }} h2 {{ font-size:16px; margin:28px 0 6px; }} small {{ color:var(--muted); font-weight:400; }}
img {{ width:100%; height:auto; border:1px solid var(--line); border-radius:6px; background:#fff; }}
li {{ margin:4px 0; }}
</style></head><body>
<h1>Kiểm tay các ngày "inverter ngừng phát"</h1>
<p>{n_outage} trên {n_days} ngày hợp lệ bị đánh dấu <code>outage</code>: ban ngày, một inverter báo dưới 0,5 kW trong
ít nhất 2 giờ, trong khi trung vị 24 inverter trên 5 kW. Mẫu gồm 50 ngày: 30 ngày bốc ngẫu nhiên (ước lượng tỉ lệ) và
20 ngày có công tơ cao hơn tổng inverter nhiều nhất (xem rõ hiện tượng). η = {eta:.4f}.</p>
<p><b>Cần quyết định mỗi ngày:</b></p>
<ul>
<li><b>ngung_that</b>: ở vùng tô, đường công tơ (xanh) <i>giảm theo</i> đường tổng inverter (cam); khung giữa nằm quanh 0.</li>
<li><b>ngung_ghi</b>: inverter báo 0 nhưng công tơ <i>không giảm</i>; khung giữa bám theo đường đứt (phần lẽ ra phát).</li>
<li><b>loi_cong_to</b>: công tơ thấp hơn hẳn tổng inverter, hoặc báo 0 khi inverter vẫn phát (lỗi nằm ở O1, không ở inverter).</li>
<li><b>khong_ro</b>: không phân biệt được (mây, clipping, nhiều inverter mất số liệu từng lúc…).</li>
</ul>
<p>Ghi vào <code>docs/kiem_tay/phieu_kiem_tay.csv</code>. Hai người kiểm độc lập: người 1 điền <code>nguoi_kiem_1</code>,
<code>ket_luan_1</code>; người 2 điền <code>nguoi_kiem_2</code>, <code>ket_luan_2</code>, không xem cột của người kia.
Sau đó bàn những ngày khác ý, điền <code>ket_luan_chot</code> và lý do ở <code>ghi_chu</code>.
Cột <code>goi_y_gap_ratio</code> chỉ là gợi ý của máy, đừng chép theo.</p>
{''.join(cards)}
</body></html>"""
    (out / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
