# Đặc tả thí nghiệm – mốc 1 (`spec-v1`)

Tài liệu này cùng các file `configs/split.yaml`, `scenarios.yaml`, `features.yaml`, `thresholds.yaml`, `configs/days.csv` và `configs/days_dropped.csv` tạo thành **mốc 1** của protocol (Final Proposal, Phụ lục 3.3). Sau khi gắn tag `spec-v1`, mọi thay đổi phải ghi vào `manifests/CHANGES.md` kèm lý do. Mô hình AI chỉ được cài đặt sau mốc 2 (`testset-v1`).

Final Proposal là chuẩn. Những chỗ proposal chưa nói rõ được chốt ở đây và đánh dấu **(chốt)**. Đối chiếu với I-REC Code ở `COMPLIANCE.md`; luồng chạy, giao diện contract và định dạng message ở `FLOW.md`.

## 1. Quy ước

- Năng lượng: số nguyên Wh.
- Ngày: ngày địa phương America/Los_Angeles, mã hóa thành số ngày kể từ 1970-01-01 (`rec/timeutil.py`). Slot 15 phút, nhãn cuối kỳ.
- **Lô (chốt):** chứng chỉ của cả nhà máy (một CP) trong một ngày. Lớp B, tỉ lệ REVIEW nhầm và kiểm tra ngẫu nhiên đều tính theo lô. Chứng chỉ vẫn được phát hành riêng cho từng thiết bị trong ngày; mọi yêu cầu của một lô nhận cùng kết luận của lớp B.
- **Ban ngày** khi kiểm tra báo cáo: theo vị trí mặt trời (góc thiên đỉnh < 90°), không theo cảm biến tại chỗ.
- **Số liệu thiếu để trống, không điền 0 (chốt).** I-REC không quy định cách xử lý dữ liệu thiếu; đây là thực hành chung của ngành đo đếm.
- Đồng hồ mô phỏng: báo cáo của ngày d gửi lúc 00:30 ngày d + 1, yêu cầu phát hành lúc 01:00 ngày d + 1 (giờ địa phương).
- Chữ dùng thống nhất: **REVIEW nhầm** (lô trung thực bị đẩy sang REVIEW), **lọt** (lô gian lận được MINT).

## 2. Ngày và chia tập (`split.yaml`)

- Khoảng dữ liệu: 2018-01-01 → 2023-11-30.
- Ngày đủ độ phủ: có ≥ 20 slot ban ngày (POA tại chỗ > 20 W/m²), và mỗi kênh (24 inverter, công tơ, POA) có số liệu ở ≥ 95% số slot ban ngày; slot inverter cần đủ 3 mẫu 5 phút. Bản sơ bộ cho 2.058 ngày.
- **Loại ngày lỗi dữ liệu (chốt):** bộ ghi đôi khi báo 0 thay vì để trống, nên bộ lọc độ phủ không nhận ra. Loại ngày có công tơ hoặc tổng inverter cả ngày ≤ 0, hoặc |công tơ / (η · tổng inverter) − 1| > 50% (η ≈ 0,983, khớp trên train). Bị loại **73 ngày** (15 ngày một nguồn báo 0, 58 ngày lệch quá 50%), ghi ở `configs/days_dropped.csv`.
  - *Lưu ý:* loại theo độ lệch có thể làm luật (a) trông tốt hơn thực tế, vì đó đúng là những ngày luật (a) sẽ REVIEW nhầm. Báo cáo phải nêu số ngày bị loại, và nêu rằng trong vận hành thật các ngày như vậy sẽ bị REVIEW.
- Chia theo năm: train 2018–2020 (**1.026** ngày), val 2021 (**321**), test 2022–2023 (**638**); tổng **1.985**. Năm 2021 mất 39 ngày, nên ngưỡng chọn trên val dựa vào ít ngày; báo cáo kèm khoảng tin cậy.
- Ngưỡng **khóa cố định** sau khi chọn trên val, không học lại theo năm (chốt). Báo cáo tỉ lệ REVIEW nhầm thực tế trên test để thấy độ trôi giữa các năm.

