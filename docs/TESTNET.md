# Trình diễn trên testnet Sepolia

File này do `python -m rec.experiments.testnet` tự ghi sau mỗi lần `deploy`, `verify`, `demo`. Chỉ chứa thông tin công khai trên chain. Thí nghiệm E1–E3 vẫn chạy trên Hardhat cục bộ (RESULTS.md); Sepolia chỉ để tra cứu công khai.

## Contract

Deploy ngày 2026-10-24, từ block 11981681 (chainId 11155111).

| Contract | Địa chỉ | Mã nguồn |
|---|---|---|
| DeviceRegistry | [`0x33FE6c429CC760829485F67811bb80b304d12Cf4`](https://sepolia.etherscan.io/address/0x33FE6c429CC760829485F67811bb80b304d12Cf4) | chưa verify |
| CertificateRegistry | [`0x2fc8481C363419CFa53dbC8BdBcF7956aF624462`](https://sepolia.etherscan.io/address/0x2fc8481C363419CFa53dbC8BdBcF7956aF624462) | chưa verify |
| DecisionGate | [`0x905d8D925937F3b9F208366b677A9130552F66f7`](https://sepolia.etherscan.io/address/0x905d8D925937F3b9F208366b677A9130552F66f7) | chưa verify |

Chứng chỉ ERC-1155 (đơn vị Wh): [https://sepolia.etherscan.io/token/0x2fc8481C363419CFa53dbC8BdBcF7956aF624462](https://sepolia.etherscan.io/token/0x2fc8481C363419CFa53dbC8BdBcF7956aF624462). Tra một chứng chỉ: thêm `?a=<tokenId>`; tokenId = keccak256(abi.encode(deviceId, day)), có sẵn ở dashboard (tab Tra chứng chỉ).

## Dữ liệu demo

Nạp ngày 2026-10-24: 3 ngày đầu của dòng hợp lệ (seed 101, cấu hình Proposed), cùng D1 và D4a bị REJECT, các lô chờ Production Auditor, và một lần tạm khóa và rút của Code Manager.

- Giao dịch: 51, tổng gas 15,949,387
- Yêu cầu đang bị giữ chờ auditor: 12

## Ghi chú vận hành

- Lần nạp thứ nhất: giao dịch chia ETH đặt cứng 21.000 gas nên thất bại (status 0). Sepolia hiện tính khoảng 207.000 gas khi chuyển ETH tới một ví mới tinh. Không có giao dịch demo nào được ghi. Đã sửa: ước lượng gas và kiểm trạng thái giao dịch.
- Lần nạp thứ hai: chữ ký EIP-712 của oracle và verifier dùng nhầm chainId 31337 (của Hardhat), nên mọi bằng chứng của lô bị revert. 32 yêu cầu phát hành bị REJECT với lý do `oracle` ở block 11981722–11981762; các event này vẫn công khai trên chain và không xóa được. Đã sửa: lấy chainId từ mạng đang kết nối.
- Lần nạp thứ ba thành công: 18 chứng chỉ được MINT; D1 bị REJECT `key`, D4a bị REJECT `budget`; 2 lô chờ auditor; một lần tạm khóa và rút của Code Manager.
- Gas trên Sepolia cao khoảng gấp đôi so với Hardhat cục bộ (15,9 triệu so với 6,7 triệu cho cùng phần demo), vì Sepolia hiện định giá lại việc ghi trạng thái mới. Bảng gas của E3 (RESULTS.md) đo trên Hardhat.
- Mã nguồn chưa được verify trên Etherscan: contracts/.env chưa có ETHERSCAN_API_KEY. Có key thì chạy `python -m rec.experiments.testnet verify`.

## Địa chỉ các vai

Suy ra từ mnemonic riêng của nhóm (không công bố). Oracle và verifier chỉ ký off-chain.

| Vai | Địa chỉ |
|---|---|
| deployer | [`0x9E6E50479b6371C212dB25C8fbabE37FE7955129`](https://sepolia.etherscan.io/address/0x9E6E50479b6371C212dB25C8fbabE37FE7955129) |
| issuerA | [`0x933939f5dB9556144aB265D642698fa076EA9cF7`](https://sepolia.etherscan.io/address/0x933939f5dB9556144aB265D642698fa076EA9cF7) |
| issuerB | [`0xEC3f9737bbA13ad7ca7f2e404205e06e35A3E5Ac`](https://sepolia.etherscan.io/address/0xEC3f9737bbA13ad7ca7f2e404205e06e35A3E5Ac) |
| O1 | [`0xB09684B117dE9e0b228b381423276a4Cf7F45Cd2`](https://sepolia.etherscan.io/address/0xB09684B117dE9e0b228b381423276a4Cf7F45Cd2) |
| O2 | [`0xE639083317620Cfb7098758a0b9f742a3F80eB3E`](https://sepolia.etherscan.io/address/0xE639083317620Cfb7098758a0b9f742a3F80eB3E) |
| O3 | [`0x4268C1a3c1C01ee17bdFBe03cA4a14e279234AfC`](https://sepolia.etherscan.io/address/0x4268C1a3c1C01ee17bdFBe03cA4a14e279234AfC) |
| O4 | [`0x49DaD8b3a86356A86400151F655961EcE5113953`](https://sepolia.etherscan.io/address/0x49DaD8b3a86356A86400151F655961EcE5113953) |
| verifier | [`0x37DBA424F5528d5345764b509891047513787cdA`](https://sepolia.etherscan.io/address/0x37DBA424F5528d5345764b509891047513787cdA) |
| auditor | [`0x7a68130D23Ecb559f01Cd80d4BAb3c0DB055C4EB`](https://sepolia.etherscan.io/address/0x7a68130D23Ecb559f01Cd80d4BAb3c0DB055C4EB) |
| codeManager | [`0xb28066a9440dD70361c60E9276d8FA9823017299`](https://sepolia.etherscan.io/address/0xb28066a9440dD70361c60E9276d8FA9823017299) |
| plant | [`0xE5D5DF8FD8c775BF7f7d5c99C25557366E8F721F`](https://sepolia.etherscan.io/address/0xE5D5DF8FD8c775BF7f7d5c99C25557366E8F721F) |
| buyer1 | [`0x20057Cbf849408E59D48Aa3D6B241787768958AC`](https://sepolia.etherscan.io/address/0x20057Cbf849408E59D48Aa3D6B241787768958AC) |
| buyer2 | [`0xa8F2B27e7b68802884ED08c61eC0386be0467A49`](https://sepolia.etherscan.io/address/0xa8F2B27e7b68802884ED08c61eC0386be0467A49) |
| outsider | [`0x966c4923f30f47E3ACC87685C624fF40C2Ce3BEe`](https://sepolia.etherscan.io/address/0x966c4923f30f47E3ACC87685C624fF40C2Ce3BEe) |
| buyer3 | [`0xfdb84001Ed810E1Ecc07A5490FA7561A1e7A22bd`](https://sepolia.etherscan.io/address/0xfdb84001Ed810E1Ecc07A5490FA7561A1e7A22bd) |

## Chạy lại

Xem README, mục trình diễn trên testnet Sepolia. Mở dashboard và chọn chain "Sepolia (testnet)" ở thanh bên.
