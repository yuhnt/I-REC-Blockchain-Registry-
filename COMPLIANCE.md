# Đối chiếu với I-REC Code for Electricity v1.11

Bảng truy vết từ điều khoản của I-REC Code v1.11 (10/10/2022, file trong `project/paper/`) tới chỗ hiện thực và test kiểm chứng. Mục đích là chứng minh **từng quy tắc cụ thể** đã được hiện thực và kiểm thử. Bảng này **không** phải chứng nhận tuân thủ: chỉ Evident mới chứng nhận được.

- GEC (chứng chỉ điện xanh của Trung Quốc) không có văn bản quy tắc trong dự án. Trong đề tài, GEC chỉ được mô hình hóa như **một issuer thứ hai** ghi vào cùng sổ cái; không tuyên bố tuân thủ GEC.
- Lớp B (phát hiện bất thường) **không phải** quy tắc của I-REC. Yêu cầu đặt ra cho nó là không vi phạm chuẩn: lớp B chỉ được giữ lại (REVIEW), không bao giờ làm tăng lượng phát hành, và quyết định cuối cùng thuộc về con người.
- Mỗi dòng có trạng thái **Đã thiết kế** sẽ có ít nhất một test, tên test bắt đầu bằng mã điều khoản (ví dụ `IREC-8.2: ...`). Cột "Test" được điền ở giai đoạn 3–5.

## 1. Bảng truy vết

| Điều khoản | Yêu cầu | Hiện thực | Test | Trạng thái |
|---|---|---|---|---|
| §7.1 | Một cơ sở có thể đăng ký ở hệ thống khác, nhưng mỗi đơn vị điện chỉ nhận một chứng chỉ theo dõi thuộc tính | Sổ cái chung cho mọi issuer; khóa (thiết bị, ngày); ngân sách CP | D1–D5, E1 | Đã thiết kế |
| §7.4 | Issuer xác minh vị trí, công suất, vị trí và cấp chính xác công tơ, kết nối lưới (có thể kiểm tra tại chỗ) | Giả định A1: ánh xạ thiết bị → CP và công suất là đúng khi đăng ký | — | Giả định, ngoài phạm vi kiểm thử |
| §7.6 | Ranh giới cơ sở theo điểm đấu nối | `DeviceRegistry`: thiết bị → CP; ngân sách CP | D4a, D4b, L1 | Đã thiết kế |
| §7.7 | Production Group: tổng ≤ 5 MW, ≤ 50 cơ sở | Bản ghi nhóm, vẫn chịu ngân sách CP | L4 | Đã thiết kế |
| §8.2 | Kỳ phát hành ≤ 1 năm, nằm trọn trong một năm dương lịch | Lớp A, lý do REJECT `period` | Kỳ vắt hai năm | Đã thiết kế |
| §8.2 | Kỳ không bắt đầu trước ngày đăng ký hiệu lực, không kết thúc sau ngày hết hạn đăng ký | Lớp A, so với ngày đăng ký và ngày đóng đăng ký | Kỳ trước ngày đăng ký; kỳ sau ngày đóng | Đã thiết kế |
| §8.2, §8.5 | Không yêu cầu cho kỳ nằm sau ngày nộp | Lớp A, so với thời điểm giao dịch | Kỳ ở tương lai | Đã thiết kế |
| §8.2 | Kỳ nằm trong owner's declaration; hạn residual mix | — | — | Ngoài phạm vi |
| §8.5 | Chỉ cấp cho sản lượng đã đo được (measured volume) tại công tơ, làm tròn tới kWh | O1 là số công tơ tại CP; ngân sách CP | Ngân sách CP | Đã thiết kế; đơn vị Wh là đơn giản hóa (mục 3) |
| §8.5 | Thứ bậc bằng chứng: (a) số đối soát thị trường; (b) công tơ chưa đối soát; (c) chứng từ giao nhận; (d) hệ đo được duyệt | Chế độ R1 = (a), R2 = (b)–(d) | E1 chạy R1, E2 chạy R2 | Đã thiết kế |
| §8.5 | Bằng chứng phải được xác minh độc lập; Production Auditor xác nhận không có dấu hiệu sửa dữ liệu | REVIEW → auditor; kiểm tra ngẫu nhiên p% số lô | Luồng REVIEW; E2a theo p | Đã thiết kế |
| §8.7 | Issuer xem xét, có thể yêu cầu thêm thông tin, rồi duyệt hoặc bác kèm lý do | Event `Review` / `Reject` kèm reason code; auditor phân xử (cách B) | Mọi từ chối đều có lý do | Đã thiết kế |
| §9.3 | Chuyển quyền sở hữu chứng chỉ | ERC-1155 `transfer` | Chuyển nhượng hợp lệ | Đã thiết kế |
| §10 | Redemption (retire) không đảo ngược; chứng chỉ đã retire không chuyển được; chỉ một tuyên bố cho mỗi chứng chỉ | `retire` = burn + event | D6 | Đã thiết kế |
| §10 | Khi retire phải ghi người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo; không được sửa sau đó | Trường của `Retire` và event `Retired` | Event có đủ trường | Đã thiết kế |
| §10.6 | Redemption Statement có QR và khóa xác minh | Dashboard dựng lại từ event; không có QR | — | Một phần |
| §11 | Chứng chỉ không bị xóa hay sửa, trừ khi sửa lỗi; Evident có thể **tạm khóa** chứng chỉ bị nghi và **rút** chứng chỉ phát hành sai (trước khi retire), rồi cho phát hành lại đúng | Vai trò Code Manager: tạm khóa, mở khóa, rút chứng chỉ chưa retire; mỗi thao tác phát event kèm lý do; không mint, không chạm chứng chỉ đã retire | Khóa thì không chuyển, không retire được; rút trả lại ngân sách; không rút được chứng chỉ đã retire; Code Manager không mint được | Đã thiết kế (mục 2) |
| §16.3 | Chuyển cơ sở sang issuer khác mà không phải đăng ký lại | Thao tác chuyển đăng ký trong `DeviceRegistry` | L3 | Đã thiết kế |
| §6, §8.3, §13–15 | KYC, hệ thống theo dõi khác, cấp phép quốc gia, đơn vị được công nhận | — | — | Ngoài phạm vi |

