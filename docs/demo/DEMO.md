# Demo prototype và ảnh chụp

Tài liệu này ghi lại bản demo dùng cho báo cáo cuối: thống kê dữ liệu, các màn hình của từng vai, bản trên Sepolia, và cách chụp lại. Kết quả thí nghiệm E1–E3 ở [RESULTS.md](../RESULTS.md); kịch bản quay video ở [VIDEO.md](VIDEO.md).

Giao diện còn dùng chữ "lô" và "trần"; báo cáo dùng "kỳ sản xuất" và "ngưỡng MWh" cho cùng khái niệm.

## 1. Thống kê dữ liệu theo tập

Nhà máy PVDAQ 2107, sau khi loại 73 ngày lỗi dữ liệu. Sản lượng là số công tơ của cả nhà máy trong ngày.

| Tập | Năm | Số ngày | Quang | Mây vừa | Nhiều mây | MWh/ngày TB | Độ lệch chuẩn | Min | Max | Tổng MWh | % ngày inverter báo 0 | Công tơ / tổng inverter (trung vị) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Train | 2018–2020 | 1.026 | 804 | 132 | 90 | 3,71 | 1,28 | 0,03 | 6,01 | 3.808 | 58,9 | 0,9828 |
| Validation | 2021 | 321 | 247 | 39 | 35 | 3,84 | 1,45 | 0,20 | 5,83 | 1.233 | 49,8 | 0,9851 |
| Test | 2022–2023 | 638 | 514 | 80 | 44 | 4,01 | 1,27 | 0,18 | 6,16 | 2.556 | 42,0 | 0,9836 |

Loại ngày theo chỉ số trời quang của NSRDB: quang ≥ 0,8; mây vừa 0,5–0,8; nhiều mây < 0,5. "Inverter báo 0": ít nhất một inverter báo dưới 0,5 kW trong ≥ 2 giờ ban ngày, trong khi trung vị các inverter trên 5 kW. Sinh lại bảng: `python docs/demo/dataset_stats.py`.

## 2. Bản demo trên chain cục bộ

`python -m rec.deploy.demo` dựng node Hardhat và nạp:

- 20 ngày đầu của tập test (dòng hợp lệ seed 101, cấu hình Proposed): 120 yêu cầu được MINT, một phần được chuyển cho người mua và retire;
- D1 (nộp lại cùng thiết bị và ngày) → REJECT `KEY`; D4a (issuerB đăng ký thiết bị mới cùng điểm đấu nối, chép sản lượng) → REJECT `BUDGET`;
- 3 kỳ sản xuất bị REVIEW chờ auditor: ngày 2022-03-28 (M2, k = 1: công tơ khai tăng 45%, cờ không nhất quán), ngày 2022-05-03 (M2, k = 3: ba nguồn tại chỗ cùng tăng 20%, cờ vượt ngưỡng MWh), ngày 2022-01-31 (trung thực nhưng bị REVIEW nhầm);
- Code Manager tạm khóa một chứng chỉ rồi rút 10%, kèm lý do; issuer tự gọi `withdraw` thì bị revert.

Trang "Truy vết kịch bản" so điểm chặn kỳ vọng với event đọc từ chain: **8/8 kịch bản khớp**.

### Ảnh theo vai

