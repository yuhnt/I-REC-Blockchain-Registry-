# Kịch bản quay video demo

Dài khoảng 8–10 phút. Mỗi bước ghi: làm gì trên màn hình, nói gì, khoảng bao lâu. Ảnh mẫu của từng bước nằm ở `docs/demo/img/`, mô tả ở [DEMO.md](DEMO.md).

## Chuẩn bị (không quay)

- Dựng lại chain demo để số liệu đúng như ảnh mẫu:
  ```bash
  .venv/Scripts/python -m rec.deploy.demo --stop
  .venv/Scripts/python -m rec.deploy.demo
  ```
- Mở dashboard: `.venv/Scripts/streamlit run dashboard/app.py`, trình duyệt ở `http://localhost:8501`.
- Chọn chain "Sepolia (testnet)" **một lần trước khi quay**. Lần đầu dashboard phải đọc log của mọi block mới, có thể mất vài phút; sau đó có cache nên mở lại nhanh. Xong thì chuyển về "Hardhat cục bộ".
- Mở sẵn các tab Etherscan ở bước 9 và đợi trang tải xong. Etherscan có trang kiểm tra trình duyệt nên đừng mở lần đầu trong lúc quay.
- **Không để lộ trên màn hình:** file `contracts/.env`, URL RPC, mnemonic. Dashboard đã tự ẩn URL; chỉ cần không mở file `.env` và không chạy lệnh in biến môi trường.
- Trình duyệt phóng to 100%, cửa sổ khoảng 1440 × 900, tắt thông báo hệ thống.

Giao diện còn dùng chữ "lô" và "trần", trong khi báo cáo đã đổi thành "kỳ sản xuất" và "ngưỡng MWh". Khi nói, dùng thuật ngữ của báo cáo.

## Kịch bản

| # | Màn hình | Làm gì | Nói gì | Thời lượng |
|---|---|---|---|---|
| 0 | Terminal, rồi dashboard | Chạy `python -m rec.deploy.demo` (hoặc chiếu kết quả đã chạy). Trên thanh bên chỉ: chain "Hardhat cục bộ", số block, "Lớp B: Proposed (prereg)" | Hệ thống gồm 3 contract trên chain cục bộ, 4 nút oracle ký số liệu, và lớp B chạy off-chain. Bản demo nạp 20 ngày dữ liệu thật của nhà máy PVDAQ 2107, cùng một số kịch bản gian lận | 45 giây |
| 1 | **Công khai → Tổng quan** | Chỉ 5 ô số và biểu đồ | Đây là phần ai cũng xem được: 51,86 MWh đã phát hành, 15,98 MWh đã retire, 2 yêu cầu bị từ chối, 3 kỳ sản xuất bị REVIEW. Biểu đồ so sánh sản lượng công tơ với lượng đã phát hành theo ngày | 30 giây |
| 2 | **Truy vết kịch bản** | Chỉ "8/8 khớp kỳ vọng". Bấm lần lượt dòng D1, D4a, M2-k3, honest | Mỗi dòng là một kịch bản đã chạy trên chain, so điểm chặn kỳ vọng với event đọc từ chain. D1 nộp lại cùng (thiết bị, ngày) nên bị REJECT vì khóa. D4a đăng ký thiết bị mới ở issuer khác để chép sản lượng, bị REJECT vì vượt ngân sách điểm đấu nối. M2-k3 khai tăng cả 3 nguồn đo tại chỗ, bị REVIEW vì vượt ngưỡng MWh do model AI đưa ra. Dòng honest là một ngày trung thực bị REVIEW nhầm | 1 phút 30 giây |
| 3 | **Nhà máy** | Chỉ 5 ô số. Mục "Sản xuất theo ngày": bấm ngày 2022-01-01, cuộn xuống bảng thiết bị, bảng 4 oracle và hai biểu đồ. Lướt qua 3 mục còn lại | Nhà máy thấy sản lượng công tơ, lượng đã phát hành, chứng chỉ đang giữ, đã chuyển và yêu cầu chờ auditor. Ngày 1/1/2022: 6 thiết bị được phát hành; yêu cầu trùng của B1 và thiết bị giả X-D4a bị từ chối kèm lý do. Bảng 4 oracle cho thấy số liệu từng nguồn, và file gốc khớp hash `data_root` đã ghi trên chain | 1 phút 15 giây |
| 4 | **Issuer** | Chọn issuerA; chỉ bảng "Yêu cầu bị giữ" và "Yêu cầu bị từ chối" | Issuer thấy các yêu cầu đang chờ auditor và các yêu cầu bị từ chối. Sau khi auditor duyệt, issuer bấm "Gửi lại" để phát hành | 30 giây |
| 5 | **Production Auditor** | Mục "Chứng chỉ chờ duyệt": bấm một dòng của ngày 2022-05-03 (M2-k3), mở "Bằng chứng của lô", chỉ reason code và hai biểu đồ. Sau đó bấm một dòng của ngày 2022-01-31 (ngày trung thực bị REVIEW nhầm), nhập lý do, bấm **Duyệt cả lô** | Auditor không thấy nhãn kịch bản, chỉ thấy bằng chứng: số liệu 4 oracle, cờ của lớp B và reason code. Ngày 3/5/2022 số công tơ vượt ngưỡng MWh, nên bị giữ. Ngày 31/1/2022 là ngày trung thực bị giữ nhầm; auditor duyệt, và quyết định áp dụng cho cả kỳ sản xuất. Khóa auditor chỉ đổi trạng thái, không tự phát hành được | 1 phút 30 giây |
| 6 | **Issuer**, rồi **Nhà máy** | Issuer bấm "Gửi lại … yêu cầu của các lô đã duyệt". Quay lại Nhà máy, chỉ ô "Đã phát hành" tăng | Sau khi được duyệt, issuer gửi lại và chứng chỉ của ngày đó được MINT | 30 giây |
| 7 | **Người mua** | Mục "Chứng chỉ đang giữ": chọn một chứng chỉ, retire một phần kèm người thụ hưởng và mục đích. Mở "Tuyên bố đã retire" | Người mua nhận chứng chỉ từ nhà máy, rồi retire khi dùng điện. Retire là burn: phần đó không chuyển hay retire lại được, nhưng bản ghi retire vẫn công khai | 1 phút |
| 8 | **Công khai → Nhật ký công khai**, **Lineage completeness**; **Production Auditor → Chứng chỉ bị tạm khóa** | Chỉ các event REJECT, khóa, rút của Code Manager; chỉ lineage 100% | Mọi REJECT, mọi lần tạm khóa hoặc rút chứng chỉ đều để lại event công khai, kèm lý do. Lineage completeness cho biết bao nhiêu chứng chỉ dựng lại được đủ nguồn gốc chỉ từ event và kho file | 45 giây |
| 9 | Dashboard, chain **"Sepolia (testnet)"** | Chuyển chain ở thanh bên; mở Tổng quan và Nhà máy; bấm link "Contract chứng chỉ trên Etherscan" | Cùng hệ thống đã deploy lên testnet công khai Sepolia, với 3 ngày dữ liệu demo. Dashboard đọc trực tiếp từ testnet | 45 giây |
| 10 | **Sepolia Etherscan** | Lần lượt mở các link bên dưới | Mã nguồn 3 contract đã verify công khai. Trang token cho thấy chứng chỉ ERC-1155 được MINT, chuyển và burn khi retire. Giao dịch D1 có event `IssueRejected` lý do `KEY`; giao dịch D4a có lý do `BUDGET`. Giao dịch retire có event `Retired`, và lần rút của Code Manager có event `Withdrawn` | 1 phút 15 giây |

