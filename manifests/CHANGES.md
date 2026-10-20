# Thay đổi sau các mốc protocol

Mỗi thay đổi đối với file đã khóa ở một mốc (`spec-v1`, `testset-v1`) ghi một mục: ngày, file, thay gì, vì sao, ảnh hưởng tới kết quả nào. Sau đó chạy lại `python -m rec.manifest <mốc>` và commit manifest mới.

## Sau `spec-v1`, trước `testset-v1` (20/10/2026, khi cài đặt generator)

`SPEC.md` không bị sửa. Các mục dưới đây là chỗ làm rõ hoặc chỗ lệch khi cài đặt, và có hiệu lực từ `testset-v1`.

1. **Bước định dạng không cắt giá trị ở mức công suất** (SPEC mục 9). Số liệu bị sửa chỉ được làm tròn về Wh nguyên, slot thiếu để trống. *Vì sao:* nếu cắt ở mức công suất thì M1 với s = 5 không bao giờ vượt công suất, và luật ③ mất tác dụng. *Ảnh hưởng:* một phần ca M1 bị REJECT ở luật ③ thay vì REVIEW ở lớp B.
2. **Lượng xin của mỗi thiết bị** bằng số công tơ O1 của ngày, chia theo tỷ lệ sản lượng inverter của khối, làm tròn xuống, nên tổng không vượt O1. *Vì sao:* tổng inverter cao hơn công tơ khoảng 1,6% (tổn thất); nếu mỗi thiết bị xin đúng sản lượng inverter thì nhà máy trung thực cũng vượt ngân sách CP. *Ảnh hưởng:* đây là làm rõ, không đổi chỉ số nào.
3. **L4 chạy trong một dòng riêng** (`honest_group_s<seed>`): một Production Group thay cho 6 thiết bị. *Vì sao:* nhóm và 6 thiết bị không thể cùng được phát hành sau một CP. *Ảnh hưởng:* REJECT nhầm trên L4 được đo trên dòng riêng này.
4. **Tập test của E2 là bảng ca cộng hàm tất định `apply_case`** (theo seed và `case_id`), thay vì dòng sự kiện đầy đủ. Lô trung thực chỉ có một bản (seed 0), vì không có phần ngẫu nhiên. *Vì sao:* khoảng 232 nghìn ca; lưu cả chuỗi 15 phút của từng ca là quá nặng. Bảng ca, nhãn và mã generator cùng được hash ở mốc 2, nên dữ liệu vẫn bị khóa.
5. **Ngày nguồn X của D5** phải có cùng số slot với ngày đích (ngày đổi giờ có 92 hoặc 100 slot). Ở E1, X lấy trong các ngày test trước ngày đích; ở E2, X lấy trong mọi ngày hợp lệ trước ngày đích. *Ảnh hưởng:* D5 có 281 ngày đích đủ điều kiện (khoảng 44 ngày nhiều mây, 237 ngày trời quang có inverter ngừng phát).
6. **Kiểm tra dấu vết nhân tạo** được cài bằng kiểm tra cấu trúc, không bằng mô hình phân loại (SPEC mục 9). Mọi chuỗi, cả trung thực lẫn bị sửa, đều đi qua cùng một hàm làm tròn (`rec/oracles/encoding.py`). Bộ kiểm tra xác nhận: giá trị không âm, đúng số slot, và không thêm slot thiếu (trừ M3, D5). Vì vậy không còn đặc trưng định dạng nào khác nhau giữa bản ghi gốc và bản ghi bị sửa để một mô hình phân loại có thể học. *Ảnh hưởng:* bỏ bước đo AUC ≈ 0,5; điều kiện mà bước đó nhằm đảm bảo được kiểm trực tiếp.
7. **Schema:** `Device` có thêm ngày đăng ký hiệu lực, cờ Production Group và số thành viên; `Transfer`, `Retire`, `OperatorEdit` có thêm trường `ref` để nối với nhãn ẩn. Không đổi chỉ số.

## Sau lần chạy E2 đăng ký trước (20/10/2026): biến thể hậu kiểm của luật nhất quán

**Kết quả chính vẫn là lần chạy đăng ký trước** (commit `b76c094`, lưu ở `artifacts/results/prereg/`). Mục này mô tả một biến thể **hậu kiểm**, nghĩa là được thêm vào **sau khi đã thấy kết quả test**. Báo cáo phải trình bày cả hai và ghi rõ nhãn hậu kiểm.

- **Vấn đề quan sát được:** theo SPEC mục 6.2, luật nhất quán dùng cả tỷ số theo ngày lẫn tỷ số lớn nhất theo slot 15 phút. Trên ngày trung thực của train và val, tỷ số theo slot rất nhiễu: max O1/(η·O2) − 1 có trung vị khoảng 15%, p95 khoảng 60%; với E₃, trung vị khoảng 40–50%. Để hợp 4 cờ chỉ REVIEW nhầm 1%, mức phân vị bị đẩy lên q = 1,0, tức ngưỡng bằng giá trị lớn nhất trên val (r12 theo slot là 446%). Hệ quả: LMAX ở k = 1 (10,0%) gần bằng ở k = 3 (12,3%), nên luật nhất quán gần như vô tác dụng.
- **Các biến thể cần so** (chỉ thay cách tính thống kê theo slot; tỷ số theo ngày giữ nguyên):
  - `prereg`: như SPEC (max theo slot 15 phút);
  - `hour`: max của tỷ số trên cửa sổ trượt 4 slot (1 giờ), chỉ xét cửa sổ đủ 4 slot có số liệu và mẫu số ≥ 5% công suất của cửa sổ;
  - `day_only`: bỏ thống kê theo slot, chỉ giữ tỷ số theo ngày.
