"""Hai sơ đồ cho mục Double counting của báo cáo: ba dạng double counting [1] và ví dụ 4,6 MWh.

Chạy: python docs/report/diagrams.py <thư mục ảnh của báo cáo>
Ghi dc_ba_dang.png và dc_vi_du.png. Dùng lại các hàm vẽ của docs/figures/make_figures.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "figures"))
from make_figures import (INDEP, MUTED, OFFCHAIN, ONCHAIN, OWNER, PLAIN, REJECT, REVIEW, arrow, box, canvas,  # noqa: E402
                          text)

OUT = Path(sys.argv[1])


def save(fig, name: str) -> None:
    fig.savefig(OUT / name, dpi=180, facecolor="white")


def three_forms() -> None:
    W, H = 1500, 600
    fig, ax = canvas(W, H)
    text(ax, 30, 30, "Ba dạng double counting theo Schneider và cộng sự [1], áp vào chứng chỉ năng lượng",
         size=15, bold=True)
    cols = [
        ("Double issuance (cấp trùng)", "Một lượng điện nhận hơn một chứng chỉ", REJECT,
         ("4,6 MWh điện", ("Chứng chỉ ở hệ thống A", "Chứng chỉ ở hệ thống B")),
         ("Ví dụ: nguy cơ GEC và I-REC cùng cấp", "cho một MWh ở Trung Quốc [3]"),
         ("Đề tài: D1–D4", "Chặn ở lúc đăng ký và phát hành")),
        ("Double use (dùng trùng)", "Một chứng chỉ được dùng hơn một lần", REVIEW,
         ("Một chứng chỉ", ("Dùng lần 1 (retire)", "Dùng hoặc bán lần 2")),
         ("Ví dụ: Hungary bán lại tín chỉ CER", "đã được nộp, 2010 [21]"),
         ("Đề tài: D5", "Chặn bằng retire = burn")),
        ("Double claiming (tuyên bố trùng)", "Hai bên cùng nhận một lợi ích", ONCHAIN,
         ("Một chứng chỉ", ("Bên mua chứng chỉ|tuyên bố dùng điện tái tạo", "Bên dùng điện tại chỗ|cũng tuyên bố")),
         ("Ví dụ: GO của Iceland bị dừng", "xuất khẩu, 2023 [22]"),
         ("Ngoài phạm vi đề tài", "Xảy ra ngoài registry")),
    ]
    for i, (title, sub, colors, (src, outs), ex, scope) in enumerate(cols):
        x = 30 + i * 490
        box(ax, x, 62, 460, 510, (colors[0], colors[1]), title=title, lines=(sub,), ts=13, fs=10.5, top=26)
        box(ax, x + 130, 140, 200, 50, PLAIN, title=src, center=True, ts=11, top=25)
        for k, o in enumerate(outs):
            ox = x + 18 + k * 222
            parts = tuple(o.split("|"))
            box(ax, ox, 250, 204, 56, PLAIN, lines=parts, center=True, fs=9.4, top=28 if len(parts) == 1 else 19,
                line_color="#1F2933")
            arrow(ax, (x + 230, 190), (x + 230, 220), (ox + 102, 220), (ox + 102, 250))
        box(ax, x + 18, 340, 424, 84, PLAIN, lines=ex, fs=10.3, top=30)
        box(ax, x + 18, 450, 424, 96, PLAIN, title=scope[0], lines=(scope[1],), ts=11.5, fs=10.3, top=32)
    save(fig, "dc_ba_dang.png")


def example() -> None:
    W, H = 1500, 720
    fig, ax = canvas(W, H)
    text(ax, 30, 30, "Ví dụ: một ngày nhà máy phát 4,6 MWh (số công tơ tại điểm đấu nối)", size=15, bold=True)

    # Trái: registry tách biệt
    box(ax, 30, 62, 700, 630, OWNER, title="Hiện nay: mỗi issuer một registry", ts=13, top=26)
    box(ax, 270, 110, 220, 56, PLAIN, title="Nhà máy", lines=("công tơ: 4,6 MWh",), center=True, ts=11, fs=10, top=20)
    for k, (name, l1, l2) in enumerate((("Issuer A", "thiết bị mã X", "xin 4,6 MWh"),
                                        ("Issuer B", "cùng thiết bị, mã mới Y", "xin 4,6 MWh"))):
        x = 60 + k * 340
        box(ax, x, 220, 300, 76, PLAIN, title=name, lines=(l1 + " · " + l2,), center=True, ts=11, fs=10, top=24)
        arrow(ax, (380, 166), (380, 192), (x + 150, 192), (x + 150, 220))
        box(ax, x, 340, 300, 110, OFFCHAIN, title=f"CSDL của {name}", center=True, ts=11, fs=10, top=24,
            lines=("chỉ thấy bản ghi của mình", "4,6 ≤ 4,6 → hợp lệ", "cấp 4,6 MWh"))
        arrow(ax, (x + 150, 296), (x + 150, 340))
        arrow(ax, (x + 150, 450), (x + 150, 500), (380, 500), (380, 530))
    box(ax, 110, 530, 540, 96, REJECT, title="9,2 MWh chứng chỉ cho 4,6 MWh điện", center=True, ts=13, fs=10.3, top=30,
        title_color=REJECT[1], lines=("Chỉ lộ khi hai issuer đối soát với nhau (7 hoặc 30 ngày sau)",))
    text(ax, 60, 652, "Kiểm tra hiện có: số serial trong từng registry, khai báo của bên đăng ký,", size=9.6, color=MUTED)
    text(ax, 60, 672, "issuer tra thủ công các registry đã biết (I-REC §7.4.3)", size=9.6, color=MUTED)

    # Phải: sổ cái dùng chung
    box(ax, 770, 62, 700, 630, INDEP, title="Đề tài: mọi issuer ghi vào một sổ cái dùng chung", ts=13, top=26)
    box(ax, 800, 110, 300, 76, PLAIN, title="Yêu cầu 1 (Issuer A)", center=True, ts=11, fs=10, top=24,
        lines=("thiết bị X, ngày d, 4,6 MWh",))
    box(ax, 1140, 110, 300, 76, PLAIN, title="Yêu cầu 2 (Issuer B)", center=True, ts=11, fs=10, top=24,
        lines=("bản trùng, 4,6 MWh",))
    box(ax, 800, 230, 300, 96, PLAIN, title="MINT 4,6 MWh", center=True, ts=12, fs=10, top=28, title_color=INDEP[1],
        lines=("ngân sách của điểm đấu nối", "trong ngày d còn 0"))
    arrow(ax, (950, 186), (950, 230))
    arrow(ax, (1290, 186), (1290, 230))
    box(ax, 1140, 230, 300, 26, ("#FFFFFF", "#FFFFFF"), lines=("contract kiểm ba luật:",), fs=10.3, top=13,
        line_color="#1F2933")
    rules = (("① Mã thiết bị đã đăng ký?", "cùng mã X → từ chối lúc đăng ký (D3)"),
             ("② (thiết bị, ngày) đã có chứng chỉ?", "nộp lại, hoặc kỳ dài phủ lên → REJECT (D1, D2)"),
             ("③ Tổng sau điểm đấu nối ≤ số công tơ?", "mã mới Y: 4,6 + 4,6 = 9,2 > 4,6 → REJECT (D4)"))
    for k, (q, a) in enumerate(rules):
        y = 268 + k * 84
        box(ax, 1120, y, 330, 72, PLAIN, title=q, lines=(a,), ts=10, fs=9.2, top=22)
    box(ax, 800, 380, 300, 96, PLAIN, title="Dùng xong: retire", center=True, ts=11, fs=10, top=26,
        lines=("chứng chỉ bị burn,", "không chuyển hay retire lại được (D5)"))
    arrow(ax, (950, 326), (950, 380))
    arrow(ax, (950, 476), (950, 530))
    arrow(ax, (1285, 508), (1285, 530))
    box(ax, 850, 530, 540, 96, INDEP, title="4,6 MWh chứng chỉ cho 4,6 MWh điện", center=True, ts=13, fs=10.3, top=30,
        title_color=INDEP[1], lines=("Bản trùng bị từ chối ngay lúc nộp; lý do được ghi công khai",))
    text(ax, 800, 660, "Ba luật chạy trên bản ghi của mọi issuer, nên bản trùng nộp qua issuer khác vẫn bị thấy",
         size=9.6, color=MUTED)
    save(fig, "dc_vi_du.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    three_forms()
    example()
    print("ok", OUT)