Tổng khoảng 10 phút. Nếu cần ngắn hơn, bỏ bước 6, 7 và rút bước 3.

## Link cho bước 10 (Sepolia Etherscan)

| Nội dung | Link |
|---|---|
| DecisionGate: danh sách giao dịch | https://sepolia.etherscan.io/address/0x905d8D925937F3b9F208366b677A9130552F66f7 |
| CertificateRegistry: mã nguồn đã verify | https://sepolia.etherscan.io/address/0x2fc8481C363419CFa53dbC8BdBcF7956aF624462#code |
| Chứng chỉ ERC-1155 (MINT, chuyển, burn) | https://sepolia.etherscan.io/token/0x2fc8481C363419CFa53dbC8BdBcF7956aF624462 |
| DeviceRegistry | https://sepolia.etherscan.io/address/0x33FE6c429CC760829485F67811bb80b304d12Cf4 |
| D1 bị REJECT (`KEY`) | https://sepolia.etherscan.io/tx/0xf21f3a1b4a7353d46d2c514142ecb5e252a50f0afd6726710bbbf09f5bbcccc9#eventlog |
| D4a bị REJECT (`BUDGET`) | https://sepolia.etherscan.io/tx/0x6c38a256059557b79b317ffe4090bfc952e0deceb91137d7a77c1bc30e122d6a#eventlog |
| Retire (event `Retired`) | https://sepolia.etherscan.io/tx/0x7dc71bc1349e7bfffeb34f5b718ac66b1945a2d774496ea991478b8d7682e75d#eventlog |
| Code Manager rút (event `Withdrawn`) | https://sepolia.etherscan.io/tx/0x581612be2742aa5699c085c9558602539b304500f93df873d3e4ee509219a501#eventlog |

Trong log của Etherscan, `reason` hiện dạng số theo thứ tự trong contract: 0 = `KEY`, 1 = `BUDGET`.

## Sau khi quay

Bước 5–7 đã gửi giao dịch thật lên chain cục bộ, nên số liệu đổi so với ảnh mẫu. Muốn quay lại từ đầu, chạy lại hai lệnh ở phần chuẩn bị.