## 3. Nhà máy, chế độ và oracle

- Một CP (`CP-1`); 6 thiết bị B1–B6, mỗi thiết bị 4 inverter liên tiếp. Hai issuer `issuerA`, `issuerB`.
- **Công suất AC (chốt):** 30 kW mỗi inverter, theo mức clipping quan sát được (định mức ABB TRIO-27.6 là 27,6 kW); 120 kW mỗi thiết bị, 720 kW cho CP.
- **Mọi oracle báo ở mức CP (chốt):** mỗi ngày một báo cáo cho cả nhà máy.
  - O1: công tơ tại CP.
  - O2: tổng công suất của 24 inverter, mỗi inverter đếm một lần. Báo theo thiết bị thì thiết bị giả trong D4b làm tổng O2 phình theo và qua mặt luật (a).
  - O3: bức xạ POA và nhiệt độ tại chỗ. **Nhiệt độ tại chỗ ghi bằng °F**, phải đổi sang °C (đã kiểm: sau khi đổi, lệch NSRDB trung vị 0,8 °C, tương quan 0,95).
  - O4: NSRDB tại tọa độ nhà máy.
- Mỗi báo cáo mang `slots_present` (số slot ban ngày có số liệu) và `data_root` (hash chuỗi 15 phút).
- **Dữ liệu 15 phút lưu off-chain (chốt):** kho file cục bộ, mỗi file đặt tên theo `data_root`. Ai cũng kiểm được file chưa bị sửa bằng cách tính lại hash.
- Chế độ được mô hình bằng quyền giữ khóa ký: R1 khóa O1 thuộc điện lực; R2 khóa O1–O3 thuộc chủ dự án. O4 và verifier luôn thuộc issuer.
- Kẻ gian ở R2 kiểm soát k nguồn tại chỗ, luôn gồm O1: k = 1 (O1), k = 2 (O1, O2), k = 3 (O1, O2, O3 kể cả nhiệt độ tại chỗ).
- **Quyền trong contract (chốt).** Không có mint đặc quyền, không nâng cấp; allowlist oracle, issuer và verifier đặt khi deploy. Giới hạn: không xoay được khóa oracle bị lộ, không thêm được issuer mới; quản trị đa chữ ký kèm độ trễ thời gian là hướng phát triển.
- **Vai trò Code Manager (chốt, theo I-REC §11):** một khóa riêng, tách khỏi mọi issuer, đại diện Evident. Chỉ được:
  - **tạm khóa / mở khóa** chứng chỉ chưa retire (không chuyển nhượng, không retire được khi đang khóa);
  - **rút** chứng chỉ chưa retire phát hành sai. Phần rút được trả lại ngân sách CP; rút toàn bộ một thiết bị-ngày thì khóa (thiết bị, ngày) được mở lại để issuer phát hành lại theo bằng chứng đúng, qua `DecisionGate` như bình thường.
  - Mọi thao tác phát event công khai kèm lý do. **Không** được mint, **không** được chạm vào chứng chỉ đã retire.
  - Dùng cho: lô gian lận bị kiểm tra ngẫu nhiên phát hiện (mục 8.2), và chứng chỉ bị nghi trong lúc auditor điều tra.
- **Lập luận insider (chốt):** blockchain không làm việc sửa bản ghi trở thành *không thể* (I-REC còn yêu cầu sửa được khi có lỗi), mà làm nó **không thể lặng lẽ**. Ở B0, người vận hành sửa, xóa, phát hành lại mà không để dấu vết. Trên chain, issuer không sửa được gì; Code Manager chỉ làm được hai thao tác trên, và mỗi lần đều để lại event công khai, có lý do, gắn với khóa đã ký.

## 4. Kịch bản tấn công (`scenarios.yaml`)

### 4.1 Cách sinh và điểm chặn