| # | Màn hình | Ảnh | Thấy gì |
|---|---|---|---|
| 1 | Công khai · Tổng quan | [local_01_public_1](img/local_01_public_1.png) | 51,86 MWh đã phát hành, 15,98 MWh đã retire, 2 yêu cầu bị từ chối, 3 kỳ sản xuất bị REVIEW, 2 thao tác của Code Manager; biểu đồ công tơ so với lượng phát hành theo ngày |
| 2 | Công khai · Tra chứng chỉ | [local_02_public_2](img/local_02_public_2.png) | Mọi chứng chỉ, tokenId đầy đủ, trạng thái |
| 3 | Công khai · Nhật ký công khai | [local_03_public_3](img/local_03_public_3.png) | Mọi REJECT kèm lý do, mọi lần tạm khóa và rút |
| 4 | Công khai · Lineage completeness | [local_04_public_4](img/local_04_public_4.png) | Tỉ lệ chứng chỉ dựng lại đủ nguồn gốc từ event và kho file |
| 5 | Truy vết kịch bản | [local_05_cases](img/local_05_cases.png) | 8/8 kịch bản khớp kỳ vọng |
| 5a | · D1 | [local_05_cases_row1](img/local_05_cases_row1.png) | Event `IssueRejected(KEY)` |
| 5b | · D4a | [local_05_cases_row2](img/local_05_cases_row2.png) | Event `IssueRejected(BUDGET)` |
| 5c | · M2, k = 3 | [local_05_cases_row4](img/local_05_cases_row4.png) | Kỳ sản xuất bị REVIEW vì vượt ngưỡng MWh |
| 5d | · Ngày trung thực bị REVIEW nhầm | [local_05_cases_row5](img/local_05_cases_row5.png) | Cùng cờ vượt ngưỡng, nhưng số liệu thật |
| 6 | Nhà máy · Sản xuất theo ngày | [local_06_plant_1](img/local_06_plant_1.png) | Sản lượng công tơ 63,75 MWh, đã phát hành 51,86, đang giữ 24,12, đã chuyển 27,67, 18 yêu cầu chờ auditor |
| 6a | · Ngày 2022-01-01 | [local_06_plant_1_row0](img/local_06_plant_1_row0.png) | 6 thiết bị được phát hành; yêu cầu trùng của B1 bị từ chối (`key`), thiết bị giả X-D4a bị từ chối (`budget`); 4 báo cáo oracle với file gốc khớp `data_root`; biểu đồ công tơ so với inverter và bức xạ tại chỗ so với vệ tinh |
| 7 | Nhà máy · Chứng chỉ đang giữ | [local_07_plant_2](img/local_07_plant_2.png) | Chứng chỉ của nhà máy, chuyển nhượng hoặc retire |
| 8 | Nhà máy · Bị từ chối / bị giữ | [local_08_plant_3](img/local_08_plant_3.png) | Yêu cầu bị từ chối kèm lý do, yêu cầu chờ auditor |
| 9 | Nhà máy · Đã chuyển nhượng | [local_09_plant_4](img/local_09_plant_4.png) | Lịch sử chuyển cho người mua |
| 10 | Issuer | [local_10_issuer](img/local_10_issuer.png) | Yêu cầu bị giữ, nút gửi lại sau khi auditor duyệt, yêu cầu bị từ chối |
| 11 | Production Auditor · Chờ duyệt | [local_11_auditor_1](img/local_11_auditor_1.png) | 18 chứng chỉ của 3 kỳ sản xuất chờ phân xử |
| 11a | · Hồ sơ ngày 2022-05-03 | [local_11_auditor_1_row6](img/local_11_auditor_1_row6.png) | Reason code: công tơ 6.193 kWh so với ngưỡng 6.092 kWh (dự đoán 5.633 × 1,081); 4 báo cáo oracle; biểu đồ; nút "Duyệt cả lô" / "Bác cả lô" |
| 12–15 | Production Auditor · các mục khác | [12](img/local_12_auditor_2.png) · [13](img/local_13_auditor_3.png) · [14](img/local_14_auditor_4.png) · [15](img/local_15_auditor_5.png) | Mọi kỳ sản xuất đã gửi; yêu cầu bị từ chối; đã phân xử; chứng chỉ bị tạm khóa |
| 16–19 | Người mua | [16](img/local_16_buyer_1.png) · [17](img/local_17_buyer_2.png) · [18](img/local_18_buyer_3.png) · [19](img/local_19_buyer_4.png) | Chứng chỉ đang giữ; chứng chỉ trên hệ thống; lịch sử nhận; tuyên bố đã retire (người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo, theo I-REC §10) |

Ảnh minh họa cho báo cáo: nên chọn 5 (truy vết kịch bản), 6a (một ngày của nhà máy) và 11a (hồ sơ auditor).

## 3. Bản trên Sepolia

Deploy ngày 24/10/2026, 3 contract đã verify mã nguồn; 3 ngày dữ liệu demo. Địa chỉ, giao dịch và ghi chú vận hành ở [TESTNET.md](../TESTNET.md).

