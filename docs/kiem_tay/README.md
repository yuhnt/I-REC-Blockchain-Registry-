# Hình minh họa các ngày "inverter báo 0"

Định nghĩa `outage` (SPEC mục 5) bắt được 1.032 trên 1.985 ngày: ban ngày, một inverter báo dưới 0,5 kW ít nhất 2 giờ trong khi trung vị 24 inverter trên 5 kW. Nhóm này gồm hai hiện tượng thật:

- **ngừng phát thật** (đa số): pin hoặc inverter tắt, công tơ giảm theo, khung giữa của hình nằm quanh 0. Ví dụ 22/9/2021, 28/7/2022;
- **ngừng ghi số liệu** (thiểu số): inverter báo 0 nhưng công tơ vẫn đo được điện, khung giữa bám theo đường đứt. Ví dụ 27/8/2021.

Bước kiểm tay 50 ngày **đã bỏ**: dữ liệu được giữ nguyên, và kết quả kiểm tay không làm thay đổi dữ liệu hay chỉ số nào (`manifests/CHANGES.md`, mục "Quyết định về các ngày inverter báo 0"). Bộ hình được giữ để minh họa trong báo cáo.

Dựng lại (khoảng 1 phút): `.venv/Scripts/python -m rec.data.manual_check`, rồi mở `artifacts/manual_check/index.html`. Mẫu gồm 30 ngày ngẫu nhiên và 20 ngày có công tơ cao hơn η × tổng inverter nhiều nhất. Mỗi hình có ba khung:
1. công tơ so với η × tổng inverter;
2. phần chênh lệch so với phần inverter ngừng lẽ ra phát;
3. 24 inverter, tô màu inverter bị đánh dấu.