| Kịch bản | Cách sinh | Điểm chặn (R1, sổ cái chung) |
|---|---|---|
| D1 | `issuerA` nộp lại yêu cầu (thiết bị, ngày) đã phát hành | Phát hành: khóa |
| D2 | `issuerA` nộp yêu cầu kỳ 7 hoặc 30 ngày phủ lên ngày đã phát hành | Phát hành: khóa |
| D3 | `issuerB` đăng ký lại đúng mã thiết bị đã đăng ký ở `issuerA` rồi nộp yêu cầu | **Đăng ký**: `DeviceRegistry` dùng chung từ chối mã trùng |
| D4a | Thiết bị mới ở `issuerB`, cùng CP, mã khác, nộp dữ liệu của thiết bị đã có | Phát hành: ngân sách CP |
| D4b | Thiết bị mới X ở `issuerB` gồm tỷ lệ f các khối, nộp sản lượng thật của các khối đó. Ở R2, O1 khai tăng (1 + f) lần; k = 3 thì O2, O3 tăng theo | Phát hành: ngân sách CP |
| D5 | Thay yêu cầu ngày Y (nhiều mây, hoặc trời quang có inverter ngừng phát) bằng dữ liệu ngày X đã phát hành có y_X > y_Y. Ở R2, **chuỗi 15 phút của k nguồn ở mức CP được thay bằng chuỗi của ngày X**, cộng nhiễu σ | Phát hành: ngân sách CP |
| D6 | Retire lần hai; chuyển nhượng sau retire | Vòng đời: chứng chỉ đã đốt |
| Insider | Người vận hành sửa, xóa hoặc phát hành lại bản ghi đã phát hành mà không để dấu vết | Issuer không có hàm này; Code Manager chỉ tạm khóa hoặc rút, và luôn để lại event công khai |
| M1 | Nhân s vào k nguồn trong cửa sổ 15/60/120 phút | Lớp B, hoặc luật ③ nếu vượt công suất |
| M2 | Nhân (1 + α) nhất quán vào k nguồn cả ngày | Lớp B |
| M3 | Một oracle (O1, O2 hoặc O3) kẹt giá trị, mất dữ liệu (1/6/24 giờ) hoặc lệch giờ (15/30/60 phút) | Không phải gian lận; đo độ bền |

- **Số ca của E1 (chốt):** mỗi kịch bản D1–D6 và insider chèn vào 60 ngày ngẫu nhiên của tập test, 5 seed. Lớp A là tất định nên không cần mọi ngày; 60 ngày đủ cho phân bố exposure window. DCR báo cáo kèm tỷ lệ tấn công của dòng.
- **Số ca của E2 (chốt):** mỗi ngày test đủ điều kiện cho một kịch bản là một ca. D4b, M1, M2, M3 dùng cả 638 ngày; D5 nhiều mây dùng các ngày nhiều mây của test (khoảng 44); D5 trời quang có inverter ngừng phát dùng số ngày mà định nghĩa ở mục 5 lọc ra. Mọi kết quả ghi kèm số ngày thật.
- 5 seed (101–105) chỉ thay đổi phần ngẫu nhiên (nhiễu, ngày nguồn X, thiết bị), không tạo thêm ngày.
- **H2b với D4b là kiểm tra pipeline, không phải kết quả:** O2 báo ở mức CP thì lớp B nhìn D4b giống hệt M2 với α = f, nên kết quả trùng nhau theo cách dựng. Phần có thông tin là D5, vì chuỗi bị thay có hình dạng của một ngày khác.

### 4.2 Gán nhãn

- Với mỗi (CP, ngày): `excess = tổng đã MINT − y`, với y là sản lượng thật tại công tơ. `excess` được gán cho kịch bản đã tạo ra yêu cầu vượt; mỗi Wh chỉ mang một nhãn.
- **R1:** phần vượt do kịch bản D và Wh bị dùng hơn một lần tính vào DCR.
- **R2:** mọi phần vượt đều phải đi qua việc khai tăng O1, nên tính vào OIR; D4b và D5 tách dòng riêng.
- M3 mang nhãn M nhưng không tính là gian lận.
- Nhãn ghi ra file riêng; chỉ `rec/metrics` và Production Auditor mô phỏng được đọc.