Dashboard đọc trực tiếp từ Sepolia (chọn "Sepolia (testnet)" ở thanh bên). Trang "Truy vết kịch bản" cho **6/6 kịch bản khớp** (stream, D1, D4a, M2 với k = 1, ngày trung thực bị REVIEW nhầm, Code Manager).

| # | Màn hình | Ảnh | Thấy gì |
|---|---|---|---|
| 1 | Công khai · Tổng quan | [sepolia_01_public_1](img/sepolia_01_public_1.png) | 7,74 MWh đã phát hành, 1,15 MWh đã retire, 2 kỳ sản xuất bị REVIEW, 2 thao tác của Code Manager; sidebar có link sang Etherscan |
| 2–4 | Công khai · các mục khác | [2](img/sepolia_02_public_2.png) · [3](img/sepolia_03_public_3.png) · [4](img/sepolia_04_public_4.png) | Tra chứng chỉ; nhật ký công khai; lineage completeness |
| 5 | Truy vết kịch bản | [sepolia_05_cases](img/sepolia_05_cases.png) | 6/6 khớp kỳ vọng |
| 6–9 | Nhà máy | [6](img/sepolia_06_plant_1.png) · [7](img/sepolia_07_plant_2.png) · [8](img/sepolia_08_plant_3.png) · [9](img/sepolia_09_plant_4.png) | Như bản cục bộ, trên 3 ngày dữ liệu |
| 10 | Issuer | [sepolia_10_issuer](img/sepolia_10_issuer.png) | Yêu cầu bị giữ và bị từ chối |
| 11–15 | Production Auditor | [11](img/sepolia_11_auditor_1.png) · [12](img/sepolia_12_auditor_2.png) · [13](img/sepolia_13_auditor_3.png) · [14](img/sepolia_14_auditor_4.png) · [15](img/sepolia_15_auditor_5.png) | Chứng chỉ chờ duyệt, mọi kỳ sản xuất đã gửi, yêu cầu bị từ chối, đã phân xử, bị tạm khóa |
| 16–19 | Người mua | [16](img/sepolia_16_buyer_1.png) · [17](img/sepolia_17_buyer_2.png) · [18](img/sepolia_18_buyer_3.png) · [19](img/sepolia_19_buyer_4.png) | buyer1 giữ 0,54 MWh |

Ô "Yêu cầu bị từ chối" ghi 34: ngoài D1 và D4a còn 32 yêu cầu bị REJECT `oracle` ở lần nạp thứ hai (chữ ký dùng nhầm chainId của Hardhat). Các event này vẫn nằm công khai trên chain, không xóa được; xem TESTNET.md, mục "Ghi chú vận hành".

Etherscan chặn trình duyệt tự động bằng trang kiểm tra, nên không có ảnh Etherscan ở đây. Link để mở tay (và để quay video) ở [VIDEO.md](VIDEO.md), bước 10.

## 4. Chụp lại

```bash
.venv/Scripts/python -m rec.deploy.demo --stop
.venv/Scripts/python -m rec.deploy.demo
.venv/Scripts/streamlit run dashboard/app.py --server.port 8501
python docs/demo/capture.py --prefix local
python docs/demo/capture.py --chain "Sepolia (testnet)" --prefix sepolia --no-details
# RPC công khai có thể ngắt giữa chừng; chụp lại phần còn thiếu: thêm --roles auditor,buyer
```

`capture.py` cần Playwright (`pip install playwright`) và dùng Chrome có sẵn trên máy. Ảnh ghi vào `docs/demo/img/`.

## 5. Logs nộp kèm

`artifacts/` không nằm trong git. `python docs/demo/pack_logs.py` đóng gói `artifacts/results/` (E1 kèm nhật ký quyết định, E2 đăng ký trước và hậu kiểm, E3, parity, hình, `run_all.log`) cùng `manifests/` vào `../final/logs/results-v1.zip` (193 file, khoảng 17 MB). Giải nén vào `source/` rồi chạy `python -m rec.manifest results-v1 --check` để kiểm mọi file khớp hash đã commit.

Trước khi đóng gói ngày 31/10/2026, parity được chạy lại đầy đủ (`python -m rec.experiments.parity`), vì bản cũ đã bị một lần test nhỏ ghi đè. Sau đó `rec.manifest results-v1 --check` báo khớp toàn bộ.
