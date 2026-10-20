# Đồ án A.5 – Registry chứng chỉ I-REC chống double counting

Mã nguồn cho [Final Proposal](<D:/notes/Work/Master/HK1/Blockchain/Đồ án/Proposal/Final Proposal.md>). Kế hoạch code, cấu trúc thư mục và các giai đoạn nằm trong [PLAN.md](PLAN.md). Luồng chạy từng bước, giao diện contract và định dạng message nằm trong [FLOW.md](FLOW.md).

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

## Đặc tả thí nghiệm (mốc 1)

[SPEC.md](SPEC.md) cùng `configs/split.yaml`, `scenarios.yaml`, `features.yaml`, `thresholds.yaml`, `configs/days.csv` và `configs/days_dropped.csv` là đặc tả đã chốt trước khi cài đặt AI. `tests/test_spec.py` kiểm tính nhất quán giữa các file này. [COMPLIANCE.md](COMPLIANCE.md) đối chiếu từng điều khoản I-REC Code v1.11 với chỗ hiện thực và test.

Sinh lại danh sách ngày hợp lệ (1.985 ngày sau khi loại 73 ngày lỗi dữ liệu; đồng thời ghi `artifacts/p2107_15m.parquet`):

```bash
.venv/Scripts/python -m rec.data.days
```

Dựng dataset cho 4 oracle (chạy sau lệnh trên; ghi `artifacts/slots.parquet` một dòng mỗi slot 15 phút, `artifacts/days.parquet` một dòng mỗi ngày):

```bash
.venv/Scripts/python -m rec.data.dataset
```

Sinh tập test (mốc 2; ghi `artifacts/testset/`, chỉ ghi khi bộ kiểm tra generator qua hết):

```bash
.venv/Scripts/python -m rec.generator.cli
```

Chạy E2 off-chain (khớp lớp B trên train, chọn ngưỡng trên val, đánh giá trên tập test đã khóa). Kết quả ghi vào `artifacts/results/<biến thể>/`, tóm tắt ở [RESULTS.md](RESULTS.md):

```bash
.venv/Scripts/python -m rec.experiments.e2 --variant prereg
```

`prereg` là cách tính đúng `spec-v1`. `--select` chọn biến thể hậu kiểm của luật nhất quán, chỉ dùng train và val. `--variant day_only` chạy biến thể đã chọn. Xem `manifests/CHANGES.md`.

Ghi hoặc kiểm hash của mốc 1:

```bash
.venv/Scripts/python -m rec.manifest spec-v1 --check
```

## Hình của proposal

Hai hình trong Final Proposal (mô hình đề xuất, sơ đồ thực nghiệm) được vẽ bằng code, nên sửa được và vẽ lại được:

```bash
.venv/Scripts/python docs/figures/make_figures.py
```

Lệnh này ghi `mo_hinh_de_xuat` và `so_do_thuc_nghiem` (PNG và SVG) vào `docs/figures/`. Sau đó chép hai file PNG sang thư mục `Attachments` của ghi chú đồ án.

## Cấu trúc hiện tại

```
source/
├─ PLAN.md, SPEC.md, FLOW.md, COMPLIANCE.md, RESULTS.md, README.md, pyproject.toml, requirements-lock.txt
├─ configs/        # paths, split, days.csv, scenarios, features, thresholds
├─ rec/            # schema, timeutil, config, manifest; data/, oracles/, generator/, physics/, checks/, model/, gate/, metrics/, experiments/
├─ tests/          # pytest
├─ manifests/      # hash của từng mốc, CHANGES.md
├─ docs/figures/   # script vẽ hình của proposal
└─ contracts/      # Hardhat; contracts/test/ToolchainCheck.sol là contract tạm của giai đoạn 0
```