## 5. Mẫu âm khó (L1–L5)

| Mã | Lớp | Đo ở | Nội dung |
|---|---|---|---|
| L1 | A | E1 | Các khối inverter hợp lệ khác nhau sau cùng một CP (§7.6); đăng ký và phát hành không được bị REJECT |
| L3 | A | E1 | Chuyển issuer: **chuyển đăng ký** sang issuer mới, giữ nguyên mã thiết bị, không đăng ký lại (I-REC §16.3) |
| L4 | A | E1 | Production Group (§7.7): một bản ghi nhóm thay cho 6 thiết bị, vẫn chịu ngân sách CP; nhóm ≤ 5 MW, ≤ 50 cơ sở |
| L2 | B | E2a | Các ngày trời quang có hình dạng sản lượng gần giống nhau |
| L5 | B | E2a | Inverter ngừng phát, clipping, đoạn treo, ngày nhiều mây |

- **Inverter ngừng phát (chốt định nghĩa, kiểm tay ở giai đoạn 2):** ban ngày, một inverter báo < 0,5 kW trong ≥ 8 slot (2 giờ) trong khi trung vị 24 inverter > 5 kW. Thử trên dữ liệu: 47% số ngày có ít nhất một inverter ngừng ≥ 2 giờ giữa trưa; tỷ số công tơ / tổng inverter ở các ngày này vẫn ≈ 0,983, tức là ngừng phát thật. 2 thành viên kiểm tay 50 ngày trước khi dùng.
- Ngưỡng loại ngày (quang ≥ 0,8; mây vừa 0,5–0,8; nhiều mây < 0,5 theo chỉ số trời quang NSRDB) là lựa chọn thiết kế. Tập test có khoảng 514 / 80 / 44 ngày.

## 6. Luật quyết định

### 6.1 Lớp A (contract, chắc chắn) → REJECT

| Luật | Nội dung |
|---|---|
| Đăng ký | Mã thiết bị không trùng; thiết bị gắn đúng một CP; chuyển đăng ký sang issuer khác giữ nguyên mã (§16.3); đóng đăng ký có ngày hiệu lực |
| ① khóa, vòng đời | (thiết bị, ngày) chưa phát hành; chứng chỉ đã retire không chuyển nhượng, không retire lại; retire ghi người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo và không sửa được (§10) |
| ② ngân sách CP | Σ phát hành tại (CP, ngày) ≤ O1; O1 của một (CP, ngày) được lưu ở lần đầu, O1 khác gửi sau bị từ chối |
| ③ công suất | Mỗi slot ≤ công suất AC × 0,25 h; mỗi ngày ≤ công suất AC × số giờ mặt trời trên đường chân trời (pvlib) |
| Kỳ phát hành (I-REC trang 41) | Kỳ ≤ 1 năm và nằm trọn trong một năm dương lịch; không bắt đầu trước ngày đăng ký hiệu lực; không kéo sau ngày đóng đăng ký; không nằm sau ngày nộp |

### 6.2 Lớp B (off-chain, thống kê) → REVIEW

| Bước | Kiểm tra | Cấu hình |
|---|---|---|
| ① Đủ báo cáo | Thiếu báo cáo cần dùng, hoặc báo cáo có số liệu ở < 95% slot ban ngày → REVIEW | B2, Proposed |
| ② Nhất quán (a), **một phía** | r₁₂ = O1 / (η · O2) − 1 và r₁₃ = O1 / E₃ − 1, ở mức ngày và mức slot (slot có O2 ≥ 5% công suất). **Chỉ REVIEW khi r > τ** (O1 cao hơn); khai thấp không phải khai khống | B2, Proposed |
| ③ Trần | B2: O1 > PVWatts(NSRDB) · (1 + τ₄). Proposed: O1 > Q̂₀.₉₅(x) · (1 + τ_C) | B2 / Proposed |