## 2. §11 xử lý lỗi và vai trò Code Manager

I-REC cho phép Evident:
- **tạm khóa** chứng chỉ có nguồn gốc bị nghi, không cho chuyển nhượng hay retire cho tới khi điều tra xong;
- **rút hoặc sửa** chứng chỉ phát hành sai khi chưa retire, rồi cho issuer phát hành lại đúng;
- sau khi đã retire thì chỉ sửa khi có thỏa thuận với bên liên quan.

Thiết kế chốt (SPEC mục 3):
- Một khóa **Code Manager** riêng, tách khỏi mọi issuer, chỉ có hai quyền: tạm khóa hoặc mở khóa, và rút chứng chỉ **chưa retire**.
- Mỗi thao tác phát event công khai kèm lý do. Code Manager không mint được và không chạm được chứng chỉ đã retire.
- **Đơn giản hóa:** I-REC còn cho phép "sửa" chứng chỉ; đề tài thay việc sửa bằng *rút rồi phát hành lại đúng* qua `DecisionGate`. Sửa chứng chỉ đã retire (cần thỏa thuận với bên liên quan) nằm ngoài phạm vi.

Hệ quả cho lập luận insider: blockchain không làm việc sửa bản ghi trở thành không thể (chuẩn còn yêu cầu sửa được khi có lỗi), mà làm nó **không thể lặng lẽ**.

## 3. Đơn giản hóa so với chuẩn

| Chuẩn | Trong đề tài | Lý do |
|---|---|---|
| 1 chứng chỉ = 1 MWh | Token tính theo Wh | Mô phỏng sản lượng theo ngày của từng thiết bị (dưới 1 MWh) |
| Kỳ phát hành tối đa 1 năm | Kỳ theo ngày (D2 thử kỳ 7 và 30 ngày) | Vẫn nằm trong giới hạn của chuẩn |
| Issuer xác minh khi đăng ký (§7.4) | Giả định A1 là đúng | Không mô phỏng được kiểm tra tại chỗ |
| Production Auditor là con người | Mô phỏng, giả định luôn kết luận đúng | Không có auditor thật |
| Registry do Evident vận hành | Prototype trên chain cục bộ | Ngoài phạm vi: tích hợp registry thật |
