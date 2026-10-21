# Kiểm tay các ngày "inverter ngừng phát"

Việc còn treo từ giai đoạn 2 (SPEC mục 5, `scenarios.yaml` → `inverter_outage.manual_check_days: 50`). E2 cho thấy một phần ngày `outage` là inverter **ngừng ghi số liệu** chứ không ngừng phát (manifests/CHANGES.md), nên phải kiểm trước khi dùng các ngày này làm mẫu âm L5 và ngày đích D5.

## Cách làm

1. Dựng bộ hình (khoảng 1 phút): `.venv/Scripts/python -m rec.data.manual_check`. Mở `artifacts/manual_check/index.html`: một trang gồm 50 hình kèm hướng dẫn.
2. Hai người kiểm **độc lập**, không xem cột của nhau: người 1 điền `nguoi_kiem_1`, `ket_luan_1`; người 2 điền `nguoi_kiem_2`, `ket_luan_2` trong `phieu_kiem_tay.csv` (mở được bằng Excel). Giá trị kết luận:
   - `ngung_that`: ở vùng tô, công tơ giảm theo tổng inverter; khung giữa nằm quanh 0;
   - `ngung_ghi`: inverter báo 0 nhưng công tơ không giảm; khung giữa bám theo đường đứt;
   - `loi_cong_to`: công tơ thấp hơn hẳn tổng inverter, hoặc báo 0 khi inverter vẫn phát;
   - `khong_ro`: không phân biệt được.
3. Ngày hai người khác ý thì bàn lại, điền `ket_luan_chot` và lý do ở `ghi_chu` (ngày cùng ý thì chép kết luận chung). Commit phiếu đã điền.
4. Cột `goi_y_gap_ratio` là gợi ý của máy. Nó sai ở những ngày có nhiều lỗi chồng nhau (ví dụ 27/8/2021: cả bộ ghi inverter về 0 sau 15:00, gợi ý chỉ ra 0,16). Không chép theo cột này.

## Mẫu

- 30 ngày `ngau_nhien` (seed 2026) trong 1.032 ngày `outage` của cả train, val và test: dùng để ước lượng tỉ lệ ngừng ghi.
- 20 ngày `duoi_cao`: công tơ cao hơn η × tổng inverter nhiều nhất trong số còn lại: dùng để thấy rõ hiện tượng. Nhóm này không dùng để ước lượng tỉ lệ.

## Sau khi kiểm

- Nếu tỉ lệ `ngung_ghi` trong 30 ngày ngẫu nhiên đáng kể: sửa định nghĩa `outage` (ví dụ đòi công tơ giảm theo), sinh lại dataset và tập test (`testset-v2`), ghi vào `manifests/CHANGES.md`. Mọi kết quả chạy trên `testset-v2` mang nhãn **hậu kiểm**, và vẫn báo cáo kết quả của `testset-v1`.
- Nếu gần như toàn bộ là `ngung_that`: giữ định nghĩa; ghi kết quả kiểm vào CHANGES. Đuôi của luật nhất quán vẫn phải được giải thích bằng các ngày ngừng ghi đã thấy ở nhóm `duoi_cao`.
