# Kết quả E2 (RQ2, lớp B)

Tập test `testset-v1` gồm 638 lô test trung thực (514 ngày quang, 80 mây vừa, 44 nhiều mây), chế độ R2. Lớp B chạy off-chain qua `rec/gate/sim.py`. Mọi ngưỡng chỉ chọn trên val (321 lô).

- **Kết quả chính** là lần chạy đăng ký trước: đúng `spec-v1`, commit `b76c094`, lưu ở `artifacts/results/prereg/`.
- Cột **hậu kiểm** là biến thể `day_only`, được thêm vào sau khi đã thấy test. Lý do, tiêu chí chọn (ghi trước khi chạy) và kết quả chọn nằm ở [manifests/CHANGES.md](manifests/CHANGES.md).

Lệnh chạy lại:

```bash
.venv/Scripts/python -m rec.experiments.e2 --variant prereg
.venv/Scripts/python -m rec.experiments.e2 --select
.venv/Scripts/python -m rec.experiments.e2 --variant day_only
```

Số liệu dưới đây ở mức trần 4% (mức chính), trừ chỗ có ghi khác.

## 1. Tham số khớp trên train, ngưỡng chọn trên val

| | Đăng ký trước | Hậu kiểm `day_only` |
|---|---|---|
| η (công tơ / tổng inverter) | 0,9828 | 0,9828 |
| β, γ của E₃ | 657,16 Wh/(Wh/m²); −0,00652 /°C | như cũ |
| Hệ số pvlib | 0,8141 | như cũ |
| q của ngưỡng nhất quán (hợp 4 cờ ≤ 1%) | **1,000** (bằng giá trị lớn nhất trên val) | 0,9969 |
| τ₁₂ ngày / slot | 36,9% / 446% | 27,0% / — |
| τ₁₃ ngày / slot | 31,0% / 161% | 24,3% / — |
| τ trần ở 4%: B2 / Proposed / A1 / A2 | 26,9% / 8,1% / 5,7% / 1,1% | như cũ |

## 2. LMAX (kẻ gian thích nghi)

LMAX là lượng khai khống tối đa còn lọt, tính theo tỉ lệ của sản lượng thật.

| Cấu hình | k = 1 | k = 2 | k = 3 | k = 3, hậu kiểm |
|---|---|---|---|---|
| B1 | 15,42% | 15,42% | 15,42% | 15,42% |
| B2 | 10,76% | 11,38% | 12,33% | 12,35% |
| Proposed | 10,02% | 10,62% | 12,29% | 12,34% |
| A1 (O3 thay O4) | 9,40% | 9,98% | 13,65% | 13,70% |
| A2 (tuyến tính) | 10,20% | 10,81% | 12,66% | 12,67% |

Ở hậu kiểm, giá trị k = 1 của B2 và Proposed lần lượt là 10,43% và 9,69%.

**LMAX ở k = 3 theo loại ngày** (đăng ký trước):

| | Quang (514) | Mây vừa (80) | Nhiều mây (44) |
|---|---|---|---|
| B2 | 11,73% | 16,13% | 24,43% |
| Proposed | **10,69%** | 18,76% | 60,57% |

**LMAX ở k = 3 theo tỉ lệ REVIEW nhầm của trần** (đăng ký trước):

| q trần | 1% | 2% | 4% | 5% | 10% |
|---|---|---|---|---|---|
| B2 | 13,27% | 12,98% | 12,33% | 12,03% | 11,35% |
| Proposed | 12,83% | 12,59% | 12,29% | 11,89% | 11,03% |

## 3. Quy tắc kết luận (chốt trước, SPEC mục 8.1)

Hiệu LMAX(B2 − Proposed) ở k = 3, khoảng tin cậy 95% bootstrap theo ngày:

| q trần | Đăng ký trước | Hậu kiểm |
|---|---|---|
| 4% | +0,04 điểm, CI [−0,35; +0,36] | +0,01 điểm, CI [−0,39; +0,33] |
| 1% | **+0,44 điểm, CI [+0,13; +0,72]** | +0,43 điểm, CI [+0,11; +0,72] |

Kết quả này **không khớp dòng nào** trong bảng quy tắc đã chốt. Bảng chỉ có ba trường hợp: cả hai mức; chỉ ở 4% hoặc chỉ ở q lớn; không mức nào. Ở đây hiệu chỉ có ý nghĩa ở q = 1%, tức là khi trần chặt và ít REVIEW. Nhóm không sửa bảng sau khi đã thấy số. Cách ghi trung thực:

- H2 **không được ủng hộ ở mức chính 4%**.
- H2 có ý nghĩa ở q = 1%, nhưng độ lớn chỉ 0,44 điểm phần trăm trên mức lọt khoảng 13%.

**Vì sao lợi ích nhỏ:** Proposed chặt hơn B2 ở ngày quang (10,7% so với 11,7%), nhưng lỏng hơn nhiều ở ngày nhiều mây (60,6% so với 24,4%). Hai phần gần như bù trừ nhau. Đúng như H2 dự đoán, ưu thế nằm ở ngày quang, nhưng ở ngày nhiều mây mô hình AI kém trần vật lý.

## 4. Phía người trung thực (E2a)

Tỉ lệ REVIEW nhầm trên test và tỉ lệ MWh thật bị giữ tạm, ở mức trần 4%:

| | B2 | Proposed | A1 | A2 |
|---|---|---|---|---|
| REVIEW nhầm, đăng ký trước | 5,2% | 7,1% | 9,4% | 6,6% |
| REVIEW nhầm, hậu kiểm | 3,3% | 5,2% | 7,5% | 4,9% |
| MWh bị giữ tạm, đăng ký trước | 4,4% | 7,6% | 9,2% | 7,4% |

Mục tiêu đặt trên val là khoảng 5% (1% + 4%). Proposed vượt mục tiêu trên test: riêng nhóm ngày L2 bị REVIEW nhầm 10,1%. Đây là độ trôi giữa năm 2021 và 2022–2023.

## 5. Kẻ gian ngây thơ (E2a, đăng ký trước)

- **D4b, M2:** recall của B2 và Proposed gần bằng nhau. Ở k = 3 và mức tăng lớn, Proposed thấp hơn B2 2–3 điểm.
- **D5, ngày quang có inverter ngừng phát, k = 3:** Proposed bắt 27–29%, B2 16–19%.
- **D5, ngày nhiều mây, k = 3:** B2 bắt 97–99%, Proposed 91–93%.
- **M1** (tăng đột biến ngắn): B1 bắt 33–92%, B2 và Proposed thêm 3–15 điểm.
- **M3** (oracle lỗi, không phải gian lận): thiếu báo cáo luôn bị REVIEW. Khi giá trị bị kẹt hoặc lệch giờ, tỉ lệ REVIEW là 5–98%, tùy oracle và độ dài lỗi.
- **Ở hậu kiểm:** recall của M3 giảm từ khoảng 60% xuống 48%, của D5 từ 68% xuống 63%, của M1 từ 69% xuống 66%. OIR gần như không đổi.

Bảng đầy đủ theo từng tham số: `artifacts/results/<biến thể>/e2a.csv`.

## 6. Phát hiện về luật nhất quán và dữ liệu

- Ở đăng ký trước, luật nhất quán **gần như vô tác dụng**. Ngưỡng bằng giá trị lớn nhất trên val, nên LMAX ở k = 1 (10,0%) chỉ thấp hơn k = 3 (12,3%) một chút.
- Hậu kiểm bỏ thống kê theo slot. Kết quả chỉ là đổi mức cân bằng: REVIEW nhầm giảm, recall với M1, M3, D5 cũng giảm. Luật không chặt hơn đáng kể.
- **Nguyên nhân gốc** là đuôi của tỷ số theo ngày, đến từ các ngày `outage`. Trong những ngày đó, công tơ vẫn đo được điện trong khi inverter báo 0, tức là inverter ngừng ghi số liệu chứ không ngừng phát. Chi tiết ở CHANGES.md.
- Phát hiện này gắn với việc kiểm tay 50 ngày inverter ngừng phát, vẫn còn treo từ giai đoạn 2. Nếu nhóm đổi định nghĩa `outage` hoặc loại các ngày này thì phải sinh `testset-v2`, và mọi kết quả mới đều mang nhãn hậu kiểm.
- Luật nhất quán bị giới hạn bởi chất lượng dữ liệu inverter, chứ không bởi thiết kế một phía. Trên ngày không `outage` của val, p99 của tỷ số O1/O2 chỉ là 4,3%.
