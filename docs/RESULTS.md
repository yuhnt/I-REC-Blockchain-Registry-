# Kết quả thí nghiệm

- [E1 (RQ1, lớp A)](#e1-rq1-lớp-a)
- [E2 (RQ2, lớp B)](#e2-rq2-lớp-b)
- [Parity chain – mô phỏng](#parity-chain--mô-phỏng-off-chain)
- [E3 (chi phí và truy vết)](#e3-chi-phí-và-truy-vết)
- [Bổ sung sau nhận xét giữa kỳ](#bổ-sung-sau-nhận-xét-giữa-kỳ)

# E2 (RQ2, lớp B)

Tập test `testset-v1` gồm 638 lô test trung thực (514 ngày quang, 80 mây vừa, 44 nhiều mây), chế độ R2. Lớp B chạy off-chain qua `rec/gate/sim.py`. Mọi ngưỡng chỉ chọn trên val (321 lô).

- **Kết quả chính** là lần chạy đăng ký trước: đúng `spec-v1`, commit `b76c094`, lưu ở `artifacts/results/prereg/`.
- Cột **hậu kiểm** là biến thể `day_only`, được thêm vào sau khi đã thấy test. Lý do, tiêu chí chọn (ghi trước khi chạy) và kết quả chọn nằm ở [manifests/CHANGES.md](../manifests/CHANGES.md).

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
| q của ngưỡng nhất quán (hợp 4 cờ ≤ 1%) | **1,0** (bằng giá trị lớn nhất trên val) | 0,9969 |
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
- **D5, ngày quang có inverter báo 0, k = 3:** Proposed bắt 27–29%, B2 16–19%.
- **D5, ngày nhiều mây, k = 3:** B2 bắt 97–99%, Proposed 91–93%.
- **M1** (tăng đột biến ngắn): B1 bắt 33–92%, B2 và Proposed thêm 3–15 điểm.
- **M3** (oracle lỗi, không phải gian lận): thiếu báo cáo luôn bị REVIEW. Khi giá trị bị kẹt hoặc lệch giờ, tỉ lệ REVIEW là 5–98%, tùy oracle và độ dài lỗi.
- **Ở hậu kiểm:** recall của M3 giảm từ khoảng 60% xuống 48%, của D5 từ 68% xuống 63%, của M1 từ 69% xuống 66%. OIR gần như không đổi.

Bảng đầy đủ theo từng tham số: `artifacts/results/<biến thể>/e2a.csv`.

## 6. Phát hiện về luật nhất quán và dữ liệu

- Ở đăng ký trước, luật nhất quán **gần như vô tác dụng**. Ngưỡng bằng giá trị lớn nhất trên val, nên LMAX ở k = 1 (10,0%) chỉ thấp hơn k = 3 (12,3%) một chút.
- Hậu kiểm bỏ thống kê theo slot. Kết quả chỉ là đổi mức cân bằng: REVIEW nhầm giảm, recall với M1, M3, D5 cũng giảm. Luật không chặt hơn đáng kể.
- **Nguyên nhân gốc** là đuôi của tỉ số theo ngày, đến từ các ngày "inverter báo 0" (`outage`). Nhóm này gồm hai hiện tượng thật:
  - **ngừng phát thật**, chiếm đa số: pin hoặc inverter tắt, công tơ giảm theo, tỉ số không đổi, không gây REVIEW nhầm. Ví dụ 28/7/2022: năm inverter gần như không phát khoảng 10 giờ, công tơ / (η · tổng inverter) − 1 = −0,8%;
  - **ngừng ghi số liệu**, chiếm thiểu số: inverter báo 0 nhưng công tơ vẫn đo được điện. Chính nhóm này tạo ra đuôi. Ví dụ 27/8/2021.
- **Giữ nguyên dữ liệu** (CHANGES, "Quyết định về các ngày inverter báo 0"). Cả hai hiện tượng đều là ngày trung thực mà registry thật sẽ gặp; loại chúng đi sẽ làm luật trông chặt hơn thực tế.
- **Giới hạn cần nêu trong báo cáo:** luật nhất quán bị chặn bởi chất lượng ghi số liệu của inverter, chứ không bởi thiết kế một phía. Trên ngày không `outage` của val, p99 của tỉ số O1/O2 chỉ là 4,3%, nhưng tính cả các ngày ngừng ghi thì dung sai ở mức 1% REVIEW nhầm là khoảng 27–37%.
- Hướng phát triển: hiệu chỉnh O2 theo số inverter đang báo số (CHANGES, cùng mục).

## 7. Kiểm tra ngẫu nhiên p (SPEC mục 8.2, đăng ký trước, trần 4%)

Production Auditor bốc thăm p% số lô đã MINT, lúc 12:00 ngày d + 2 (`rec/gate/auditor.py`). Lô gian lận bị bốc trúng thì Code Manager rút phần chứng chỉ chưa retire.

| | p = 0 | p = 1% | p = 5% |
|---|---|---|---|
| LMAX k = 3, B1 | 15,42% | 15,31% | 14,63% |
| LMAX k = 3, B2 | 12,33% | 12,23% | 11,64% |
| LMAX k = 3, Proposed | 12,29% | 12,19% | 11,59% |
| LMAX k = 1, Proposed | 10,02% | 9,92% | 9,42% |

OIR của kẻ gian ngây thơ cũng giảm khoảng p lần, ví dụ M2 với Proposed: 2,01% → 1,90% ở p = 5%. Mô phỏng gần trùng công thức (1 − p) · LMAX, vì theo vòng đời của dòng hợp lệ, chứng chỉ gần như chưa kịp retire trước lần kiểm.

**Trả lời câu hỏi của SPEC mục 8.2:**
- Kiểm tra 5% số lô chỉ bù khoảng 5% phần lọt.
- Lớp B (B1 → B2) bù 20% ở k = 3 (15,4% → 12,3%) và khoảng 30–35% ở k = 1.
- Vậy với mức kiểm tra khả thi, lớp B vẫn đáng làm. Hai cơ chế cộng dồn được.
- Đề tài chưa mô hình hóa hình phạt khi bị bắt, nên chưa tính được tác dụng răn đe của việc kiểm tra.

## 8. Hình

`python -m rec.experiments.figures` ghi vào `artifacts/results/figures/`:
- `lmax_by_k.png`: LMAX theo k;
- `lmax_by_day_type.png`: LMAX ở k = 3 theo loại ngày;
- `lmax_by_review_rate.png`: LMAX theo tỉ lệ REVIEW nhầm của trần;
- `lmax_random_check.png`: LMAX theo p.

# E1 (RQ1, lớp A)

Chế độ R1: O1 do điện lực ký nên kẻ gian không sửa được. Mỗi kịch bản D1–D6 và insider chèn vào 60 ngày test ngẫu nhiên × 5 seed (101–105), tức 300 ca. Mỗi ca chạy chồng lên dòng hợp lệ 638 ngày (6 thiết bị, có L3). Dòng Production Group (L4) chạy riêng. Cùng một dòng sự kiện được chạy qua ba backend:

```bash
.venv/Scripts/python -m rec.experiments.e1 --backends b0_separate,b0_shared --run-only
.venv/Scripts/python -m rec.experiments.e1 --backends chain --seeds 101 --run-only --port 8545   # mỗi seed một cổng
.venv/Scripts/python -m rec.experiments.e1 --metrics-only
```

Kết quả ghi ở `artifacts/results/e1/` (`summary.csv`, `cases.csv`, `false_reject.csv`, `gas_s*.csv`, nhật ký quyết định trong `decisions/`).

## 1. Điểm chặn và tỉ lệ lọt

| Kịch bản | b0_separate (mỗi issuer một CSDL) | b0_shared (CSDL dùng chung) | chain |
|---|---|---|---|
| D1 nộp lại | 0/300 lọt (khóa) | 0/300 (khóa) | 0/300 (khóa) |
| D2 kỳ 7/30 ngày | 0/300 (khóa) | 0/300 (khóa) | 0/300 (khóa) |
| D3 đăng ký lại mã ở issuer khác | **178/300 lọt**, tỉ lệ lọt 58% | 0/300 (bước đăng ký) | 0/300 (bước đăng ký) |
| D4a thiết bị mới cùng CP, chép dữ liệu | **299/300 lọt**, 100% | 0/300 (ngân sách CP) | 0/300 (ngân sách CP) |
| D4b thiết bị mới gồm tỉ lệ f các khối | **261/300 lọt**, 74% | 0/300 (ngân sách CP) | 0/300 (ngân sách CP) |
| D5 thay ngày Y bằng dữ liệu ngày X | **128/300 lọt**, 9% | 0/300 (ngân sách CP) | 0/300 (ngân sách CP) |
| D6 retire lại, chuyển sau retire | 0/300 (vòng đời) | 0/300 (vòng đời) | 0/300 (vòng đời) |
| Insider sửa / xóa / phát hành lại | **300/300 thành công, không dấu vết: fail** | **300/300, không dấu vết: fail** | 0/300 (không có hàm quản trị): **pass** |

- Tỉ lệ lọt = Wh vượt đã MINT / Wh vượt đã nộp, tính theo lô (SPEC mục 4.2; CHANGES, giai đoạn 3, mục 3).
- **DCR của b0_separate:** D3 0,90%, D4a 1,56%, D4b 3,28%, D5 0,40%, insider 1,06%. Tỉ lệ tấn công trong dòng là 1,5–4,4% Wh.
- D3 trên b0_separate có 122 ca bị REJECT `not_registered`. Đây là do generator đặt thời điểm đăng ký lại (CHANGES, giai đoạn 3, mục 4), nên 58% là cận dưới.
- D5 trên b0_separate chỉ lọt khi một phần thiết bị đã chuyển sang issuerB (L3). Khi đó mỗi CSDL chỉ thấy phần ngân sách của mình.

## 2. Exposure window của b0_separate

Số ngày từ lúc MINT bản trùng tới lần đối soát chéo kế tiếp. Không ca nào bị cắt ở cuối dòng.

| Kịch bản | Trung vị, T_rec = 7 | Lớn nhất, T_rec = 7 | Trung vị, T_rec = 30 | Lớn nhất, T_rec = 30 |
|---|---|---|---|---|
| D3 | 3,5 ngày | 6,5 | 15,5 | 29,5 |
| D4a | 3,4 | 6,5 | 14,5 | 29,5 |
| D4b | 2,5 | 6,5 | 15,4 | 29,5 |
| D5 | 4,0 | 6,5 | 18,5 | 29,5 |

Đối soát gộp CSDL rồi chạy lại khóa và ngân sách CP. Nó tìm ra mọi bản trùng của D3–D5, nhưng chỉ sau khi chứng chỉ đã được phát hành và có thể đã được chuyển đi. Sổ cái dùng chung (b0_shared, chain) chặn ngay lúc phát hành: exposure bằng 0. Đối soát **không** tìm ra insider, vì bản ghi đã bị sửa ngay trong CSDL gốc.

## 3. REJECT nhầm (mẫu âm của lớp A)

| Mẫu âm | Số yêu cầu (5 seed, mọi dòng) | Bị REJECT hoặc giữ |
|---|---|---|
| L1: 6 khối hợp lệ sau cùng CP | 155.874 | 0 ở cả ba backend |
| L3: B6 chuyển đăng ký sang issuerB giữa kỳ (§16.3) | 14.184 | 0 |
| L4: Production Group thay 6 thiết bị (§7.7) | 3.190 | 0 |

## 4. Parity chain – CSDL dùng chung

Nhật ký quyết định của chain và b0_shared được so từng dòng trên 50 dòng sự kiện (339.238 thao tác):

- Ngoài kịch bản insider, kết cục (MINT, REJECT, revert) và lượng MINT trùng nhau 100%.
- 368 dòng lệch đều thuộc insider, và lệch là đúng thiết kế. Trên CSDL có 300 lần sửa thành công; 68 lần chuyển nhượng hoặc retire về sau thất bại vì bản ghi đã bị xóa. Trên chain, cả 300 lần đều revert.

Như H1 đã dự đoán: về khả năng **phát hiện trùng**, blockchain không hơn một CSDL dùng chung. Khác biệt duy nhất là insider: trên chain, không ai sửa được bản ghi đã phát hành một cách lặng lẽ.

## 5. Gas (Hardhat, tối ưu 200 lần chạy, viaIR)

| Thao tác | Số lần | Gas trung vị |
|---|---|---|
| `submitLotEvidence` (4 chữ ký báo cáo + 1 chữ ký verdict) | 31.900 | 138.772 |
| `issue` (một thiết bị-ngày) | 176.545 | 195.225 |
| `registerDevice` | 875 | 119.885 |
| `safeTransferFrom` | 85.851 | 55.530 |
| `retire` | 42.628 | 45.852 |
| `transferRegistration` | 45 | 59.135 |

Gas trên mỗi MWh và độ trễ thuộc E3 (block mỗi 2 giây), chưa chạy.

# Parity chain – mô phỏng off-chain

E2 chạy off-chain qua `gate/sim.py`. Test parity kiểm tra rằng contract cho cùng quyết định (FLOW mục 11):

```bash
.venv/Scripts/python -m rec.experiments.parity --per-scenario 50
```

- **Mẫu:** 50 ca mỗi kịch bản (honest, M1, M2, M3, D4b, D5), chọn ngẫu nhiên. Có 3 ca M3 không có yêu cầu nào vì O1 mất số liệu cả ngày, nên còn 297 ca. Mỗi ca chạy với 3 cấu hình B1, B2, Proposed (biến thể `prereg`, trần 4%), tổng 891 lô.
- **Phía chain:** verifier ký verdict, issuer gửi bằng chứng của lô rồi `issue` từng yêu cầu. Lô REVIEW được auditor phân xử theo nhãn thật, rồi issuer gửi lại.
- **Kết quả:** 0 lệch trên 5.484 yêu cầu. So sánh gồm cờ của verifier, kết cục ở lượt đầu (2.615 MINT, 765 giữ, 2.097 REJECT `capacity`, 7 REJECT `budget`), kết cục sau phân xử, và lượng Wh được MINT. Trong đó 281 lô bị REVIEW.
- **Hai chỗ đã sửa để đạt parity:**
  - `gate/sim.py` giờ xét ngân sách trước công suất, như contract. Lượng MINT của E2 không đổi.
  - Lô đang REVIEW không giữ chỗ trong ngân sách (CHANGES, giai đoạn 5).
- Cờ của verifier (đọc tham số từ file đã khóa) cũng trùng với `decide` của E2 trên 120 ca ngẫu nhiên (`tests/test_verifier.py`).

# E3 (chi phí và truy vết)

Dòng hợp lệ của seed 101: 365 ngày lịch đầu của tập test, tức 336 ngày hợp lệ, 6 thiết bị, có L3. Mỗi cấu hình chạy lại từ cùng trạng thái sau deploy. Lô REVIEW được auditor duyệt lúc 23:00 ngày d + 1 rồi gửi lại.

```bash
.venv/Scripts/python -m rec.experiments.e3
```

## 1. Gas

| | B1 | B2 | Proposed |
|---|---|---|---|
| Giao dịch | 3.875 | 4.036 | 4.050 |
| Lô bị REVIEW (nhầm, vì dòng hợp lệ) | 0 | 24 (7,1%) | 26 (7,7%) |
| MWh phát hành | 1.325,8 | 1.325,8 | 1.325,8 |
| Gas phát hành / MWh (bằng chứng + issue + phân xử) | 336.416 | 343.797 | 344.389 |
| Gas mọi thao tác / MWh (thêm chuyển nhượng, retire) | 396.769 | 403.871 | 404.463 |

Gas trung vị theo thao tác (Proposed): `submitLotEvidence` 139.588; `issue` 195.225 cho một thiết bị-ngày; `resolveReview` 29.676; `safeTransferFrom` 55.530; `retire` 45.852; `registerDevice` 119.825.

- REVIEW làm tăng gas phát hành khoảng 2%: mỗi lô REVIEW tốn thêm một `resolveReview` và một lượt `issue` bị giữ.
- Phần lớn chi phí là `issue` theo từng thiết bị-ngày. Gộp nhiều ngày vào một yêu cầu (kỳ dài hơn, vẫn ≤ 1 năm theo §8.2) sẽ giảm số giao dịch, nhưng mỗi ngày vẫn phải ghi khóa và ngân sách riêng.

## 2. Độ trễ (block mỗi 2 giây)

30 ngày đầu, 371 giao dịch gửi tuần tự. Mỗi giao dịch đến vào một thời điểm ngẫu nhiên trong chu kỳ block (CHANGES, giai đoạn 5, mục 3).

| p50 | p95 | Lớn nhất |
|---|---|---|
| 0,99 giây | 1,91 giây | 2,01 giây |

Độ trễ chỉ là thời gian chờ block kế tiếp, khoảng một nửa chu kỳ block. Chain cục bộ không có độ trễ mạng hay tranh chấp phí; trên mạng thật, con số này là cận dưới.

## 3. Lineage completeness

**100%** ở cả ba cấu hình (2.016 chứng chỉ mỗi cấu hình). Mỗi chứng chỉ dựng lại được chỉ từ event on-chain và kho file, theo chuỗi:

1. `DeviceRegistered`;
2. `LotEvidenced` với 4 `data_root`, cả 4 file trong `artifacts/store/` khớp hash;
3. với lô REVIEW: `LotReview`, file reason code, `LotResolved`;
4. `Issued`;
5. mọi `TransferSingle` và `Retired`, khớp số dư.

Dashboard dùng cùng hàm này; trên chain demo, kết quả cũng là 100%, kể cả chứng chỉ bị Code Manager rút một phần.

# Tái lập (giai đoạn 6)

`python -m rec.experiments.run_all` chạy lại toàn bộ trong 64 phút trên máy của nhóm:
- dữ liệu gốc → generator;
- E2 (đăng ký trước, chọn biến thể, hậu kiểm);
- E1 (SQLite; chain 5 node song song, 30 phút);
- parity, E3 (17 phút), hình.

Kết quả:

- Dataset, danh sách ngày và tập test sinh lại từ dữ liệu gốc **khớp hash** của `spec-v1` và `testset-v1`.
- So với lần chạy trước, 174/177 file kết quả trùng từng byte, gồm 150 nhật ký quyết định E1 của ba backend và mọi bảng E2. Ba file còn lại khác vì lý do đã biết, không phải do kết quả dao động:
  - `e3/lineage.csv` có thêm cột `withdrawn_wh`; nội dung các cột cũ trùng;
  - bản parity cũ đã bị test nhỏ (`REC_CHAIN_TESTS=1`) ghi đè. Chạy lại parity đủ mẫu lần nữa thì trùng từng byte với bản của `run_all`.
- Hash của các file tất định nằm ở `manifests/results-v1.sha256`. Trên máy khác, chạy `python -m rec.experiments.run_all --check`; nó báo `khop` nếu ra cùng số.
- Không nằm trong manifest: độ trễ E3 (đo theo đồng hồ thật), nhật ký chạy, `models.pkl`.

# Bổ sung sau nhận xét giữa kỳ

Ba phân tích thêm vào ngày 12/11/2026, không sửa file nào đã khóa. Ở phần này, "ngưỡng MWh" là "trần" và "kỳ sản xuất" là "lô" của các mục trên. Tiêu chí của phần hậu kiểm ghi ở [manifests/CHANGES.md](../manifests/CHANGES.md), mục 12/11/2026.

```bash
.venv/Scripts/python -m rec.experiments.error_analysis
.venv/Scripts/python -m rec.experiments.e2_hybrid --test --sweep
.venv/Scripts/python -m rec.experiments.e1 --crosscheck
```

## 1. Rà việc dùng train, validation, test

| Tham số hoặc lựa chọn | Lấy từ đâu | Có nhìn test không |
|---|---|---|
| Danh sách ngày, 73 ngày lỗi bị loại | Luật không dùng nhãn; η của luật lấy trên train | Luật áp cho cả test, nhưng chốt ở `spec-v1` trước khi sinh tập test |
| η, β, γ của luật nhất quán; hệ số 0,8141 của PVWatts | Khớp trên ngày trung thực của train | Không |
| Đặc trưng của AI (8 cột từ O4 và lịch) | Chốt ở `spec-v1` | Không |
| Siêu tham số GBM (300 vòng, tốc độ học 0,05, lá ≥ 20 mẫu) | Đặt cố định một lần, không dò | Không; không đổi giữa các commit (`b76c094`, `a945557`) |
| Phân vị nền 0,95; mức REVIEW nhầm 1% (nhất quán) và 4% (ngưỡng MWh); dãy quét 1–10% | Chốt ở `spec-v1` | Không |
| τ₁₂, τ₁₃ và τ của ngưỡng MWh | Ngày trung thực của val | Không |
| Kết quả chính (đăng ký trước) | Chạy test một lần, commit `b76c094` | — |
| Biến thể `day_only` của luật nhất quán | Chọn trên val theo tiêu chí ghi trước | **Có**: ý tưởng nảy ra sau khi thấy kết quả test. Mang nhãn hậu kiểm, không thay kết quả chính |
| Ngưỡng ghép `hybrid` (mục 3 dưới đây) | Chọn trên val theo tiêu chí ghi trước | **Có**: thêm vào sau khi đã thấy kết quả test của B2 và Proposed. Mang nhãn hậu kiểm |
| Cấu hình chạy trên chain và trong demo | Đăng ký trước | — |

Kết luận: kết quả chính không có tham số nào chỉnh trên test. Hai biến thể hậu kiểm được chọn trên val, nhưng lý do để thử chúng đến từ kết quả test, nên chúng chỉ là kết quả tham khảo.

## 2. Error analysis: ngưỡng MWh của AI lỏng ở đâu

Mỗi ngày trung thực có một **khoảng hở** = ngưỡng MWh / sản lượng thật − 1: mức khai tăng mà riêng ngưỡng MWh còn cho qua. Số liệu ở mức 4%, k = 3, bản đăng ký trước. Bảng đầy đủ ở `artifacts/results/error_analysis/`.

**Theo loại ngày (test; trong ngoặc là val):**

| | Quang | Mây vừa | Nhiều mây |
|---|---|---|---|
| Số ngày | 514 (247) | 80 (39) | 44 (35) |
| Phần sản lượng | 89,9% (90,1%) | 8,2% (7,2%) | 1,9% (2,7%) |
| Khoảng hở trung vị, B2 | 19,2% (20,3%) | 25,6% (14,3%) | 26,4% (15,5%) |
| Khoảng hở trung vị, Proposed | **10,8%** (11,2%) | 30,8% (23,4%) | **86,5%** (114,6%) |
| LMAX, B2 | 11,7% (11,3%) | 16,1% (15,5%) | 24,4% (28,0%) |
| LMAX, Proposed | 10,7% (9,9%) | 18,8% (21,4%) | 60,6% (93,6%) |
| Phần MWh lọt nằm ở loại ngày này, B2 | 85,5% | 10,7% | 3,7% |
| Phần MWh lọt nằm ở loại ngày này, Proposed | 78,2% | 12,5% | 9,2% |
| REVIEW nhầm do ngưỡng MWh, B2 | 0,6% (0%) | 5,0% (10,3%) | **15,9%** (22,9%) |
| REVIEW nhầm do ngưỡng MWh, Proposed | 4,1% (3,6%) | 3,8% (2,6%) | 4,5% (5,7%) |

Trên **val**, LMAX ở k = 3 của Proposed là 13,0%, cao hơn B2 (12,0%). Tức là ngay trên val, AI đã không hơn ngưỡng vật lý.

**Vì sao AI lỏng ở ngày nhiều mây:**

| | Quang | Mây vừa | Nhiều mây |
|---|---|---|---|
| Số ngày train | 804 | 132 | 90 |
| Lệch bức xạ vệ tinh so với cảm biến tại chỗ, trung vị (test) | 7,1% | 11,0% | 18,5% |
| Sản lượng thật / nền của B2, trung vị (test) | 1,06 | 1,01 | 1,00 |
| Sản lượng thật / nền của Proposed, trung vị (test) | 0,98 | 0,83 | **0,58** |

- Nền của B2 là ước lượng **trung tâm** (PVWatts nhân hệ số trung vị), cộng một biên chung 26,9%. Nền của Proposed là **phân vị 0,95** cộng biên 8,1%.
- Ở ngày nhiều mây, bức xạ vệ tinh lệch nhiều (18,5%) và train chỉ có 90 ngày. Phân vị 0,95 vì vậy nằm rất xa giá trị điển hình: sản lượng thật chỉ bằng 58% nền. Ở ngày quang con số này là 98%.
- B2 chặt ở ngày nhiều mây vì nó **chấp nhận REVIEW nhầm 16–23% số ngày nhiều mây**. Proposed rải REVIEW nhầm đều khoảng 4% cho mọi loại ngày. Hai cấu hình có cùng tỉ lệ REVIEW nhầm theo số ngày trên val, nhưng đặt chỗ REVIEW nhầm khác nhau.

**Theo tình trạng inverter (test):**

| | Bình thường | Ngừng phát thật | Ngừng ghi số liệu |
|---|---|---|---|
| Số ngày | 370 | 259 | 9 |
| Phần sản lượng | 57,2% | 41,5% | 1,3% |
| Khoảng hở trung vị, B2 / Proposed | 16,0% / 8,4% | 32,6% / 25,0% | 53,8% / 42,6% |
| LMAX, B2 / Proposed | 8,3% / 8,5% | **17,5% / 17,1%** | 25,8% / 25,8% |
| Phần MWh lọt nằm ở nhóm này, B2 / Proposed | 38,5% / 39,6% | **58,8% / 57,8%** | 2,7% / 2,7% |
| REVIEW nhầm do luật nhất quán | 2,4% | 2,3% | 11,1% |

"Ngừng ghi số liệu" là ngày có inverter báo 0 mà công tơ cao hơn η · tổng inverter trên 10%; các ngày inverter báo 0 còn lại là "ngừng phát thật".

- **Gần 60% lượng khai khống còn lọt nằm ở ngày ngừng phát thật.** Hôm đó nhà máy phát ít hơn mức thời tiết cho phép, nên ngưỡng MWh nào suy từ thời tiết cũng để hở phần của inverter đã tắt. Ở k = 3, kẻ gian sửa luôn số inverter, nên luật nhất quán không thấy. Đây là giới hạn của mọi ngưỡng chỉ dựa vào vệ tinh, không riêng AI.
- Ngày ngừng ghi số liệu chỉ có 9 ngày test (1,3% sản lượng). Chúng làm luật nhất quán lỏng (mục 6 của E2), nhưng không phải nguồn chính của phần lọt ở k = 3.

## 3. Cải tiến hậu kiểm: ngưỡng ghép `hybrid`

Hai ứng viên, tiêu chí ghi trước khi chạy, chọn trên val bằng LMAX ở k = 3:

| Trên val | B2 | Proposed | `hybrid` | `ratio` |
|---|---|---|---|---|
| LMAX k = 3 | 12,04% | 13,01% | **11,50%** | 11,78% |
| LMAX ngày quang / nhiều mây | 11,3% / 28,0% | 9,9% / 93,6% | 10,2% / 36,5% | 10,1% / 49,2% |
| REVIEW nhầm | 4,7% | 4,7% | 4,7% | 5,0% |

- `hybrid`: ngưỡng của ngày = min(PVWatts · 1,385; Q̂₀.₉₅ · 1,088). Hai biên lấy ở cùng mức phân vị 2,49% trên val, để hợp hai cờ là 3,7% số ngày.
- `ratio`: GBM học tỉ số công tơ / PVWatts.
- Chọn `hybrid`. Test chạy một lần:

| Trên test | B2 | Proposed | `hybrid` |
|---|---|---|---|
| LMAX k = 1 / 2 / 3 | 10,76% / 11,38% / 12,33% | 10,02% / 10,62% / 12,29% | 10,15% / 10,76% / **11,84%** |
| LMAX k = 3: quang / mây vừa / nhiều mây | 11,7% / 16,1% / 24,4% | 10,7% / 18,8% / 60,6% | 10,9% / 17,7% / 30,8% |
| REVIEW nhầm (mọi ngày trung thực) | 5,2% | 7,1% | 6,7% |
| MWh thật bị giữ tạm | 4,4% | 7,6% | 7,1% |

Hiệu LMAX ở k = 3, khoảng tin cậy 95% bootstrap theo ngày: B2 − `hybrid` = +0,49 điểm [+0,30; +0,68]; Proposed − `hybrid` = +0,45 điểm [+0,22; +0,75].

**Đọc kết quả này thế nào.** `hybrid` thấp hơn B2 0,49 điểm, nhưng trên test nó REVIEW nhầm nhiều hơn B2 1,5 điểm (6,7% so với 5,2%). Cùng mức REVIEW nhầm trên val không bảo đảm cùng mức trên test. Bảng quét dưới đây so ở mức REVIEW nhầm **đo trên test** (mô tả, không dùng để chọn gì):

| q trên val | B2: LMAX / REVIEW nhầm | Proposed: LMAX / REVIEW nhầm | `hybrid`: LMAX / REVIEW nhầm |
|---|---|---|---|
| 1% | 13,27% / 3,1% | 12,83% / 5,3% | 13,09% / 3,1% |
| 2% | 12,98% / 3,4% | 12,59% / 6,3% | 12,03% / 6,1% |
| 4% | 12,33% / 5,2% | 12,29% / 7,1% | 11,84% / 6,7% |
| 5% | 12,03% / 7,1% | 11,89% / 9,7% | 11,64% / 7,2% |
| 10% | 11,35% / 9,3% | 11,03% / 14,7% | 10,58% / 12,9% |

- Ở REVIEW nhầm khoảng 7% trên test: B2 12,03%, Proposed 12,29%, `hybrid` 11,64–11,84%. Tức là **ở cùng mức REVIEW nhầm đo trên test, Proposed không hơn B2**, còn `hybrid` hơn B2 khoảng 0,2–0,4 điểm.
- Mô hình AI trôi giữa val và test nhiều hơn ngưỡng vật lý: đặt 4% trên val thì ngưỡng của Proposed REVIEW nhầm 4,1% số ngày test, của B2 là 2,2%.
- Kết luận trong phạm vi đã thử: AI một mình chưa hơn ngưỡng vật lý; ghép hai ngưỡng cho lợi ích nhỏ (dưới 0,5 điểm trên mức lọt khoảng 12%), và đây là kết quả hậu kiểm. `hybrid` chưa được chạy với kẻ gian ngây thơ (E2a) và chưa đưa lên chain.

## 4. B0 tách biệt có tra chéo lúc đăng ký (I-REC §7.4.3)

Quy trình I-REC đã có một bước kiểm tra giữa các hệ thống: khi đăng ký, issuer tra các registry đã biết. Baseline mới `CrossCheckRegistry` mô phỏng bước này trên B0 tách biệt, ở hai mức, và giả định bước tra **luôn chính xác** (trường hợp tốt nhất cho quy trình thủ công). Chuyển issuer hợp lệ (§16.3) không bị ảnh hưởng. Cùng dòng sự kiện và cách tính như E1, 300 ca mỗi kịch bản; mã kịch bản theo code.

| Kịch bản | B0 tách biệt (E1) | + tra theo mã thiết bị | + tra theo điểm đấu nối | Sổ chung, chain (E1) |
|---|---|---|---|---|
| D3 đăng ký lại mã ở issuer khác | 178 ca lọt | **0** (bước đăng ký) | 0 | 0 |
| D4a thiết bị mới cùng CP | 299 | 299 | **0** (bước đăng ký) | 0 |
| D4b một phần khối đăng ký thành thiết bị mới | 261 | 261 | **0** (bước đăng ký) | 0 |
| D5 thay ngày Y bằng dữ liệu ngày X | 128 (tỉ lệ lọt 9%) | 128 | **128** | 0 (ngân sách CP) |
| D1, D2, D6 | 0 | 0 | 0 | 0 |

REJECT nhầm trên L1, L3, L4: 0 ở cả hai mức.

- Tra theo **mã thiết bị** chỉ chặn được D3. Bản trùng đổi mã (D4a, D4b) qua được, vì mã mới chưa có ở đâu.
- Tra theo **điểm đấu nối** chặn cả D3, D4a, D4b ngay lúc đăng ký, nếu bước tra không sót.
- Phần còn lại là D5: sau khi một thiết bị chuyển issuer hợp lệ, mỗi CSDL chỉ thấy phần ngân sách của mình, nên phát hành vượt số công tơ không bị thấy lúc phát hành. Đối soát định kỳ tìm ra sau 4–18 ngày (mục 2 của E1).
- Như vậy lợi ích của sổ chung so với quy trình hiện có gồm hai phần:
  - thay một bước tra thủ công, dựa vào khai báo, bằng kiểm tra tự động. Phần này lớn hay nhỏ tùy tỉ lệ sót của bước tra thủ công, là thứ đề tài **không đo được**;
  - kiểm tra ngân sách ngay lúc phát hành, là thứ registry tách biệt không làm được dù tra chéo hoàn hảo.