- **E₃** = Σ β · POA · (1 + γ(T − 25)) cắt ở công suất, với T là nhiệt độ tại chỗ đã đổi sang °C; **η**, β, γ khớp trên lô trung thực của train.
- **Luật khớp ngày cũ (c) đã bỏ (chốt):** nó không phân biệt được hai ngày trời quang giống nhau với dữ liệu bị chép, chỉ bắt được bản chép y nguyên, và kẻ gian không cần chép dữ liệu cũ vì kiểu gì cũng phải khai tăng O1.
- **Chọn ngưỡng (chốt),** trên lô trung thực của val:
  1. τ₁₂, τ₁₃ (ngày và slot) là phân vị cùng mức q của phân bố tương ứng; chọn q sao cho hợp các cờ (a) = **1%**.
  2. τ₄ (B2) và τ_C (Proposed) chọn sao cho **riêng trần** REVIEW nhầm **4%** (mức chính). Tổng REVIEW nhầm của lớp B khoảng 5%; tổng này được báo cáo, không dùng để chỉnh.
  3. Vì val có 321 lô, tỉ lệ đạt được đi theo bước 1/321 ≈ 0,31%; chọn τ nhỏ nhất sao cho số lô vượt không quá q × 321, và ghi tỉ lệ thực đạt được.
- τ₁₂, τ₁₃ dùng chung cho B2 và Proposed; chỉ trần khác nhau.
- **Trần AI:** mô hình học phân vị 0,95 trên train (`random_state` = 0); τ_C chỉnh trên val như τ₄. Hai trần cùng dạng "nền × (1 + τ)", chỉ khác phần nền (vật lý cố định so với học theo thời tiết).
- Đặc trưng AI: chỉ các cột trong `features.yaml` (O4 và thông số tĩnh). Có test chặn mọi cột mang tiền tố `inv`, `meter`, `poa_site`, `o1`, `o2`, `o3`.
- Lớp B không bao giờ làm tăng lượng phát hành: kết quả chỉ có thể là giữ nguyên hoặc REVIEW.

### 6.3 REVIEW và Production Auditor (cách B, như proposal)

- Lô bị REVIEW chưa được MINT, và được lưu kèm bằng chứng (cờ, reason code, `data_root`, báo cáo O1–O4) ở hàng đợi REVIEW trên dashboard.
- Production Auditor phân xử bằng `resolveReview` trên contract (khóa auditor riêng, chỉ đổi trạng thái lô, không mint): lô trung thực được MINT sau khi duyệt, lô gian lận bị bác. Luồng chi tiết ở `FLOW.md` mục 5. Trong thí nghiệm, auditor được giả định **luôn kết luận đúng** (dùng nhãn thật); đây là giới hạn cần ghi rõ. Cái giá của REVIEW nhầm đo bằng khối lượng việc của auditor và lượng MWh bị giữ tạm.

## 7. Chỉ số

