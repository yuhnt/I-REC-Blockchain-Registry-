# Luật quyết định: từ 4 báo cáo oracle đến chứng chỉ

Tài liệu này ghi lại **đúng các luật và ngưỡng mà code đang chạy**, theo thứ tự một lô đi qua hệ thống. Lô = một ngày
của cả nhà máy (CP-1). Luồng tổng quát và lý do thiết kế ở [FLOW.md](FLOW.md); định nghĩa gốc ở
[SPEC.md](../SPEC.md) mục 6; kết quả đo ở [RESULTS.md](RESULTS.md).

Ngưỡng của lớp B không ghi tay ở đây: chúng được chọn một lần trên tập val và khóa trong
`artifacts/model/<biến thể>/layer_b.json`. Bảng dưới chép lại các giá trị đó (làm tròn) để đọc cho tiện.

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

Ngày có Wh = 0 được bỏ qua. Nếu qua hết mà còn ngày thuộc lô **REVIEW**: phát `IssueHeld(reqId, lotKey)`, không mint,
không giữ chỗ ngân sách. Nếu mọi ngày đều CLEAR hoặc APPROVED: mint ERC-1155 cho chủ đăng ký của CP, mỗi
(thiết bị, ngày) một `tokenId`, đánh dấu khóa đã dùng.

Hai lớp bảo vệ ngân sách độc lập: `DecisionGate` kiểm `BUDGET` ở trên, và `CertificateRegistry.mint` tự revert
`KeyUsed` / `OverBudget` nếu bị gọi vượt (phòng lỗi của gate).

## 5. Production Auditor phân xử lô REVIEW: `resolveReview`

Chỉ địa chỉ auditor gọi được, chỉ khi lô đang REVIEW. Kết quả `APPROVED` hoặc `REJECTED` kèm `reasonHash` (file biên
bản trong kho). Phân xử không mint: issuer gửi lại yêu cầu đã bị giữ và `issue` chạy lại **toàn bộ** bảng ở mục 4.
Lô APPROVED → mint; lô REJECTED → `LOT_REJECTED`.

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
