# Đồ án A.5 – Registry chứng chỉ I-REC chống double counting

Mã nguồn cho [Final Proposal](<D:/notes/Work/Master/HK1/Blockchain/Đồ án/Proposal/Final Proposal.md>). Kế hoạch code, cấu trúc thư mục và các giai đoạn nằm trong [PLAN.md](PLAN.md).

Hệ thống có hai lớp tách rời:

- **Lớp A – sổ cái chung** (`contracts/`, `rec/registry/`): khóa (thiết bị, ngày), ngân sách năng lượng tại điểm đấu nối (CP), trạng thái vòng đời. Lớp này chặn double counting.
- **Lớp B – kiểm tra số liệu** (`rec/checks/`, `rec/model/`, `rec/gate/`): multi-oracle O1–O4 và trần sản lượng học từ vệ tinh. Lớp này phát hiện khai khống.

## Cài đặt

Yêu cầu: Python 3.11+, Node 22+, git.

**Python** (chạy trong `source/`):

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -e ".[dev]"
```

Trên macOS/Linux, thay `.venv/Scripts/python` bằng `.venv/bin/python`. Phiên bản đã kiểm tra được ghi trong `requirements-lock.txt`; muốn dựng lại đúng môi trường thì cài theo file đó:

```bash
.venv/Scripts/python -m pip install -r requirements-lock.txt
```

**Contract** (chạy trong `source/contracts/`):

```bash
npm ci
```

Dùng Hardhat 2 (tag `hh2`) kèm `@nomicfoundation/hardhat-toolbox` 6, OpenZeppelin Contracts 5.6, Solidity 0.8.28. TypeScript được ghim ở 5.9, vì ts-node chưa chạy với TypeScript 7.

## Chạy test

```bash
.venv/Scripts/python -m pytest
```

```bash
cd contracts && npx hardhat test
```

Đo gas khi chạy test:

```bash
cd contracts && REPORT_GAS=true npx hardhat test
```

## Dữ liệu

Dữ liệu gốc **không** nằm trong repo. Đường dẫn khai trong [configs/paths.yaml](configs/paths.yaml), mặc định là `../dataset`:

- `pvdaq-systems-2105-2107/2107_*`: PVDAQ hệ 2107 (công tơ 15 phút, 24 inverter 5 phút, POA, môi trường);
- `nsrdb/nsrdb_conus_v4_2107_<năm>_5min.csv`: NSRDB GOES CONUS v4, 2018–2023.

Sản phẩm trung gian (parquet, tập test, mô hình, kết quả) ghi vào `artifacts/` (không commit). Hash của chúng được commit trong `manifests/`.

## Quy ước

- Năng lượng: số nguyên **Wh** ở mọi nơi.
- Ngày: ngày **địa phương** của nhà máy (America/Los_Angeles, tương đương PST8PDT của PVDAQ), mã hóa thành số ngày kể từ 1970-01-01. Không dùng ngày UTC. Xem [rec/timeutil.py](rec/timeutil.py).
- Slot 15 phút, nhãn cuối kỳ.
- Đối tượng dùng chung (thiết bị, yêu cầu phát hành, báo cáo oracle, verdict, quyết định, sự kiện, nhãn) nằm trong [rec/schema.py](rec/schema.py).
- Nhãn ẩn của generator chỉ được đọc bởi `rec/metrics` và Production Auditor mô phỏng.

## Cấu trúc hiện tại

```
source/
├─ PLAN.md, README.md, pyproject.toml, requirements-lock.txt
├─ configs/paths.yaml
├─ rec/            # schema.py, timeutil.py (các module khác thêm dần theo PLAN.md)
├─ tests/          # pytest
└─ contracts/      # Hardhat; contracts/test/ToolchainCheck.sol là contract tạm của giai đoạn 0
```