| Chỉ số | Định nghĩa | Thí nghiệm |
|---|---|---|
| DCR | (Σ excess do kịch bản D + Σ Wh bị dùng > 1 lần) / Σ Wh đã MINT, kèm tỷ lệ tấn công trong dòng | E1 |
| Tỉ lệ lọt | Σ Wh trùng đã MINT / Σ Wh trùng đã nộp; không phụ thuộc tỷ lệ tấn công tự chọn | E1 |
| Exposure window | Số ngày từ lúc MINT bản trùng đến lúc bị phát hiện. B0 tách biệt đối soát mỗi T_rec ∈ {7, 30} ngày bằng cách gộp CSDL các issuer rồi chạy lại khóa và ngân sách CP; 0 nếu bị chặn trước khi MINT; bị cắt ở cuối kỳ nếu không phát hiện | E1 |
| Insider | Pass nếu mọi thay đổi bản ghi đã phát hành đều để lại event công khai, có lý do, gắn với khóa đã ký; fail nếu sửa, xóa hay phát hành lại được mà không để dấu vết | E1 |
| REJECT nhầm | Tỉ lệ yêu cầu hợp lệ (L1, L3, L4) bị lớp A từ chối; kỳ vọng 0 | E1 |
| OIR | Σ excess đã MINT trên các lô bị tấn công / Σ y của các lô đó; theo kịch bản, theo tỉ lệ kiểm tra ngẫu nhiên p | E2a |
| Recall | Tỉ lệ lô bị tấn công nhận REVIEW hoặc REJECT | E2a |
| Tỉ lệ REVIEW nhầm | Tỉ lệ lô trung thực nhận REVIEW; chung và theo L2, L5; riêng trần và tổng lớp B | E2a |
| Precision ở tỷ lệ gian lận π | π · recall / (π · recall + (1 − π) · tỉ lệ REVIEW nhầm), π ∈ {1%, 5%, 20%} | E2a |
| MWh thật bị giữ tạm | Σ y của lô trung thực bị REVIEW / Σ y trung thực | E2a, E2b |
| M3 | Tỉ lệ REVIEW; Σ \|MINT − y\| / Σ y | E2a |
| **LMAX** | Σ_lô max(0, A − y) / Σ y trên 638 lô test. A = y · s*, với s* là hệ số nhân lớn nhất áp lên chuỗi thật của k nguồn bị sửa mà **mọi** kiểm tra của cấu hình vẫn qua. Báo cáo theo k và loại ngày | E2b |
| Gas | Gas mỗi thao tác (đăng ký, phát hành, chuyển nhượng, retire) và gas trên mỗi MWh | E3 |
| Độ trễ | Từ lúc gửi giao dịch đến khi có receipt, p50/p95, Hardhat đào block mỗi 2 giây | E3 |
| Lineage completeness | % chứng chỉ dựng lại được đủ chuỗi chỉ từ event và kho file theo `data_root` | E3 |

- Khoảng tin cậy 95%: bootstrap theo ngày (1.000 lần), gộp 5 seed. LMAX tất định khi ngưỡng đã cố định; khoảng tin cậy chỉ đến từ bootstrap theo ngày.

## 8. Tỉ lệ REVIEW nhầm và tỉ lệ kiểm tra ngẫu nhiên

### 8.1 Tỉ lệ REVIEW nhầm

So sánh B2 và Proposed khi cho **riêng trần** được REVIEW nhầm q ∈ {1%, 2%, **4%**, 5%, 10%} lô trung thực; **4% là kết quả chính**. Lý do: con số 4% do nhóm chọn (I-REC không quy định), nên phải kiểm tra kết luận có phụ thuộc vào nó không.

- **Cố định ở mọi mức:** mô hình AI (không học lại), công thức pvlib, ngưỡng luật (a).
- **Thay đổi:** chỉ τ₄ và τ_C, chọn lại trên val như mục 6.2.
- **Đầu ra mỗi mức:** tỉ lệ REVIEW nhầm thực tế trên test (riêng trần và tổng); LMAX theo k và loại ngày cho B2 và Proposed. Ở q = 4% và q = 1%: thêm recall và OIR của E2a.
- **Quy tắc kết luận (chốt trước),** dựa trên hiệu LMAX (B2 − Proposed) ở k = 3, khoảng tin cậy 95% bootstrap theo ngày:

| Kết quả | Kết luận |
|---|---|
| Hiệu > 0, khoảng tin cậy không chứa 0, ở cả q = 4% và q = 1% | H2 đúng và vững: AI tốt hơn bất kể tỉ lệ REVIEW nhầm |
| Chỉ đúng ở q = 4% hoặc chỉ ở q lớn | H2 có điều kiện: AI chỉ hơn khi chấp nhận nhiều REVIEW |
| Không ở mức nào | H2 sai: trần vật lý đã đủ |

### 8.2 Tỉ lệ kiểm tra ngẫu nhiên

Production Auditor bốc thăm ngẫu nhiên **p ∈ {0, 1%, 5%} số lô đã MINT** để kiểm tra kỹ, chạy ở q = 4%. Lô gian lận bị bốc trúng thì bị phát hiện chắc chắn, và Code Manager rút phần chứng chỉ chưa retire (mục 3). Phần đã retire trước khi bị phát hiện thì không rút được, và được tính là lọt. Báo cáo OIR sau kiểm tra và LMAX × (1 − p). Câu hỏi: kiểm tra ngẫu nhiên bù được bao nhiêu phần lọt, và lớp B còn đáng làm không. Chưa mô hình hóa hình phạt khi bị bắt.

