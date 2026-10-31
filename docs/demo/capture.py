"""Chụp ảnh dashboard cho báo cáo (docs/demo/DEMO.md): mỗi vai, mỗi mục một ảnh.

Cần: chain demo đang chạy (python -m rec.deploy.demo), dashboard ở cổng 8501 (streamlit run dashboard/app.py),
và Playwright (pip install playwright; dùng Chrome có sẵn trên máy).
Chạy: python docs/demo/capture.py [--url http://localhost:8501] [--chain "Sepolia (testnet)"] [--prefix sepolia]
                                  [--no-details] [--roles auditor,buyer]
--roles chỉ chụp các vai đã nêu (theo tên trong SLUG), giữ nguyên số thứ tự ảnh; dùng khi RPC công khai ngắt giữa chừng.
Ghi PNG vào docs/demo/img/.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parent / "img"

# (vai trên thanh bên, các mục trong trang; None = trang không chia mục)
PAGES = [
    ("Công khai", ["Tổng quan", "Tra chứng chỉ", "Nhật ký công khai", "Lineage completeness"]),
    ("Truy vết kịch bản", None),
    ("Nhà máy", ["Sản xuất theo ngày", "Chứng chỉ đang giữ", "Bị từ chối / bị giữ", "Đã chuyển nhượng"]),
    ("Issuer", None),
    ("Production Auditor", ["Chứng chỉ chờ duyệt", "Mọi lô đã gửi", "Yêu cầu bị từ chối", "Đã phân xử",
                            "Chứng chỉ bị tạm khóa"]),
    ("Người mua", ["Chứng chỉ đang giữ", "Chứng chỉ trên hệ thống", "Lịch sử nhận", "Tuyên bố đã retire"]),
]
# Chụp thêm phần chi tiết sau khi bấm vào dòng thứ i (đếm từ 0) của bảng đầu tiên trong mục.
DETAILS = {
    ("Truy vết kịch bản", None): [1, 2, 4, 5],          # D1, D4a, M2-k3, honest (REVIEW nhầm)
    ("Nhà máy", "Sản xuất theo ngày"): [0],
    ("Production Auditor", "Chứng chỉ chờ duyệt"): [6],  # một yêu cầu của lô M2-k3 (vượt ngưỡng)
}
SLUG = {"Công khai": "public", "Truy vết kịch bản": "cases", "Nhà máy": "plant", "Issuer": "issuer",
        "Production Auditor": "auditor", "Người mua": "buyer"}


def _arg(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def settle(page: Page, extra_ms: int = 1500) -> None:
    """Chờ Streamlit chạy xong lượt tải lại (biểu tượng 'Running' biến mất) rồi chờ thêm cho biểu đồ vẽ."""
    page.wait_for_timeout(600)
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=3_600_000)  # Sepolia lần đầu có thể đọc log rất lâu
    page.wait_for_timeout(extra_ms)


def pick_radio(page: Page, scope: str, label: str) -> None:
    page.locator(f'{scope} [role="radiogroup"] label').filter(has_text=label).first.click()
    settle(page)


def shoot(page: Page, path: Path) -> None:
    """Streamlit cuộn bên trong khung chính, nên giãn cửa sổ theo chiều cao nội dung rồi mới chụp."""
    h = page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
    page.set_viewport_size({"width": 1440, "height": max(900, min(int(h) + 40, 6000))})
    page.wait_for_timeout(1200)
    page.screenshot(path=str(path), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(400)


def click_row(page: Page, i: int) -> None:
    """Bấm ô chọn của dòng i trong bảng đầu tiên (bảng của Streamlit vẽ trên canvas, nên bấm theo tọa độ)."""
    grid = page.locator('[data-testid="stMain"] [data-testid="stDataFrame"]').first
    grid.scroll_into_view_if_needed()
    box = grid.bounding_box()
    page.mouse.click(box["x"] + 16, box["y"] + 36 + 35 * i + 17)
    settle(page, 2500)


def expand_evidence(page: Page) -> None:
    ev = page.locator('[data-testid="stExpander"] summary').filter(has_text="Bằng chứng của lô")
    if ev.count():
        ev.first.click()
        settle(page, 2500)


def main() -> int:
    url, chain, prefix = _arg("--url", "http://localhost:8501"), _arg("--chain", ""), _arg("--prefix", "local")
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.goto(url)
        page.wait_for_selector('[data-testid="stSidebar"]', timeout=120_000)
        settle(page, 3000)
        if chain:
            page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]').first.click()
            page.get_by_role("option", name=chain).click()
            settle(page, 5000)
        only = set(_arg("--roles", "").split(",")) - {""}
        for role, sections in PAGES:
            if only and SLUG[role] not in only:
                n += len(sections or [None])
                continue
            pick_radio(page, '[data-testid="stSidebar"]', role)
            for sec in sections or [None]:
                if sec:
                    pick_radio(page, '[data-testid="stMain"]', sec)
                n += 1
                base = f"{prefix}_{n:02d}_{SLUG[role]}" + (f"_{sections.index(sec) + 1}" if sec else "")
                shoot(page, OUT / f"{base}.png")
                print(f"{base}.png", "|", role, "|", sec or "")
                for i in ([] if "--no-details" in sys.argv else DETAILS.get((role, sec), [])):
                    click_row(page, i)
                    expand_evidence(page)
                    shoot(page, OUT / f"{base}_row{i}.png")
                    print(f"{base}_row{i}.png", "|", role, "|", sec or "", "| dòng", i)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
