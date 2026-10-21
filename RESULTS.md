# Kết quả thí nghiệm

- [E1 (RQ1, lớp A)](#e1-rq1-lớp-a)
- [E2 (RQ2, lớp B)](#e2-rq2-lớp-b)
- [Parity chain – mô phỏng](#parity-chain--mô-phỏng-off-chain)
- [E3 (chi phí và truy vết)](#e3-chi-phí-và-truy-vết)

# E2 (RQ2, lớp B)

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
| D4b thiết bị mới gồm tỷ lệ f các khối | **261/300 lọt**, 74% | 0/300 (ngân sách CP) | 0/300 (ngân sách CP) |
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
