# Luật quyết định: từ 4 báo cáo oracle đến chứng chỉ

Tài liệu này ghi lại **đúng các luật và ngưỡng mà code đang chạy**, theo thứ tự một lô đi qua hệ thống. Lô = một ngày
của cả nhà máy (CP-1). Luồng tổng quát và lý do thiết kế ở [FLOW.md](FLOW.md); định nghĩa gốc ở
[SPEC.md](../SPEC.md) mục 6; kết quả đo ở [RESULTS.md](RESULTS.md).

Ngưỡng của lớp B không ghi tay ở đây: chúng được chọn một lần trên tập val và khóa trong
`artifacts/model/<biến thể>/layer_b.json`. Bảng dưới chép lại các giá trị đó (làm tròn) để đọc cho tiện.

Gặp ký hiệu hay viết tắt chưa rõ (τ, η, E₃, k, R1, OIR, LMAX, B2, …): xem [mục 8](#8-thuật-ngữ-và-ký-hiệu).

## 0. Hằng số của nhà máy và thời gian

| Hằng số | Giá trị | Nguồn |
|---|---|---|
| Công suất AC mỗi inverter | 30 kW (mức clipping quan sát được) | `configs/scenarios.yaml` → `plant` |
| Thiết bị | 6 khối B1–B6 × 4 inverter = **120 kW** mỗi thiết bị | như trên |
| Công suất CP | **720 kW**; trần một slot = 720 kW × 0,25 h = **180 kWh** | `DeviceRegistry.cpCapacityW` |
| Slot | 15 phút; số slot ban ngày `sunSlots` = số slot có góc thiên đỉnh < 90° (pvlib) | `configs/thresholds.yaml` |
| Kết thúc ngày d | 00:00 giờ nhà máy (UTC−7) của ngày d + 1 | `DecisionGate.DAY_END_OFFSET_S = 7 hours` |
| Lịch một lô | 00:30 oracle báo cáo → 00:45 issuer gửi bằng chứng → 01:00 yêu cầu MINT → 23:00 auditor xử lý REVIEW → 12:00 ngày d + 2 kiểm tra ngẫu nhiên | `rec/generator/common.py`, `rec/sim/runner.py`, `rec/gate/auditor.py` |

## 1. Bốn oracle (off-chain) → báo cáo đã ký

Mỗi oracle là một nút riêng (`rec/oracles/node.py`), giữ một khóa riêng; contract chỉ nhận báo cáo của oracle i nếu
chữ ký khớp `oracleSigner[CP][i]`.

| Oracle | Nguồn | Đơn vị | Người giữ khóa (R1 / R2) |
|---|---|---|---|
| O1 | Công tơ tại điểm đấu nối | Wh | điện lực / chủ dự án |
| O2 | Tổng 24 inverter | Wh | chủ dự án |
| O3 | Bức xạ POA và nhiệt độ tại chỗ | Wh/m², °F → °C | chủ dự án |
| O4 | Bức xạ POA từ vệ tinh NSRDB | Wh/m² | issuer |

Báo cáo ngày (EIP-712 `OracleReport`): `valueDay` = tổng các slot có số liệu, `maxSlot` = slot lớn nhất,
`slotsPresent` = số slot có số liệu (slot thiếu **không** điền 0), `dataRoot` = keccak của chuỗi 15 phút
(`rec/oracles/encoding.py`). Chuỗi gốc nằm trong kho file theo `dataRoot`, ai cũng kiểm được.

## 2. Contract nhận bằng chứng của lô: `submitLotEvidence`

Issuer gửi 4 báo cáo + chữ ký + `Verdict` của verifier. Contract **revert** (không ghi gì) nếu:

| Kiểm tra | Lỗi |
|---|---|
| Thiếu báo cáo O1 (O1 là cơ sở của ngân sách CP) | `BadReport(0)` |
| Báo cáo sai vị trí oracle, khác CP hoặc ngày, hoặc `maxSlot > valueDay` | `BadReport(i)` |
| Chữ ký báo cáo không khớp địa chỉ của oracle đó | `BadSignature(i)` |
| `Verdict` không trỏ đúng lô hoặc đúng hash của 4 báo cáo | `BadVerdict` |
| `Verdict` không do verifier đã đăng ký ký | `BadSignature(4)` |
| Lô đã có bằng chứng với cùng giá trị O1 | `LotAlreadyEvidenced` |

Riêng khi lô đã có bằng chứng mà **O1 mới khác O1 cũ**: không revert, phát `O1Conflict(stored, offered)` để dấu vết
còn lại on-chain, giữ nguyên O1 cũ. Nếu qua hết: lưu `o1Wh`, `maxSlot`, `sunSlots`, `flags`, ghi O1 vào
`CertificateRegistry.recordO1`, trạng thái lô là **CLEAR** khi `flags = 0`, ngược lại **REVIEW** (phát `LotReview`).

O2–O4 được phép vắng (oracle = 0); khi đó verifier đặt cờ thiếu báo cáo ở bước ① dưới đây.

## 3. Lớp B: verifier tính `flags` (off-chain, ký kết quả)

Code: `rec/gate/verifier.py`, `rec/checks/consistency.py`. Cấu hình chạy trên chain là **Proposed**, biến thể
**prereg** (đăng ký trước), trần ở mức **4%** REVIEW nhầm. `modelHash` trong `Verdict` = keccak của
`layer_b.json` + `models.pkl` + cấu hình, nên lô nào cũng chỉ rõ bộ ngưỡng nào đã quyết định nó.

Lớp B **chỉ chống khai khống** (O1 cao hơn thực tế). Nó không tham gia chống đếm trùng; việc đó là của lớp A.

### ① Đủ báo cáo — cờ `MISSING_REPORT` (2)

Với O1, O2, O3: tỉ lệ slot ban ngày có số liệu phải **≥ 95%**. Một oracle dưới mức này là đủ để REVIEW. O4 không xét
(do issuer vận hành).

### ② Nhất quán một phía — cờ `INCONSISTENT` (1)

Tham số khớp trên ngày trung thực của train: η = 0,9828 (công tơ / tổng inverter), β = 657,16 Wh mỗi Wh/m²,
γ = −0,00652 /°C. Sản lượng kỳ vọng từ O3: E₃ = min(180 kWh, β · POA · (1 + γ · (T − 25))).

| Thống kê | Công thức | τ (prereg) | τ (day_only, hậu kiểm) |
|---|---|---|---|
| r12_day | ΣO1 / (η · ΣO2) − 1 | 0,3689 | 0,2701 |
| r12_slot | max theo slot O1 / (η · O2) − 1 | 4,4615 | — |
| r13_day | ΣO1 / ΣE₃ − 1 | 0,3101 | 0,2428 |
| r13_slot | max theo slot O1 / E₃ − 1 | 1,6113 | — |

Tổng chỉ tính trên slot ban ngày mà cả hai bên cùng có số liệu. Thống kê theo slot chỉ xét slot có mẫu số ≥ 5% công
suất slot (9 kWh). **Chỉ một phía:** REVIEW khi một thống kê **lớn hơn** τ, tức O1 cao hơn; O1 thấp hơn không bị
xét. Thiếu dữ liệu để so (NaN) thì không đặt cờ (bước ① đã lo phần thiếu).

Cách chọn τ: tăng dần phân vị q trên lô trung thực của val tới khi hợp 4 cờ ≤ 1% REVIEW nhầm. Ở prereg, đuôi của thống
kê theo slot đẩy q lên 1,0 (τ = giá trị lớn nhất trên val), nên luật này gần như chỉ bắt được khai khống rất lớn. Biến
thể `day_only` là phân tích hậu kiểm, ghi ở [manifests/CHANGES.md](../manifests/CHANGES.md); verifier on-chain vẫn dùng
prereg.

### ③ Trần sản lượng ngày — cờ `OVER_CEILING` (4)

REVIEW khi `O1.valueDay > nền · (1 + τ)`.

| Cấu hình | Nền của ngày | τ ở 4% | Ghi chú |
|---|---|---|---|
| B2 | 0,8141 · PVWatts(NSRDB) | 0,2688 | vật lý, không học |
| **Proposed** | Q̂₀.₉₅ của mô hình GBM (đặc trưng chỉ từ O4 và lịch) | **0,0814** | `configs/features.yaml` |

Các mức khác (1%, 2%, 5%, 10%) có trong `layer_b.json` → `tau_ceiling`. τ chọn sao cho riêng cờ trần chiếm đúng
mức đó trên lô trung thực của val.

`flags = ① | ② | ③`. Khác 0 → lô vào REVIEW. Lý do chi tiết (tỉ lệ phủ, các thống kê, nền, τ) lưu thành file JSON
trong kho; `reasonsHash` trên chain trỏ tới file đó.

## 4. Lớp A: `issue` quyết định từng yêu cầu MINT (on-chain)

Yêu cầu = một thiết bị, một kỳ gồm các ngày liên tiếp, Wh của từng ngày. Contract kiểm theo đúng thứ tự dưới đây và
dừng ở lỗi đầu tiên. Vi phạm **không revert** mà phát `IssueRejected(reqId, device, day, reason)` để lý do được lưu
công khai (§8.7). Chỉ cần một ngày vi phạm là cả yêu cầu bị từ chối.

| # | Mã | Điều kiện từ chối | Phạm vi | I-REC |
|---|---|---|---|---|
| 1 | `NOT_REGISTERED` | thiết bị chưa đăng ký | cả yêu cầu | §7.1 |
| 2 | `PERIOD` | kỳ vắt qua hai năm, trước ngày đăng ký hiệu lực, từ ngày đóng đăng ký, hoặc chưa kết thúc lúc nộp | cả yêu cầu | §8.2 |
| 3 | `NOT_ISSUER` | người gửi không phải issuer phụ trách thiết bị ở mọi ngày trong kỳ | từng ngày | §16.3 |
| 4 | `KEY` | khóa (thiết bị, ngày) đã có chứng chỉ | từng ngày | §7.1 |
| 5 | `ORACLE` | lô của ngày chưa có bằng chứng | từng ngày | §8.7 |
| 6 | `BUDGET` | Wh đã phát cho CP trong ngày + Wh yêu cầu > O1 của lô | từng ngày | §8.5 |
| 7 | `CAPACITY` | Wh > 120 kW × `sunSlots` × 0,25 h, hoặc `maxSlot` > 180 kWh, hoặc O1 > 720 kW × `sunSlots` × 0,25 h | từng ngày | §7.6 |
| 8 | `LOT_REJECTED` | auditor đã bác lô | từng ngày | §8.7 |

Ngày có Wh = 0 được bỏ qua. Nếu qua hết mà còn ngày thuộc lô **REVIEW**: phát `IssueHeld(reqId, lotKey)`, không MINT,
không giữ chỗ ngân sách. Nếu mọi ngày đều CLEAR hoặc APPROVED: MINT, tức `CertificateRegistry.mint` tạo token ERC-1155 cho chủ đăng ký của CP, mỗi
(thiết bị, ngày) một `tokenId`, đánh dấu khóa đã dùng.

Hai lớp bảo vệ ngân sách độc lập: `DecisionGate` kiểm `BUDGET` ở trên, và `CertificateRegistry.mint` tự revert
`KeyUsed` / `OverBudget` nếu bị gọi vượt (phòng lỗi của gate).

## 5. Production Auditor phân xử lô REVIEW: `resolveReview`

Chỉ địa chỉ auditor gọi được, chỉ khi lô đang REVIEW. Kết quả `APPROVED` hoặc `REJECTED` kèm `reasonHash` (file biên
bản trong kho). Phân xử không MINT: issuer gửi lại yêu cầu đã bị giữ và `issue` chạy lại **toàn bộ** bảng ở mục 4.
Lô APPROVED → MINT; lô REJECTED → `LOT_REJECTED`.

Trong mô phỏng (`rec/gate/auditor.py`), auditor luôn kết luận đúng: duyệt khi lô không có phần khai vượt sản lượng
thật. Đây là giả định có lợi cho hệ thống; tỉ lệ REVIEW nhầm cho biết auditor phải đọc bao nhiêu lô trung thực.

## 6. Kiểm tra ngẫu nhiên p và Code Manager

Lúc 12:00 ngày d + 2, auditor bốc ngẫu nhiên p% số lô đã MINT (p ∈ {0; 1%; 5%}). Mỗi lô có một số u ∈ [0, 1) cố định,
được kiểm khi u < p, nên tập kiểm ở 1% nằm trong tập ở 5%. Lô gian lận bị bốc trúng thì Code Manager xử lý:

- `suspend(tokenId, true, lý do)`: khóa chứng chỉ, không chuyển nhượng hay retire được (§11);
- `withdraw(tokenId, holder, Wh, lý do)`: rút phần **chưa retire** và trả lại ngân sách CP (§11). Phần đã retire
  trước lúc kiểm đã bị đốt, không rút được, và tính là lọt.

Retire (`CertificateRegistry.retire`) đốt Wh của người giữ và ghi người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo;
không đảo ngược, không sửa được (§10). Chứng chỉ đang bị tạm khóa thì không retire được.

## 7. Tra cứu nhanh: một yêu cầu bị từ chối vì sao

| Thấy trên chain | Nghĩa |
|---|---|
| `IssueRejected … KEY` | đếm trùng: (thiết bị, ngày) đã có chứng chỉ (D1, D2) |
| `IssueRejected … BUDGET` | tổng các issuer xin cho CP vượt O1 của ngày (D4a, D4b, D5) |
| `IssueRejected … CAPACITY` | vượt giới hạn vật lý của thiết bị hoặc CP (khai khống rất lớn) |
| Đăng ký thiết bị revert | mã thiết bị đã đăng ký ở issuer khác (D3), chặn trước khi có yêu cầu MINT |
| `IssueRejected … ORACLE` | chưa có bằng chứng của lô, hoặc bằng chứng đã revert |
| `IssueHeld` | lô đang REVIEW vì `flags` của lớp B; chờ auditor |
| `IssueRejected … LOT_REJECTED` | auditor đã bác lô |
| `O1Conflict` | có người gửi O1 thứ hai khác cho cùng lô; O1 đầu tiên được giữ |
| Giao dịch revert, không có event | người không có quyền gọi (ví dụ insider sửa bằng chứng, `NotIssuer`, `BadSignature`) |

## 8. Thuật ngữ và ký hiệu

Quy ước viết: **MINT**, **REJECT**, **REVIEW** viết hoa là kết cục của một yêu cầu; `mint` trong backtick là hàm của
contract. Số viết kiểu Việt: dấu phẩy thập phân (0,95), dấu chấm tách nghìn (1.985).

### Dữ liệu và đơn vị

| Từ | Nghĩa |
|---|---|
| Slot | Khoảng 15 phút, nhãn ở cuối khoảng. Một ngày có 96 slot (92 hoặc 100 vào ngày đổi giờ) |
| Lô | Một ngày sản xuất của cả nhà máy (một CP). Lớp B quyết định theo lô, không theo từng thiết bị |
| CP | Điểm đấu nối với lưới (connection point), nơi đặt công tơ O1. Mọi thiết bị sau một CP dùng chung ngân sách |
| Thiết bị | Một khối 4 inverter (120 kW) được đăng ký riêng; nhà máy có 6 thiết bị B1–B6 |
| Slot ban ngày, `sunSlots` | Slot có mặt trời trên đường chân trời (góc thiên đỉnh < 90°, pvlib tính từ tọa độ). Chỉ slot ban ngày được tính độ phủ |
| Độ phủ | Tỉ lệ slot ban ngày mà một oracle có số liệu |
| `data_root` | Hash keccak256 của chuỗi 15 phút của một báo cáo; cũng là tên file trong kho. Ai cũng kiểm được file chưa bị sửa |
| y | Sản lượng thật của lô (Wh, theo công tơ gốc trước khi kịch bản sửa số). Chỉ thí nghiệm biết y |
| excess | Phần Wh đã MINT vượt y, tức phần khai khống lọt qua |

### Oracle và kẻ gian

| Từ | Nghĩa |
|---|---|
| O1 | Công tơ tại CP. Chứng chỉ được cấp theo số này, nên đây là số kẻ gian muốn khai tăng |
| O2 | Tổng 24 inverter |
| O3 | Bức xạ trên mặt tấm pin (POA) và nhiệt độ, đo bằng cảm biến tại chỗ |
| O4 | Bức xạ POA từ vệ tinh NSRDB. Nhà máy không sửa được nguồn này |
| POA | Plane of array: bức xạ trên mặt phẳng tấm pin, W/m² |
| NSRDB | National Solar Radiation Database của NREL: bức xạ và thời tiết ước lượng từ vệ tinh |
| R1, R2 | Ai giữ khóa ký: R1 khóa O1 thuộc điện lực; R2 khóa O1–O3 thuộc chủ dự án. O4 và verifier luôn thuộc issuer |
| k | Số nguồn tại chỗ kẻ gian sửa được, luôn gồm O1: k = 1 (O1), k = 2 (O1, O2), k = 3 (O1, O2, O3) |

### Lớp B

| Ký hiệu | Nghĩa |
|---|---|
| Một phía | Chỉ báo động khi O1 **cao hơn** nhân chứng. O1 thấp hơn thì nhà máy tự thiệt, không phải khai khống, nên không xét |
| η | Tỉ số công tơ / tổng inverter, phần điện mất qua dây và máy biến áp (0,9828). Khớp trên ngày trung thực của train |
| β, γ | Hệ số đổi bức xạ ra điện: β Wh mỗi Wh/m², γ hệ số nhiệt mỗi °C lệch khỏi 25 °C (dạng mô hình PVWatts). Khớp trên train |
| E₃ | Sản lượng kỳ vọng suy từ O3: min(180 kWh, β · POA · (1 + γ · (T − 25))) mỗi slot |
| r₁₂, r₁₃ | Mức O1 cao hơn O2 (đã nhân η) và cao hơn E₃, tính theo ngày (tổng) và theo slot (lớn nhất) |
| τ | Ngưỡng. τ₁₂, τ₁₃ cho luật nhất quán; τ của trần là biên an toàn trong nền · (1 + τ). Mọi τ chọn trên val theo tỉ lệ REVIEW nhầm cho trước |
| Nền | Sản lượng dự đoán của ngày, chỉ từ O4 và lịch: PVWatts(NSRDB) với B2, mô hình AI với Proposed |
| PVWatts, pvlib | PVWatts là mô hình sản lượng điện mặt trời của NREL; pvlib là thư viện Python cài đặt mô hình này. "PVWatts(NSRDB)" là sản lượng PVWatts tính từ bức xạ vệ tinh |
| Q̂₀.₉₅(x) | Phân vị 95% của sản lượng ngày do mô hình GBM dự đoán từ đặc trưng x (chỉ lấy từ O4 và lịch) |
| Verdict | Kết quả lớp B của một lô, do verifier ký EIP-712: `flags`, `sunSlots`, `ceilingWh`, `modelHash`, `reasonsHash` |
| Verifier | Khóa của issuer chạy lớp B off-chain và ký verdict. Contract chỉ nhận verdict có chữ ký trong allowlist |
| `flags` | Các cờ: 1 không nhất quán, 2 thiếu báo cáo, 4 vượt trần. Khác 0 thì lô vào REVIEW |
| `modelHash` | Hash của bộ ngưỡng và mô hình đã dùng, để biết lô được quyết định bằng phiên bản nào |
| prereg, day_only | prereg là cách tính đăng ký trước (`spec-v1`), chạy trên chain. day_only là biến thể hậu kiểm, bỏ thống kê theo slot |

### Cấu hình so sánh

| Tên | Gồm |
|---|---|
| B0 | Registry tập trung trên SQLite. Biến thể tách biệt: mỗi issuer một CSDL; dùng chung: một CSDL cho mọi issuer |
| B1 | Chỉ lớp A (khóa, ngân sách CP, công suất), không có lớp B |
| B2 | Lớp A + lớp B với trần vật lý PVWatts(NSRDB) |
| Proposed | Lớp A + lớp B với trần AI. Đây là mô hình đề xuất |
| A1, A2 | Ablation: A1 cho AI dùng O3 thay O4; A2 thay GBM bằng hồi quy phân vị tuyến tính |

### Trạng thái và kết cục

| Từ | Nghĩa |
|---|---|
| CLEAR, REVIEW, APPROVED, REJECTED | Trạng thái của lô: sạch; đang chờ auditor; auditor đã duyệt; auditor đã bác |
| MINT, REJECT, giữ | Kết cục của một yêu cầu: được cấp chứng chỉ; bị lớp A từ chối kèm mã lý do; bị giữ vì lô đang REVIEW |
| REVIEW nhầm | Lô trung thực bị đưa vào REVIEW. Tỉ lệ REVIEW nhầm là số việc thừa của auditor |
| Kiểm tra ngẫu nhiên p | Auditor bốc p% số lô đã MINT để kiểm lại lúc 12:00 ngày d + 2 |
| Production Auditor | Vai phân xử lô REVIEW (I-REC §8.5), chỉ đổi trạng thái lô, không MINT được |
| Code Manager | Vai của Evident theo I-REC §11: tạm khóa, mở khóa, rút chứng chỉ chưa retire; mọi thao tác có event công khai |
| Không nâng cấp, không quyền `mint` ngoài gate | Contract không có hàm admin để sửa, xóa hay mint tùy ý, không dùng proxy; chỉ `DecisionGate` gọi được `mint` |

### Kịch bản và chỉ số

| Từ | Nghĩa |
|---|---|
| D1–D6 | Đếm trùng: nộp lại (thiết bị, ngày) đã cấp (D1, D2); đăng ký trùng mã ở issuer khác (D3); thiết bị "mới" cùng CP chép sản lượng (D4a, D4b); thay ngày xấu bằng số của ngày tốt (D5); retire lần hai (D6) |
| Insider | Người vận hành sửa, xóa hoặc phát hành lại bản ghi mà không để dấu vết |
| M1–M3 | M1 tăng đột biến ngắn; M2 nhân (1 + α) cả ngày; M3 oracle lỗi (không phải gian lận) |
| L1–L5 | Mẫu âm: tình huống hợp lệ dễ bị chặn nhầm (nhiều thiết bị sau một CP, chuyển issuer, Production Group, ngày quang giống nhau, inverter ngừng phát) |
| DCR | Phần Wh trùng hoặc khai vượt đã MINT trên tổng Wh đã MINT (E1) |
| OIR | Σ excess đã MINT / Σ y trên các lô bị tấn công: phần khai khống lọt qua (E2a) |
| Recall | Tỉ lệ lô bị tấn công nhận REVIEW hoặc REJECT |
| LMAX | Phần khai vượt lớn nhất mà kẻ gian khôn ngoan vẫn lọt mọi kiểm tra, tính giải tích trên 638 lô test (E2b) |
| Lineage completeness | Tỉ lệ chứng chỉ dựng lại được đủ chuỗi chỉ từ event on-chain và kho file (E3) |
| train, val, test | Năm 2018–2020 để khớp mô hình; 2021 để chọn ngưỡng; 2022–2023 để đánh giá, chỉ chạy một lần |