## 9. Kiểm soát chất lượng dữ liệu sinh

- Mọi bản ghi, cả dương lẫn âm, qua cùng một bước định dạng: làm tròn 0,1 kW, cắt ở công suất, bằng 0 ban đêm, slot thiếu để trống.
- **Kiểm tra dấu vết nhân tạo (chốt cách làm):** một mô hình chỉ nhìn **đặc trưng định dạng** (số chữ số thập phân, kiểu làm tròn, vị trí slot trống, lưới thời gian), không nhìn độ lớn số đo, phải có AUC ≈ 0,5 khi phân biệt bản ghi do generator sửa với bản ghi gốc. Không đòi AUC ≈ 0,5 trên độ lớn số đo, vì phân biệt được độ lớn chính là việc của lớp B.
- Dòng sự kiện sạch phải có DCR = 0. Xem trực quan 20 mẫu mỗi kịch bản.

## 10. Các quyết định đã chốt

| # | Vấn đề | Chốt |
|---|---|---|
| 1 | Đơn vị phân tích | Lô = một ngày của cả nhà máy (mục 1) |
| 2 | Ngày lỗi dữ liệu | Loại 73 ngày; còn 1.985 (mục 2) |
| 3 | Mức báo O2 | Mức CP (mục 3) |
| 4 | Nhiệt độ cho E₃ | Cảm biến tại chỗ, đổi °F sang °C (mục 3) |
| 5 | Luật (a) | Một phía; chiếm 1% REVIEW nhầm (mục 6.2) |
| 6 | Luật khớp ngày cũ (c) | Bỏ (mục 6.2) |
| 7 | Trần | Riêng trần 4% (mức chính); AI = Q̂₀.₉₅ · (1 + τ_C) (mục 6.2) |
| 8 | Thiếu báo cáo | REVIEW; slot thiếu để trống (mục 1, 6.2) |
| 9 | REVIEW | Cách B: auditor phân xử, giả định luôn đúng (mục 6.3) |
| 10 | Số ca | E1: 60 ngày mỗi kịch bản; E2: mỗi ngày đủ điều kiện một ca (mục 4.1) |
| 11 | Tỉ lệ REVIEW nhầm, tỉ lệ kiểm tra ngẫu nhiên | Quét q và p (mục 8) |
| 12 | Ngưỡng theo thời gian | Khóa cố định, báo cáo độ trôi trên test (mục 2) |
| 13 | Quản trị contract | Không mint đặc quyền, không nâng cấp; vai trò Code Manager chỉ tạm khóa và rút chứng chỉ chưa retire, luôn công khai (I-REC §11); insider = "không sửa lặng lẽ được" (mục 3) |
| 14 | Dữ liệu off-chain | Kho file theo `data_root` (mục 3) |
| 15 | D3 và L3 | D3 chặn ở bước đăng ký; L3 dùng thao tác chuyển đăng ký theo §16.3 (mục 4.1, 5) |
| 16 | Kỳ phát hành | Theo I-REC trang 41 (mục 6.1) |
| 17 | Công suất AC | 30 kW mỗi inverter (mục 3) |
| 18 | Hardhat cho E3 | Block mỗi 2 giây; các test khác automine |

## 11. Kiểm soát thay đổi

- Mốc 1: commit các file trên, gắn tag `spec-v1`, ghi hash vào `manifests/spec-v1.sha256` (`python -m rec.manifest spec-v1`).
- Mốc 2: generator đã qua bộ kiểm tra, tập test sinh từ seed ở đây, tag `testset-v1` cùng `manifests/testset-v1.sha256`.
- Sau mỗi mốc, thay đổi nào cũng ghi vào `manifests/CHANGES.md`: thay gì, vì sao, ảnh hưởng tới kết quả nào.
