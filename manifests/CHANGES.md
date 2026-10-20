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
