"""Vẽ hai hình của Final Proposal: mô hình đề xuất (Hình 1) và sơ đồ thực nghiệm (Hình 2).

Chạy:  python docs/figures/make_figures.py [thư mục ra]
Mặc định ghi vào docs/figures/; mỗi hình một file PNG và một file SVG.
Toạ độ tính theo pixel ở dpi 100, trục y hướng xuống.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

plt.rcParams["font.family"] = ["DejaVu Sans", "Segoe UI Symbol", "Segoe UI"]
plt.rcParams["svg.fonttype"] = "none"

TEXT = "#1F2933"
MUTED = "#52606D"
HEAD = "#3E4C59"
LINE = "#3E4C59"

OWNER = ("#FDEBDD", "#D9822B")       # miền chủ dự án
INDEP = ("#E3F2E6", "#3F8F4E")       # miền độc lập
REGIME = ("#EDE4F6", "#7B5AA6")      # tùy chế độ (R1 độc lập, R2 chủ dự án)
OFFCHAIN = ("#E6EEF8", "#4A72B0")
ONCHAIN = ("#F2F3F5", "#5A6270")
PLAIN = ("#FFFFFF", "#9AA3AE")
REJECT = ("#F9E0E0", "#C0392B")
REVIEW = ("#FFF4D6", "#C89B1A")
MINT = ("#E3F2E6", "#3F8F4E")
SIM = ("#EFE8F7", "#7B5AA6")         # mô phỏng
MEASURE = ("#FFF4D6", "#C89B1A")     # đo lường

LINE_STEP = 19


def canvas(w: int, h: int):
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    return fig, ax


def text(ax, x, y, s, size=9.8, bold=False, color=TEXT, ha="left"):
    ax.text(x, y, s, fontsize=size, fontweight="bold" if bold else "normal", color=color, ha=ha, va="center")


def header(ax, x, y, s):
    # Nền trắng để mũi tên đi qua không cắt chữ.
    ax.text(x, y, s, fontsize=12.5, fontweight="bold", color=HEAD, ha="left", va="center", zorder=6,
            bbox=dict(fc="white", ec="none", pad=1.5))


def box(ax, x, y, w, h, colors, title=None, lines=(), ts=11, fs=9.6, ls="-", lw=1.6, center=False,
        title_color=TEXT, line_color=MUTED, top=22):
    fc, ec = colors
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=8",
                                fc=fc, ec=ec, lw=lw, ls=ls))
    hx, ha = (x + w / 2, "center") if center else (x + 14, "left")
    ty = y + top
    if title:
        text(ax, hx, ty, title, size=ts, bold=True, color=title_color, ha=ha)
        ty += LINE_STEP + 5
    for line in lines:
        text(ax, hx, ty, line, size=fs, color=line_color, ha=ha)
        ty += LINE_STEP


def arrow(ax, *pts, color=LINE, dashed=False, lw=1.5):
    ls = (0, (4, 3)) if dashed else "-"
    for a, b in zip(pts[:-2], pts[1:-1]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw, ls=ls, solid_capstyle="butt")
    ax.annotate("", xy=pts[-1], xytext=pts[-2],
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls, shrinkA=0, shrinkB=0,
                                mutation_scale=14))


def legend(ax, x, y, items):
    for colors, label, dashed in items:
        if dashed:
            ax.plot([x, x + 34], [y, y], color=colors[1], lw=1.6, ls=(0, (4, 3)))
            x += 44
        else:
            ax.add_patch(FancyBboxPatch((x, y - 8), 22, 16, boxstyle="round,pad=0,rounding_size=2",
                                        fc=colors[0], ec=colors[1], lw=1.2))
            x += 30
        text(ax, x, y, label, size=9.4, color=MUTED)
        x += 22 + 7.2 * len(label)


def figure_model(out: Path) -> None:
    W, H = 1500, 1985
    fig, ax = canvas(W, H)
    text(ax, 40, 34, "Mô hình đề xuất: từ thiết bị đo đến chứng chỉ và truy vết", size=19, bold=True)
    text(ax, 40, 66, "Một nhà máy PV (PVDAQ 2107) sau một điểm đấu nối lưới (CP). R1 = số đo đối soát (độc lập), "
                     "R2 = số đo do chủ dự án cung cấp. Lô = chứng chỉ của cả nhà máy trong một ngày.",
         size=10, color=MUTED)

    # Tầng 1
    header(ax, 40, 108, "TẦNG 1 · HIỆN TRƯỜNG")
    box(ax, 40, 126, 1030, 290, OWNER, ls=(0, (5, 3)), lw=1.4)
    text(ax, 58, 148, "Miền kiểm soát của chủ dự án (ở R2)", size=10.5, bold=True, color=OWNER[1])
    for i in range(6):
        bx = 62 + i * 166
        box(ax, bx, 166, 150, 66, ("#FFFFFF", OWNER[1]), title=f"Khối {i + 1}",
            lines=(f"inv{4 * i + 1:02d}–{4 * i + 4:02d}",), center=True, ts=10.5, top=24)
        ax.plot([bx + 75, bx + 75], [232, 258], color=LINE, lw=1.3)
    ax.plot([137, 967], [258, 258], color=LINE, lw=1.3)
    text(ax, 150, 276, "6 khối = 6 thiết bị", size=9.2, color=MUTED)
    arrow(ax, (555, 258), (555, 306))
    box(ax, 400, 306, 310, 82, REGIME, title="Công tơ doanh thu tại CP",
        lines=("R1: đơn vị điện lực · R2: chủ dự án",), center=True, ts=10.5)
    box(ax, 760, 306, 300, 82, ("#FFFFFF", OWNER[1]), title="Cảm biến tại chỗ",
        lines=("bức xạ POA và nhiệt độ (ghi °F)",), center=True, ts=10.5)
    box(ax, 1100, 126, 360, 290, INDEP, ls=(0, (5, 3)), lw=1.4)
    text(ax, 1118, 148, "Miền độc lập với chủ dự án", size=10.5, bold=True, color=INDEP[1])
    box(ax, 1135, 166, 310, 66, ("#FFFFFF", INDEP[1]), title="Vệ tinh NSRDB",
        lines=("GOES CONUS v4, 5 phút",), center=True, ts=10.5, top=24)
    for k, s in enumerate(("Ở R1, công tơ tại CP", "cũng thuộc miền độc lập", "(số đối soát, §8.5.1a)")):
        text(ax, 1118, 290 + k * LINE_STEP, s, size=9.4, color=MUTED)

    # Tầng 2
    header(ax, 40, 452, "TẦNG 2 · ORACLE  (mọi oracle báo ở mức CP, ký EIP-712, kèm số slot có số liệu và data_root)")
    box(ax, 40, 474, 310, 80, OWNER, title="O2 · Σ 24 inverter", lines=("mỗi inverter đếm một lần",),
        center=True, ts=10.8)
    box(ax, 400, 474, 310, 80, REGIME, title="O1 · Công tơ tại CP", lines=("R1: độc lập · R2: chủ dự án",),
        center=True, ts=10.8)
    box(ax, 760, 474, 310, 80, OWNER, title="O3 · POA + nhiệt độ", lines=("→ sản lượng kỳ vọng E₃",),
        center=True, ts=10.8)
    box(ax, 1120, 474, 340, 80, INDEP, title="O4 · NSRDB + pvlib", lines=("miền độc lập",), center=True, ts=10.8)
    arrow(ax, (137, 258), (137, 474))
    arrow(ax, (555, 388), (555, 474))
    arrow(ax, (910, 388), (910, 474))
    arrow(ax, (1290, 232), (1290, 474))

    # Tầng 3
    header(ax, 40, 590, "TẦNG 3 · LỚP B: KIỂM TRA SỐ LIỆU  (off-chain · chống khai khống · AI chỉ nhận O4)")
    box(ax, 40, 610, 1420, 245, OFFCHAIN, lw=1.4)
    box(ax, 60, 634, 280, 110, PLAIN, title="① Đủ báo cáo",
        lines=("thiếu, hoặc phủ < 95% slot", "ban ngày → REVIEW", "slot thiếu để trống, không điền 0"))
    box(ax, 360, 634, 720, 110, PLAIN, title="② Nhất quán, một phía",
        lines=("O1 so với η · ΣO2 và với E₃ (POA, nhiệt độ tại chỗ), ở mức ngày và mức 15 phút",
               "chỉ REVIEW khi O1 cao hơn quá ngưỡng · ngưỡng: 1% lô trung thực trên val",
               "O1 thấp hơn (inverter hỏng) không phải khai khống"))
    box(ax, 1100, 634, 340, 110, PLAIN, title="③ Trần sản lượng",
        lines=("B2: pvlib(NSRDB) × (1 + τ₄)", "Proposed: GB phân vị 0,95 × (1 + τ_C)",
               "ngưỡng: riêng trần 4% lô trung thực"))
    arrow(ax, (137, 554), (137, 634))
    arrow(ax, (555, 554), (555, 634))
    arrow(ax, (910, 554), (910, 634))
    arrow(ax, (1290, 554), (1290, 634))
    arrow(ax, (340, 689), (360, 689))
    arrow(ax, (1080, 689), (1100, 689))
    box(ax, 60, 762, 280, 78, PLAIN, title="Kho file off-chain",
        lines=("chuỗi 15 phút, tên file = data_root", "ai cũng tính lại hash để kiểm"), ts=10.3, fs=9.2)
    box(ax, 360, 762, 720, 78, PLAIN, title="Verdict có chữ ký (EIP-712)",
        lines=("cờ: thiếu báo cáo / không nhất quán / vượt trần · trần · reason code · hash mô hình",))
    arrow(ax, (1270, 744), (1270, 801), (1080, 801))

    # Tầng 4
    header(ax, 40, 892, "TẦNG 4 · LỚP A: BLOCKCHAIN DÙNG CHUNG CHO MỌI ISSUER  (chống double counting)")
    box(ax, 400, 910, 1060, 702, ONCHAIN, lw=1.4)
    text(ax, 420, 932, "EVM (Hardhat) · không mint đặc quyền · không nâng cấp", size=9.6, color=MUTED)
    box(ax, 420, 950, 520, 112, PLAIN, title="DeviceRegistry",
        lines=("thiết bị → CP, công suất, issuer, ngày đăng ký", "từ chối mã trùng (chặn D3 ngay khi đăng ký)",
               "chuyển đăng ký giữ nguyên mã (§16.3) · đóng đăng ký"))
    box(ax, 960, 950, 480, 112, PLAIN, title="Code Manager (§11)",
        lines=("khóa riêng, tách khỏi mọi issuer", "tạm khóa / rút chứng chỉ chưa retire",
               "mọi thao tác phát event kèm lý do · không mint"))
    box(ax, 420, 1080, 1020, 228, ("#FFFFFF", TEXT), lw=2.0)
    text(ax, 440, 1104, "DecisionGate — kiểm tra lần lượt", size=11.5, bold=True)
    text(ax, 1150, 1104, "chặn kịch bản", size=10, bold=True, color=MUTED)
    rows = (
        ("Đăng ký hợp lệ; kỳ phát hành ≤ 1 năm, trong một năm dương lịch (§8.2)", "kỳ sai chuẩn"),
        ("① Khóa (thiết bị, ngày) chưa phát hành; vòng đời", "D1, D2, D6"),
        ("② Ngân sách CP: Σ phát hành của mọi thiết bị sau CP ≤ O1", "D4, D5 (tất định ở R1)"),
        ("③ Công suất: mỗi 15 phút ≤ công suất AC × 0,25 h", "M1 lớn"),
        ("④ Verdict của lớp B có cờ", "M1, M2; D4b, D5 ở R2"),
    )
    for k, (rule, blocks) in enumerate(rows):
        yy = 1136 + k * 28
        text(ax, 440, yy, rule, size=10)
        text(ax, 1150, yy, blocks, size=10)
    text(ax, 440, 1286, "Ở R2, D4b/D5 buộc kẻ gian khai tăng O1 để qua ②, nên được xử lý như khai khống ở ④",
         size=9.2, color=MUTED)
    arrow(ax, (950, 840), (950, 1080))  # đi giữa DeviceRegistry và Code Manager
    arrow(ax, (680, 1062), (680, 1080))
    box(ax, 420, 1330, 320, 70, REJECT, title="REJECT", lines=("vi phạm lớp A",), center=True,
        title_color=REJECT[1], ts=11.5)
    box(ax, 770, 1330, 320, 70, REVIEW, title="REVIEW", lines=("cờ lớp B → hàng đợi auditor",), center=True,
        title_color="#8A6A0B", ts=11.5)
    box(ax, 1120, 1330, 320, 70, MINT, title="MINT", lines=("lượng = MWh yêu cầu",), center=True,
        title_color=MINT[1], ts=11.5)
    arrow(ax, (580, 1308), (580, 1330))
    arrow(ax, (930, 1308), (930, 1330))
    arrow(ax, (1280, 1308), (1280, 1330))
    box(ax, 420, 1428, 1020, 166, PLAIN, title="CertificateRegistry — ERC-1155 (đơn vị Wh)")
    for k, s in enumerate(("mint", "transfer", "retire")):
        px = 440 + k * 210
        ax.add_patch(FancyBboxPatch((px, 1468), 170, 36, boxstyle="round,pad=0,rounding_size=18",
                                    fc=MINT[0] if k == 0 else "#F2F3F5", ec=LINE, lw=1.2))
        text(ax, px + 85, 1486, s, size=10.5, ha="center")
        if k < 2:
            arrow(ax, (px + 170, 1486), (px + 210, 1486))
    for k, s in enumerate((
            "retire = burn + người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo; không sửa được (§10)",
            "chứng chỉ đã retire không chuyển nhượng hay retire lại được → chặn D6",
            "issuer không sửa được bản ghi; Code Manager luôn để lại event công khai → không sửa lặng lẽ được")):
        text(ax, 440, 1526 + k * LINE_STEP, s, size=9.6, color=MUTED)
    arrow(ax, (1280, 1400), (1280, 1428))

    box(ax, 40, 1080, 330, 120, PLAIN, title="Registrant", center=True,
        lines=("gửi qua Issuer A hoặc B", "yêu cầu phát hành", "(thiết bị, ngày, MWh)"))
    arrow(ax, (370, 1140), (420, 1140))
    box(ax, 40, 1330, 330, 150, REVIEW, title="Production Auditor", center=True,
        lines=("(§8.5.4, off-chain)", "phân xử lô REVIEW", "kiểm tra ngẫu nhiên p% số lô", "đã MINT → báo Code Manager"))
    arrow(ax, (930, 1400), (930, 1414), (370, 1414))

    # Tầng 5
    header(ax, 40, 1648, "TẦNG 5 · TRUY VẾT")
    box(ax, 400, 1668, 1060, 102, PLAIN, title="Dashboard provenance (Streamlit + web3.py)",
        lines=("Mỗi chứng chỉ: thiết bị → báo cáo O1–O4 (mở file theo data_root) → verdict + reason code → mint → "
               "transfer → retire",
               "Hàng đợi REVIEW kèm bằng chứng cho auditor · lý do REJECT · lineage completeness"))
    arrow(ax, (930, 1594), (930, 1668))
    text(ax, 944, 1630, "event log", size=9.2, color=MUTED)

    legend(ax, 40, 1812, [(OWNER, "miền chủ dự án", False), (INDEP, "miền độc lập", False),
                          (REGIME, "tùy chế độ (R1 độc lập, R2 chủ dự án)", False),
                          (OFFCHAIN, "off-chain (lớp B)", False), (ONCHAIN, "on-chain (lớp A)", False)])
    for k, s in enumerate((
            "D1 nộp lại · D2 kỳ chồng lấn · D3 hai issuer · D4 đổi mã thiết bị (a: đăng ký lại, b: nhà máy + khối inverter)"
            " · D5 dữ liệu lặp · D6 dùng trùng",
            "M1 tăng đột biến · M2 thông đồng (sửa k nguồn tại chỗ) · M3 oracle lỗi",
            "Oracle chạy off-chain, ký báo cáo (EIP-712). DecisionGate dùng O1 cho ngân sách CP và verdict của lớp B "
            "cho luật ④.")):
        text(ax, 40, 1856 + k * 26, s, size=9.6, color=MUTED)
    save(fig, out / "mo_hinh_de_xuat")


def figure_experiment(out: Path) -> None:
    W, H = 1850, 1620
    fig, ax = canvas(W, H)
    text(ax, 40, 40, "Sơ đồ thực nghiệm: từ dataset đến kết quả đánh giá", size=20, bold=True)
    text(ax, 40, 76, "Dữ liệu đo là dữ liệu thật. Thiết bị đăng ký, chủ dự án, kẻ gian và Production Auditor đều được "
                     "mô phỏng. Lô = chứng chỉ của cả nhà máy trong một ngày.", size=10.5, color=MUTED)

    header(ax, 40, 124, "BƯỚC 1 · DỮ LIỆU GỐC")
    box(ax, 40, 142, 870, 112, PLAIN, title="PVDAQ hệ 2107 (OEDI) · Arbuckle, CA · 893 kW DC", ts=11.5, fs=10,
        lines=("• Công tơ doanh thu, 15 phút → nguồn của O1",
               "• 24 inverter (công suất AC), 5 phút → nguồn của O2 (tổng ở mức CP)",
               "• Bức xạ POA và nhiệt độ tại chỗ (ghi °F), 5 phút → nguồn của O3 · nghiêng 25°, hướng 180°"))
    box(ax, 940, 142, 870, 112, PLAIN, title="NSRDB GOES CONUS v4 (NREL API)", ts=11.5, fs=10,
        lines=("• GHI, DNI, DHI, nhiệt độ, gió · 5 phút · 2018–2023",
               "• Tải tại tọa độ nhà máy → nguồn của O4",
               "• Không phụ thuộc thiết bị của chủ dự án"))
    arrow(ax, (475, 254), (475, 316))
    arrow(ax, (1375, 254), (1375, 316))

    header(ax, 40, 298, "BƯỚC 2 · TIỀN XỬ LÝ")
    box(ax, 40, 316, 1770, 160, PLAIN, title="Làm sạch và chuẩn hóa", ts=11.5, fs=10)
    for k, s in enumerate((
            "• Đổi giờ America/Los_Angeles → UTC; ngày luôn là ngày địa phương; công tơ dịch +15 phút",
            "• Gom về chu kỳ 15 phút; giữ ngày đủ ≥ 95% dữ liệu ban ngày → 2.058 ngày",
            "• Loại 73 ngày lỗi dữ liệu (bộ ghi báo 0, công tơ lệch tổng inverter > 50%) → 1.985 ngày",
            "• Nhiệt độ tại chỗ đổi °F → °C; slot thiếu để trống, không điền 0")):
        text(ax, 60, 366 + k * 26, s, size=10, color=MUTED)
    for k, s in enumerate((
            "• Gắn cờ: thiếu dữ liệu, đoạn treo, clipping 30 kW, ban đêm, inverter ngừng phát",
            "• Tạo 6 thiết bị (mỗi khối 4 inverter) sau một CP",
            "• POA từ NSRDB qua pvlib; loại ngày theo chỉ số trời quang (quang / mây vừa / nhiều mây)",
            "• Script: rec/data/days.py; danh sách ngày bị loại kèm lý do: configs/days_dropped.csv")):
        text(ax, 940, 366 + k * 26, s, size=10, color=MUTED)
    arrow(ax, (925, 476), (925, 532))

    header(ax, 40, 514, "BƯỚC 3 · CHIA THEO NĂM")
    for k, (label, colors) in enumerate((("Huấn luyện · 2018–2020 · 1.026 ngày", OFFCHAIN),
                                         ("Validation · 2021 · 321 ngày", OFFCHAIN),
                                         ("Test · 2022–2023 · 638 ngày", INDEP))):
        px = 40 + k * 605
        ax.add_patch(FancyBboxPatch((px, 532), 560, 64, boxstyle="round,pad=0,rounding_size=32",
                                    fc=colors[0], ec=colors[1], lw=1.6))
        text(ax, px + 280, 564, label, size=11.5, bold=True, ha="center")
        arrow(ax, (px + 280, 596), (px + 280, 662))

    header(ax, 40, 644, "BƯỚC 4 · GENERATOR")
    box(ax, 40, 662, 1770, 290, SIM, lw=1.5)
    text(ax, 60, 688, "Sinh dữ liệu có nhãn — config YAML + seed + hash; tập test sinh và khóa trước khi cài đặt AI "
                      "(mốc 2)", size=11.5, bold=True)
    box(ax, 62, 708, 560, 132, ("#FFFFFF", SIM[1]), title="① Dòng sự kiện hợp lệ", ts=11,
        lines=("đăng ký thiết bị (CP, công suất, issuer)", "phát hành theo ngày, transfer, retire",
               "L3 chuyển đăng ký (§16.3)", "L4 Production Group (§7.7)"))
    box(ax, 645, 708, 560, 132, ("#FFFFFF", SIM[1]), title="② Tầng tấn công", ts=11,
        lines=("D1–D6 · insider · M1 · M2 (sửa k nguồn) · M3", "tham số: f, σ, k, α, loại ngày đích",
               "chế độ R1 / R2 (ai giữ khóa của O1)", "mỗi ngày đủ điều kiện là một ca"))
    box(ax, 1228, 708, 560, 132, ("#FFFFFF", SIM[1]), title="③ Provenance → nhãn ẩn", ts=11, lw=2.0,
        lines=("mỗi yêu cầu ghi nguồn vật lý + khoảng 15 phút", "nhãn: hợp lệ / D / M / L",
               "MWh thật → để tính DCR, OIR"))
    text(ax, 60, 866, "Đầu ra cho hệ thống: dòng yêu cầu phát hành theo thời gian + báo cáo O1–O4 (đã bị sửa ở k nguồn "
                      "nếu có tấn công). Nhãn ẩn KHÔNG đi vào hệ thống.", size=9.8, color=MUTED)
    text(ax, 60, 894, "Kiểm tra trước khi dùng: mọi bản ghi qua cùng bước định dạng · dòng sạch có DCR = 0 · dấu vết "
                      "định dạng không phân biệt được (AUC ≈ 0,5)", size=9.8, color=MUTED)
    text(ax, 60, 920, "· xem tay 20 mẫu mỗi kịch bản · nhãn L5 (inverter ngừng phát) được 2 người kiểm tay 50 ngày",
         size=9.8, color=MUTED)

    header(ax, 40, 990, "BƯỚC 5 · HUẤN LUYỆN VÀ CHỌN NGƯỠNG")
    arrow(ax, (620, 952), (620, 1008))
    text(ax, 632, 976, "train + val", size=9.6, color=MUTED)
    box(ax, 40, 1008, 820, 225, OFFCHAIN, title="Chỉ dùng lô trung thực của train và val", ts=11.5, fs=10,
        lines=("1. Đặc trưng chỉ từ O4: POA NSRDB, chỉ số trời quang, nhiệt độ, gió,",
               "    ngày trong năm (không dùng O1–O3)",
               "2. Hồi quy phân vị gradient boosting (q = 0,95), học 2018–2020",
               "3. Trên 2021: ngưỡng nhất quán → 1% lô trung thực bị REVIEW nhầm",
               "4. τ_C (Proposed) và τ₄ (pvlib, B2) → riêng trần REVIEW nhầm 4%;",
               "    quét thêm 1%, 2%, 5%, 10% cho mục \"Tỉ lệ REVIEW nhầm\"",
               "5. Khóa mô hình và ngưỡng, ghi hash → dùng ở bước 6",
               "    (không học lại theo năm; báo cáo độ trôi trên test)"))

    header(ax, 900, 990, "BƯỚC 6 · CHẠY TRÊN TEST")
    arrow(ax, (1500, 952), (1500, 1008))
    text(ax, 1512, 976, "test", size=9.6, color=MUTED)
    box(ax, 900, 1008, 910, 225, INDEP, title="Cùng một luồng test chạy qua 4 cấu hình", ts=11.5)
    for k, (s, bold) in enumerate((("B0 · CSDL", False), ("B1 · 1 oracle", False), ("B2 · O1–O4", False),
                                   ("Proposed (+AI)", True))):
        px = 920 + k * 222
        ax.add_patch(FancyBboxPatch((px, 1050), 205, 42, boxstyle="round,pad=0,rounding_size=21",
                                    fc="#FFFFFF", ec=INDEP[1], lw=2.2 if bold else 1.3))
        text(ax, px + 102, 1071, s, size=10.5, bold=bold, ha="center")
    for k, s in enumerate((
            "Hardhat (chain cục bộ): DeviceRegistry, DecisionGate, CertificateRegistry, Code Manager —",
            "cùng contract cho B1, B2, Proposed; lớp B chạy off-chain, test parity với chain",
            "Production Auditor mô phỏng: phân xử lô REVIEW bằng nhãn thật;",
            "kiểm tra ngẫu nhiên p ∈ {0, 1%, 5%} số lô đã mint; phát hiện thì Code Manager rút",
            "E1 chạy ở R1 · E2 chạy ở R2 với k = 1…3 · 5 seed")):
        text(ax, 920, 1118 + k * 23, s, size=10, color=MUTED)
    arrow(ax, (860, 1120), (900, 1120))

    header(ax, 40, 1272, "BƯỚC 7 · ĐO VÀ BÁO CÁO")
    arrow(ax, (1355, 1233), (1355, 1290))
    text(ax, 1367, 1260, "quyết định, event log, gas report, thời điểm", size=9.6, color=MUTED)
    box(ax, 40, 1290, 1770, 206, MEASURE, title="So quyết định của từng cấu hình với nhãn ẩn", ts=11.5)
    for k, s in enumerate((
            "• Double counting: DCR, tỉ lệ lọt, exposure window, REJECT nhầm (L1, L3, L4)",
            "• Kẻ gian thích nghi: LMAX theo k, loại ngày và mức trần (chỉ số chính)",
            "• Phát hiện: precision (3 mức tỷ lệ gian lận), recall",
            "• Tỉ lệ REVIEW nhầm: trần ở 1%, 2%, 4%, 5%, 10% — quy tắc kết luận chốt trước")):
        text(ax, 60, 1340 + k * 25, s, size=10, color=MUTED)
    for k, s in enumerate((
            "• Khai khống: OIR · REVIEW nhầm theo L2, L5 · M3 · MWh thật bị giữ tạm",
            "• Kiểm tra ngẫu nhiên: OIR và LMAX khi p ∈ {0, 1%, 5%}",
            "• Chi phí: gas mỗi thao tác và mỗi MWh, độ trễ p50/p95",
            "• Truy vết: lineage completeness (dashboard, kho file theo data_root)")):
        text(ax, 940, 1340 + k * 25, s, size=10, color=MUTED)
    text(ax, 60, 1450, "5 seed · khoảng tin cậy 95% (bootstrap theo ngày) → bảng E1, E2a, E2b, kiểm tra ngẫu nhiên, E3, "
                       "ablation A1–A2 · mọi kết quả ghi kèm số ngày thật mà nó dựa vào", size=9.8, color=MUTED)
    arrow(ax, (1788, 774), (1832, 774), (1832, 1393), (1810, 1393), color=SIM[1], dashed=True)
    ax.text(1842, 1085, "nhãn ẩn (chỉ dùng để chấm điểm)", fontsize=9.4, color=SIM[1], rotation=-90,
            ha="center", va="center")

    legend(ax, 40, 1540, [(PLAIN, "dữ liệu thật", False), (SIM, "mô phỏng", False),
                          (OFFCHAIN, "huấn luyện (train/val)", False), (INDEP, "hệ thống được đánh giá (test)", False),
                          (MEASURE, "đo lường", False), (SIM, "nhãn ẩn", True)])
    text(ax, 40, 1582, "Ở bước 4, O1–O4 được \"đọc\" từ cột dữ liệu tương ứng; kẻ gian mô phỏng sửa giá trị trước khi "
                       "oracle ký và gửi đi.", size=9.6, color=MUTED)
    save(fig, out / "so_do_thuc_nghiem")


def save(fig, stem: Path) -> None:
    fig.savefig(stem.with_suffix(".png"), dpi=150, facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), facecolor="white")
    plt.close(fig)
    print("da ghi", stem.with_suffix(".png"), stem.with_suffix(".svg"))


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    figure_model(out)
    figure_experiment(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