- **Tiêu chí chọn, ghi trước khi chạy, chỉ dùng train và val:**
  1. Với mỗi biến thể, khớp mô hình trên train và chọn ngưỡng trên val như SPEC (hợp các cờ nhất quán 1%, riêng trần 4%).
  2. Tính LMAX giải tích trên **lô trung thực của val**, cấu hình Proposed, k = 1.
  3. Chọn biến thể có LMAX nhỏ nhất. Nếu `hour` kém `day_only` không quá 0,5 điểm phần trăm thì chọn `hour`, vì nó còn giữ khả năng bắt tăng đột biến ngắn (M1) mà `day_only` bỏ mất.
- **Tập test** chỉ được chạy cho biến thể đã chọn, đúng một lần. Kết quả ghi ở `artifacts/results/<biến thể>/`.
- **Kết quả chọn trên val** (`python -m rec.experiments.e2 --select`, ghi `artifacts/results/selection.json`):

  | Biến thể | q của ngưỡng nhất quán | REVIEW nhầm trên val | LMAX trên val (Proposed, k = 1) |
  |---|---|---|---|
  | `prereg` | 1,000 | 0,0% | 9,55% |
  | `hour` | 1,000 | 0,0% | 9,66% |
  | `day_only` | 0,9969 | 0,62% | **9,10%** |

  `hour` kém `day_only` 0,56 điểm, vượt mức 0,5 điểm, nên theo tiêu chí ta chọn **`day_only`**. Cửa sổ 1 giờ không bớt nhiễu: tỷ số theo cửa sổ vẫn có đuôi dài (ngưỡng r12 theo cửa sổ là 1.137%), nên q vẫn bị đẩy lên 1,0. Với `day_only`, ngưỡng theo ngày là τ₁₂ = 27,0% và τ₁₃ = 24,3%.
- **Kết quả test của `day_only`** (chạy một lần; so với `prereg` ở mức trần 4%):
  - LMAX ở k = 1: B2 10,76% → 10,43%; Proposed 10,02% → 9,69%. Ở k = 3 gần như không đổi (B2 12,33% → 12,35%; Proposed 12,29% → 12,34%).
  - REVIEW nhầm trên test (mọi lô trung thực): B2 5,2% → 3,3%; Proposed 7,1% → 5,2%. MWh thật bị giữ tạm của Proposed: 7,6% → 5,3%.
  - Đổi lại, recall với kẻ gian ngây thơ giảm: M3 khoảng 60% → 48%, D5 68% → 63%, M1 69% → 66% (Proposed); M2 và D4b tăng nhẹ (0,1–1 điểm).
  - Quy tắc kết luận không đổi: ở 4%, hiệu 0,01 điểm, CI [−0,39; 0,33]; ở 1%, hiệu 0,43 điểm, CI [0,11; 0,72].
- **Kết luận của mục này:** bỏ thống kê theo slot chỉ đổi mức cân bằng giữa REVIEW nhầm và recall, không làm luật nhất quán chặt hơn đáng kể. Nguyên nhân chính là đuôi của tỷ số theo ngày trên lô trung thực (27% cho O1/O2 và 24% cho O1/E₃ ở mức 1% REVIEW nhầm), chứ không phải thống kê theo slot. Nhóm không thử thêm biến thể nào trên test.
- **Nguồn gốc của đuôi** (chẩn đoán trên train và val, không dùng test để chọn gì): trong 26 ngày trung thực của train và val có O1/(η·O2) − 1 > 10%, có 22 ngày thuộc nhóm "inverter ngừng phát" (`outage`). Trên val, p99 của tỷ số này là 4,3% ở ngày không có `outage` và 23,5% ở ngày có `outage`. Ví dụ ngày 27/8/2021: tổng inverter bằng 0 ở 19 slot ban ngày, nhưng công tơ vẫn đo được 685 kWh trong các slot đó. Như vậy một phần ngày `outage` là **inverter ngừng ghi số liệu**, không phải ngừng phát thật. Điều này trái với giả định ở Final Proposal mục 2.1 ("công tơ giảm theo, tức là ngừng thật"). Đây đúng là rủi ro "kiểm tay 50 ngày inverter ngừng phát" còn treo ở giai đoạn 2. Nếu nhóm sửa định nghĩa thì đó là thay đổi dữ liệu sau khi đã thấy test: phải sinh `testset-v2`, ghi vào đây, và vẫn báo cáo kết quả `testset-v1`.
