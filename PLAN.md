# Kế hoạch code – Đồ án A.5 (thư mục `source/`)

Tài liệu này biến [Final Proposal](<D:/notes/Work/Master/HK1/Blockchain/Đồ án/Proposal/Final Proposal.md>) thành kế hoạch code. Khi hai bên lệch nhau, **proposal là chuẩn**; nếu phải đổi thiết kế thì sửa proposal trước rồi mới sửa code.

## 0. Nguyên tắc

1. **Hai lớp, hai phần code.** Lớp A (sổ cái: khóa, ngân sách CP, vòng đời) nằm trong contract và trong B0 (SQLite). Lớp B (kiểm tra số liệu: đủ báo cáo, nhất quán một phía, trần pvlib hoặc trần AI) là Python thuần, không phụ thuộc nơi lưu trữ.
2. **Một logic quyết định duy nhất.** Lớp B chỉ có một bản cài đặt bằng Python. Bản này được dùng ở hai chỗ:
   - mô phỏng off-chain cho E2 và ablation, vốn cần hàng trăm nghìn quyết định;
   - dịch vụ verifier ký kết quả để contract dùng ở luật ④.

   Một test parity kiểm tra rằng chạy qua chain và chạy mô phỏng cho cùng quyết định.
3. **Nhãn ẩn tách riêng.** Generator ghi nhãn ra file riêng. Không module nào của hệ thống được đánh giá (`gate/sim.py`, `checks`, `model`, `registry`) được đọc file nhãn. Chỉ `metrics` và Production Auditor mô phỏng (`gate/auditor.py`, mục 4.5) được đọc.
4. **Tái lập được.** Mọi kết quả sinh ra từ config + seed + một lệnh chạy. Mốc 1 và mốc 2 của protocol là **git tag** kèm file hash (`manifests/`).
5. **Không đưa dữ liệu gốc vào repo.** Dữ liệu nằm ở `../dataset`; đường dẫn khai trong `configs/paths.yaml`. Sản phẩm trung gian để trong `artifacts/` (gitignore), chỉ commit hash.

## 1. Môi trường

Máy hiện có: Python 3.11.9 (pandas 2.3, numpy 2.3, PyYAML), Node 22.19, npm 11.7, git 2.45. Chưa có pvlib, scikit-learn, pyarrow, web3, eth-account, streamlit, pytest; thư mục `source/` chưa là git repo.

| Phần | Công cụ |
|---|---|
| Python | 3.11, venv `.venv`, cài bằng `pip install -e .[dev]` từ `pyproject.toml` |
| Thư viện Python | pandas, numpy, pyarrow, pvlib, scikit-learn, pyyaml, web3, eth-account (ký EIP-712), streamlit, pytest |
| Contract | Hardhat 2.29 (tag `hh2`, TypeScript), `@nomicfoundation/hardhat-toolbox` 6.1 (ethers v6, chai, gas reporter, typechain), OpenZeppelin Contracts 5.6 (ERC1155, EIP712, ECDSA), Solidity 0.8.28 |
| Chain | Hardhat Network cục bộ; E3 dùng chế độ đào theo khoảng thời gian (không automine) để độ trễ có nghĩa |

Đã ghim ở giai đoạn 0:
- Python: `requirements-lock.txt` (từ `pip freeze`).
- Node: `contracts/package-lock.json`. TypeScript ghim 5.9.3, vì `latest` là TypeScript 7 mà ts-node chưa hỗ trợ.
- Chọn Hardhat 2 thay vì Hardhat 3 vì API và plugin ổn định, nhiều tài liệu, hợp với nhóm chưa có kinh nghiệm.

## 2. Cấu trúc thư mục

```
source/
├─ PLAN.md
├─ SPEC.md                   # đặc tả mốc 1: chỉ số, gán nhãn, ngưỡng, quyết định đã chốt
├─ FLOW.md                   # luồng chạy, giao diện contract, định dạng EIP-712, runner, dashboard
├─ COMPLIANCE.md             # bảng truy vết điều khoản I-REC → hiện thực, test
├─ README.md                 # cách cài, cách chạy từng thí nghiệm
├─ pyproject.toml            # package `rec` + dependencies
├─ configs/
│  ├─ paths.yaml             # trỏ tới ../dataset, artifacts/
│  ├─ split.yaml             # train 2018–2020, val 2021, test 2022–2023 (mốc 1)
│  ├─ days.csv               # 1.985 ngày hợp lệ kèm split (mốc 1, sinh bằng rec.data.days)
│  ├─ days_dropped.csv       # 73 ngày bị loại vì lỗi dữ liệu, kèm lý do
│  ├─ scenarios.yaml         # Bảng 3.2, 3.3: kịch bản, lưới tham số, seed tập test (mốc 1)
│  ├─ features.yaml          # đặc trưng được phép của AI: chỉ O4 + thông số tĩnh (mốc 1)
│  └─ thresholds.yaml        # luật chọn ngưỡng, phân bổ 5% REVIEW nhầm (mốc 1)
├─ rec/                      # Python package
│  ├─ schema.py              # dataclass dùng chung (mục 3)
│  ├─ timeutil.py            # ngày địa phương PST8PDT ↔ số ngày; slot 15 phút
│  ├─ config.py              # đọc configs/ và kiểm tính nhất quán của đặc tả
│  ├─ manifest.py            # hash các file của từng mốc → manifests/
│  ├─ data/                  # load_pvdaq, load_nsrdb, preprocess, daytype
│  ├─ physics/               # pvwatts.py: PVWatts(NSRDB) hiệu chỉnh trên train
│  ├─ generator/             # honest, attacks, labels, checks, cli
│  ├─ oracles/               # sources (O1–O4 đọc từ dữ liệu), signer (EIP-712)
│  ├─ checks/                # completeness ①, consistency (a), ceiling_pvlib, ceiling_ai
│  ├─ model/                 # features, train, calibrate (hồi quy phân vị)
│  ├─ gate/                  # sim.py: DecisionGate mô phỏng ①–④; profiles B0/B1/B2/Proposed; auditor.py
│  ├─ registry/              # base (interface), sqlite_registry (B0 tách/chung), chain_registry (web3)
│  ├─ metrics/               # dcr, oir, lmax, detection, bootstrap
│  └─ experiments/           # e1, e2a, e2b, e3, ablation, run_all
├─ contracts/                # Hardhat project
│  ├─ contracts/             # DeviceRegistry, CertificateRegistry, DecisionGate
│  ├─ test/                  # D1–D6, insider, chữ ký, ngân sách CP
│  ├─ scripts/deploy.ts
│  └─ hardhat.config.ts
├─ dashboard/app.py          # Streamlit + web3.py
├─ docs/figures/             # make_figures.py vẽ Hình 1, Hình 2 của proposal (PNG + SVG)
├─ tests/                    # pytest
├─ manifests/                # sha256 của tập test, mô hình, kết quả (commit)
└─ artifacts/                # parquet, tập test, mô hình, kết quả (gitignore)
```

## 3. Quy ước dữ liệu và giao diện

### 3.1 Đơn vị và thời gian

- **Năng lượng:** số nguyên **Wh** ở mọi nơi (Python, SQLite, contract).
- **Ngày:** ngày **địa phương** của nhà máy (PVDAQ ghi theo `PST8PDT`), mã hóa thành số ngày kể từ 1970-01-01 (`uint32`).
  - Không dùng ngày UTC. Ở California, sản lượng buổi chiều rơi sang ngày UTC hôm sau (khoảng 13:00–03:30 UTC), nên ngày UTC cắt đôi một ngày sản xuất.
  - `analysis/check_nsrdb_vs_pvdaq.py` đang gom năng lượng ngày theo UTC. Con số sai lệch vệ tinh p50 11% / p90 27% cần tính lại theo ngày địa phương, đúng với việc proposal đã ghi là "sẽ tính lại trên 2018–2021".
- **Slot:** 15 phút, nhãn cuối kỳ. Công tơ PVDAQ đánh nhãn đầu kỳ nên dịch +15 phút (đã làm trong `trackA_01_prep.py`).
- **Số liệu thiếu để trống, không điền 0.** Ban ngày khi kiểm tra báo cáo xác định theo vị trí mặt trời.
- **Lô:** chứng chỉ của cả nhà máy (một CP) trong một ngày. Lớp B và kiểm tra ngẫu nhiên xét theo lô; chứng chỉ vẫn phát hành theo từng thiết bị.

### 3.2 Đối tượng dùng chung (`rec/schema.py`)

| Đối tượng | Trường chính | Ghi chú |
|---|---|---|
| `Device` | `device_id`, `cp_id`, `ac_capacity_w`, `issuer` | 6 thiết bị = 6 khối × 4 inverter, cùng `CP-1`. Mã là chuỗi; tầng chain đổi sang bytes32/address |
| `RegistrationTransfer`, `Deregistration` | chuyển đăng ký sang issuer khác (§16.3); đóng đăng ký có ngày hiệu lực | Dùng cho L3 và luật kỳ phát hành §8.2 |
| `IssueRequest` | `req_id`, `issuer`, `device_id`, `day_start`, `wh_per_day[]` | Nhiều ngày một lần để mô phỏng D2 (kỳ 7/30 ngày) |
| `OracleReport` | `oracle` (O1–O4), `subject` (= `cp_id`, mọi oracle báo ở mức CP), `day`, `wh_day`, `max_slot_wh`, `slots_present`, `data_root`, `signature` | `data_root` = hash chuỗi 15 phút; chuỗi đầy đủ lưu trong kho file đặt tên theo `data_root` |
| `Verdict` | `lot_key`, `flags` (inconsistent / missing_report / over_ceiling), `ceiling_wh`, `model_hash`, `reasons[]`, `signature` | Kết quả lớp B cho một lô, do verifier của issuer ký |
| `Decision` | `REJECT(key/budget/capacity/period/oracle)` · `REVIEW(flags)` · `MINT(wh)` | Giống nhau cho mọi cấu hình |
| `Retire` | người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo | I-REC §10: không sửa được sau khi ghi |
| `Event` | `t` (giây mô phỏng), `kind`, payload | Dòng sự kiện do generator sinh; kiểu payload phải khớp `kind` |
| `Label` (file riêng) | `req_id` → `scenario`, `kind` (honest / D / M / L), `excess_wh_true` | Chỉ `metrics` và Production Auditor mô phỏng đọc |

### 3.3 Mô hình chế độ R1 / R2 bằng quyền giữ khóa

- **R1:** khóa ký của O1 thuộc "điện lực" mô phỏng. Kẻ gian không ký được O1 đã sửa.
- **R2:** khóa ký của O1 (và O2, O3) thuộc chủ dự án. Kẻ gian ký được O1 tùy ý, trong phạm vi k nguồn.
- O4 và verifier luôn thuộc issuer.

Cách này cho phép chạy hai chế độ trên cùng một contract, chỉ khác nhau ở việc ai giữ khóa nào.

## 4. Thiết kế từng phần

### 4.1 Lớp A – contract (`contracts/`)

| Contract | Trách nhiệm |
|---|---|
| `DeviceRegistry` | Đăng ký thiết bị → CP, công suất AC, issuer, ngày đăng ký hiệu lực. Từ chối mã trùng (D3 bị chặn ở đây). Chuyển đăng ký sang issuer khác giữ nguyên mã (§16.3); đóng đăng ký có ngày hiệu lực |
| `CertificateRegistry` | ERC-1155 theo Wh; `tokenId = keccak256(deviceId, day)`. Giữ **bitmap ngày theo thiết bị** (①) và **ngân sách `issued[cp][day] ≤ o1[cp][day]`** (②). `transfer`; `retire(id, wh, người thụ hưởng, mục đích, nơi tiêu thụ, kỳ báo cáo)` = burn + event `Retired` (§10). Chỉ `DecisionGate` có quyền mint |
| `DecisionGate` | Hai bước. `submitLotEvidence`: một lần mỗi lô, nhận 4 báo cáo O1–O4 và verdict có chữ ký, lưu O1 và trạng thái lô (CLEAR / REVIEW). `issue`: mỗi thiết bị, kiểm đăng ký, kỳ phát hành (§8.2), ①–③ và trạng thái lô, rồi gọi `CertificateRegistry`. Vi phạm lớp A phát `IssueRejected` (không revert); lô REVIEW phát `IssueHeld`. `resolveReview` do khóa auditor gọi để duyệt hoặc bác lô REVIEW. Chi tiết ở `FLOW.md` |

Các quyết định cụ thể:

- **Bất biến nằm trong `CertificateRegistry`**, không nằm trong gate. Nhờ vậy dù gate có lỗi cũng không phát hành trùng được.
- **Lưu O1 lần đầu.** O1 của một (CP, ngày) được lưu ở lần đầu tiên xuất hiện. Một O1 khác cho cùng (CP, ngày) gửi sau bị từ chối và phát event riêng. Kẻ gian ở R2 vì vậy phải khai tăng ngay từ đầu, đúng với mệnh đề trong proposal.
- **Luật ③ không cần chuỗi 15 phút on-chain.** Báo cáo O1 mang `max_slot_wh`; contract kiểm `max_slot_wh ≤ cap × 0,25 h` và `wh_day ≤ cap × số giờ có nắng`.
- **Kỳ phát hành (§8.2):** ≤ 1 năm và nằm trọn trong một năm dương lịch; không trước ngày đăng ký hiệu lực; không sau ngày đóng đăng ký; không sau thời điểm nộp. Vi phạm → REJECT `period`.
- **Không mint đặc quyền, không nâng cấp**; allowlist oracle, issuer và verifier đặt trong constructor.
- **Vai trò Code Manager (I-REC §11):** một khóa riêng, chỉ có `suspend`/`unsuspend` và `withdraw` cho chứng chỉ chưa retire. Mỗi lời gọi phát event kèm lý do. `withdraw` trả lại ngân sách CP; rút toàn bộ một thiết bị-ngày thì mở lại khóa để phát hành lại qua `DecisionGate`. Chứng chỉ đang bị khóa thì `transfer` và `retire` đều revert.
- **Test Hardhat** gồm: D1–D6 bị revert; mint hợp lệ; chữ ký sai hoặc ngoài allowlist; O1 xung đột; kỳ phát hành sai chuẩn; ví dụ trong proposal (đã phát hành 5,0 MWh tại CP-1, thiết bị X xin thêm 1,67 MWh → REJECT); gas report. Tên test mang mã điều khoản I-REC theo `COMPLIANCE.md`.

### 4.2 B0 – SQLite (`rec/registry/sqlite_registry.py`)

- Cùng các kiểm tra như contract: khóa, ngân sách CP, vòng đời, luật công suất, kỳ phát hành.
- Hai biến thể:
  - **tách biệt:** mỗi issuer một file DB; mỗi `T_rec ∈ {7, 30}` ngày theo đồng hồ mô phỏng, **gộp các DB rồi chạy lại khóa và ngân sách CP** để phát hiện trùng (D3, D4b);
  - **dùng chung:** một file DB.
- Có hàm `operator_edit` (UPDATE/DELETE/phát hành lại, không để dấu vết) để chạy kịch bản insider. Trên contract, issuer không có hàm tương đương; Code Manager chỉ tạm khóa hoặc rút, và luôn để lại event.

Cả ba backend cài cùng một interface `Registry` (`register`, `issue`, `transfer`, `retire`, `operator_edit`), để E1 chạy **cùng một dòng sự kiện** qua cả ba.

### 4.3 Dữ liệu (`rec/data/`)

Chuyển code từ `analysis/trackA_01_prep.py` và `check_nsrdb_vs_pvdaq.py` vào package. Môi trường hiện dùng **pandas 3.x** (copy-on-write mặc định, kiểu chuỗi mặc định), còn hai script trên viết cho pandas 2.3, nên phải kiểm lại từng bước khi chuyển. Sửa lại để:

1. Đọc 24 inverter (5 phút), công tơ (15 phút, dịch +15 phút), POA tại chỗ, nhiệt độ/gió tại chỗ (**nhiệt độ ghi °F**, đổi sang °C); NSRDB 2018–2023 (UTC → `PST8PDT`).
2. Gom về slot 15 phút; giữ ngày có ≥ 95% dữ liệu ban ngày (POA > 20 W/m²), rồi loại ngày lỗi dữ liệu (một nguồn báo 0 cả ngày, hoặc công tơ lệch tổng inverter > 50%). **Đã làm** trong `rec/data/days.py`: 2.058 ngày đủ độ phủ, loại 73, còn **1.985** (train 1.026 / val 321 / test 638).
3. Gắn cờ: thiếu dữ liệu, đoạn treo, clipping (30 kW), ban đêm, inverter ngừng phát (định nghĩa trong `scenarios.yaml`, kiểm tay 50 ngày).
4. Tạo 6 thiết bị (khối 4 inverter) sau `CP-1`.
5. Tính POA từ NSRDB qua pvlib (nghiêng 25°, hướng 180°, tọa độ 38.996306, −122.134111 trong metadata); đặc trưng ngày; phân loại ngày (quang / mây vừa / nhiều mây).
6. Ghi `artifacts/p2107_15m.parquet`, `artifacts/slots.parquet` và `artifacts/days.parquet` (một dòng mỗi ngày: sản lượng thật theo khối và CP, giá trị ngày của O1–O4, độ phủ ban ngày từng oracle, đặc trưng O4, loại ngày, cờ inverter ngừng phát, split).

**Đã làm** (`rec/data/dataset.py`, `rec/data/nsrdb.py`): 190.520 slot của 1.985 ngày; công tơ / tổng inverter trung vị 0,984; độ phủ ban ngày trung vị 100% ở cả 4 oracle; ngưỡng POA ứng với clipping 806 W/m² (720 kW AC / 893 kW DC). Cờ inverter ngừng phát bật ở 1.032/1.985 ngày (52%) khi ban ngày tính theo vị trí mặt trời, cao hơn mức 47% đo theo giữa trưa trước đây. Cần kiểm tay 50 ngày trước khi dùng định nghĩa này. Mã hóa `data_root` ở `rec/oracles/encoding.py`.

### 4.4 Generator (`rec/generator/`)

**Đã làm** (`python -m rec.generator.cli`, kết quả ở `artifacts/testset/`):
- E1: mỗi seed có một dòng hợp lệ (khoảng 9.200 sự kiện, gồm L3), một dòng Production Group (L4), và 8 kịch bản tấn công chèn chồng, mỗi kịch bản 60 ca;
- E2: bảng khoảng 232 nghìn ca, cộng hàm tất định `apply_case`; D5 có 281 ngày đích.

Các điểm lệch so với `spec-v1` ghi ở `manifests/CHANGES.md`.

- **Đầu vào:** `days.parquet`, `scenarios.yaml`, seed.
- **Đầu ra:** `events.jsonl` (dòng sự kiện + báo cáo O1–O4, có thể đã bị sửa ở k nguồn) và `labels.parquet` (ẩn).
- **Dòng hợp lệ:** đăng ký 6 thiết bị; mỗi thiết bị mỗi ngày một yêu cầu đúng sản lượng thật; chuyển nhượng; retire; L3 (chuyển đăng ký), L4 (Production Group).
- **Tấn công:** D1–D6, insider, M1–M3 theo `scenarios.yaml`; **mỗi ngày test đủ điều kiện là một ca**. Ở R2, D4b khai O1 tăng (1 + f) lần; D5 thay chuỗi 15 phút của k nguồn bằng chuỗi của ngày X; M2 có thêm mức α = f để so với D4b (H2b).
- **Bộ kiểm tra** (`checks.py`, chạy như test):
  - dòng sạch có DCR = 0;
  - mọi bản ghi qua cùng bước định dạng (0,1 kW, clipping, 0 ban đêm, slot thiếu để trống);
  - kiểm tra dấu vết nhân tạo: mô hình chỉ nhìn đặc trưng định dạng (số chữ số, làm tròn, vị trí slot trống, lưới thời gian) phải có AUC ≈ 0,5;
  - bản gốc và bản sao cùng tập;
  - xuất 20 mẫu mỗi kịch bản ra ảnh để xem tay.

### 4.5 Lớp B (`rec/checks/`, `rec/model/`, `rec/gate/`)

| Bước | Công thức | Dùng ở |
|---|---|---|
| ① Đủ báo cáo | Thiếu báo cáo, hoặc `slots_present` < 95% số slot ban ngày (theo vị trí mặt trời) → REVIEW | B2, Proposed |
| ② Nhất quán (a), một phía | O1 / (η·O2) − 1 > τ₁₂ và O1 / E₃ − 1 > τ₁₃, ở mức ngày và slot; E₃ từ POA và nhiệt độ tại chỗ (°C). Biến thể hậu kiểm `day_only` bỏ mức slot (`manifests/CHANGES.md`) | B2, Proposed |
| ③ Trần | B2: O1 > PVWatts(NSRDB) · (1 + τ₄). Proposed: O1 > Q̂₀.₉₅(x) · (1 + τ_C) | B2 / Proposed |

Luật công suất ③ và luật kỳ phát hành thuộc lớp A (contract), áp dụng cho mọi cấu hình. Luật khớp ngày cũ (c) đã bỏ.

- **Mô hình AI:** `HistGradientBoostingRegressor(loss="quantile", quantile=0.95, random_state=0)`. Đầu vào chỉ lấy từ `features.yaml`; có test chặn cột O1–O3. Mục tiêu là năng lượng ngày tại công tơ. Huấn luyện trên 2018–2020.
- **Hiệu chỉnh ngưỡng** trên lô trung thực của 2021, theo `thresholds.yaml`: (a) chiếm 1% REVIEW nhầm; riêng trần 4% (mức chính), quét thêm 1%, 2%, 5%, 10% cho mục "Tỉ lệ REVIEW nhầm" (SPEC mục 8).
- **`gate/sim.py`:** hàm thuần `decide(request, reports, state, profile) → Decision`, với `profile` ∈ {B0, B1, B2, Proposed, A1, A2}.
- **Verifier:** gói kết quả lớp B thành `Verdict`, ký EIP-712 kèm hash mô hình.
- **`gate/auditor.py` – Production Auditor mô phỏng** (§8.5), áp dụng cho mọi cấu hình ở R2:
  - lô bị REVIEW được phân xử theo nhãn thật: trung thực thì MINT sau khi duyệt, gian lận thì bác (cách B);
  - kiểm tra ngẫu nhiên p ∈ {0, 1%, 5%} số lô đã MINT; lô gian lận bị bốc trúng thì bị phát hiện, và Code Manager rút phần chưa retire.

  Đây là module duy nhất ngoài `metrics` được đọc nhãn, và chỉ đọc đúng nhãn của lô mà nó đang xét.

### 4.6 Chỉ số (`rec/metrics/`)

- **DCR, tỉ lệ lọt, exposure window, REJECT nhầm (L1, L3, L4):** từ quyết định của từng backend so với nhãn (E1).
- **OIR, precision, recall, tỉ lệ REVIEW nhầm theo L2, L5:** từ quyết định của `gate/sim.py` so với nhãn (E2a). Precision báo cáo ở 3 mức tỷ lệ gian lận (1%, 5%, 20%). D4b và D5 tách dòng trong OIR.
- **M3 (oracle lỗi):** tỷ lệ REVIEW và sai số MWh phát hành, không tính là gian lận.
- **MWh thật bị giữ tạm:** tổng sản lượng thật của các lô trung thực bị REVIEW (E2a, E2b).
- **LMAX:** tính **giải tích** trên 638 lô test, không cần mô phỏng. Với mỗi lô, cấu hình và k, A là mức chặt nhất trong các kiểm tra mà kẻ gian không sửa được (công suất; nhất quán với nguồn chưa bị sửa; trần pvlib hoặc trần AI). LMAX = Σ max(0, A − y) / Σ y, báo cáo theo k và loại ngày (E2b), ở mọi mức của dãy quét tỉ lệ REVIEW nhầm.
- **Khoảng tin cậy 95%:** bootstrap theo ngày; 5 seed.

### 4.7 Thí nghiệm (`rec/experiments/`)

| Exp | Chạy trên | Cách chạy |
|---|---|---|
| E1 | SQLite tách biệt, SQLite dùng chung, chain | Cùng một dòng sự kiện D1–D6 + insider + mẫu âm L1, L3, L4 qua interface `Registry`; ghi điểm chặn, pass/fail, exposure window, REJECT nhầm |
| E2a | `gate/sim.py` (off-chain) | Mỗi ngày test đủ điều kiện là một ca, 5 seed; mẫu âm là mọi lô test trung thực (L2, L5) |
| Parity | chain + `gate/sim.py` | Lấy mẫu vài trăm ca của E2a chạy qua contract; quyết định phải trùng 100% |
| E2b | `metrics/lmax.py` | Giải tích theo k ∈ {1, 2, 3}, loại ngày, và từng mức tỉ lệ REVIEW nhầm của trần |
| E3 | chain | Dòng sự kiện hợp lệ 1 năm; gas mỗi thao tác và mỗi MWh; độ trễ p50/p95 (block mỗi 2 giây); lineage completeness từ event và kho file |
| Ablation | `gate/sim.py` + `lmax.py` | A1 (O3 thay O4 làm đầu vào trần AI), A2 (hồi quy phân vị tuyến tính thay AI) |

E2a gồm hàng chục nghìn quyết định. Chạy trên chain thì quá chậm, nên E2 chạy off-chain và dựa vào test parity để chứng minh kết quả giống chain.

### 4.8 Dashboard (`dashboard/app.py`)

Streamlit + web3.py đọc event từ Hardhat:

- lineage từng chứng chỉ: thiết bị → báo cáo O1–O4 (mở file gốc theo `data_root`) → verdict + reason code → mint → transfer → retire;
- hàng đợi REVIEW cho auditor, kèm bằng chứng (cờ, reason code, báo cáo O1–O4); lý do REJECT;
- tỷ lệ lineage completeness.

## 5. Các giai đoạn

| GĐ | Việc | Đầu ra / xong khi |
|---|---|---|
| 0. Dựng repo | `git init`; `pyproject.toml`; Hardhat trong `contracts/`; `.gitignore`; README cài đặt; `rec/schema.py`, `rec/timeutil.py` | **Xong** (commit `b2a985e`) |
| 1. Đặc tả (mốc 1) | `split.yaml`, `scenarios.yaml`, `features.yaml`, `thresholds.yaml`; `SPEC.md`; `COMPLIANCE.md`; `rec/config.py` kiểm tính nhất quán; `configs/days.csv`, `days_dropped.csv` từ `rec.data.days` | **Tag `spec-v1`** + `manifests/spec-v1.sha256` |
| 2. Dữ liệu + generator (mốc 2) | `rec/data`, `rec/physics`; tính lại sai lệch vệ tinh và độ rộng trần theo loại ngày trên 2018–2021 (ngày địa phương); kiểm tay 50 ngày inverter ngừng phát; `rec/generator` + bộ kiểm tra; sinh tập test | Bộ kiểm tra generator qua; **tag `testset-v1`** + sha256 tập test |
| 3. Lớp A | 3 contract + test Hardhat (mang mã điều khoản I-REC); `sqlite_registry` (2 biến thể); `chain_registry`; E1 | D1–D6 bị chặn đúng điểm chặn trên SQLite dùng chung và chain; L1, L3, L4 không bị REJECT; bảng E1 ra được. **Đã làm:** 3 contract, 37 test Hardhat mang mã điều khoản, `rec/registry/` (3 backend), `rec/experiments/runner.py`, `e1.py`; kết quả ở [RESULTS.md](RESULTS.md) |
| 4. Lớp B | `oracles` + signer; `checks`; `model` (train, calibrate); `gate/sim.py`, `gate/auditor.py`; `metrics`; E2a, E2b chạy off-chain | Bảng E2a, E2b có khoảng tin cậy, ở mọi mức tỉ lệ REVIEW nhầm; test chặn rò đặc trưng O1–O3 qua. **Đã chạy off-chain** (commit `b76c094` là bản đăng ký trước; biến thể hậu kiểm `day_only`); kết quả ở [RESULTS.md](RESULTS.md). Còn `gate/auditor.py` |
| 5. Tích hợp | Verifier ký `Verdict`; nối vào `DecisionGate`; kho file theo `data_root`; test parity; E3; dashboard; ablation | Parity 100%; bảng E3; dashboard hiện đủ lineage |
| 6. Kết quả | `run_all` sinh lại toàn bộ bảng và hình từ tag; `manifests/results.sha256` | Chạy lại trên máy khác ra cùng số |

**Phụ thuộc:**

```
GĐ0 → GĐ1 → GĐ2 ─┬→ GĐ4 ─┐
           GĐ3 ──┴────────┴→ GĐ5 → GĐ6
```

- GĐ3 (contract, B0) chỉ cần `schema.py` của GĐ0 và đặc tả kịch bản D của GĐ1, nên làm song song với GĐ2 được.
- GĐ4 cần dữ liệu của GĐ2. Riêng phần mô hình AI phải chờ **sau mốc 2** mới cài đặt.

**Quy tắc kiểm soát:**

- Chưa có tag `spec-v1` hoặc `testset-v1` → chưa cài đặt mô hình AI.
- Sau `testset-v1`, mọi thay đổi generator hay tập test phải ghi lý do trong `manifests/CHANGES.md`.
- Nếu pipeline B1 end-to-end chậm → cắt ablation và phần tổng quát hóa sang hệ 10 trước. Không cắt dashboard, chỉ số truy vết hay baseline nào đề bài yêu cầu.

## 6. Kiểm thử

| Lớp test | Nội dung |
|---|---|
| Đơn vị (pytest) | `timeutil` (ranh giới ngày địa phương, đổi giờ mùa hè); từng bước ①–③ của lớp B với ca dựng tay (kể cả luật (a) không báo khi O1 thấp hơn); DCR, OIR, LMAX trên ví dụ tính tay |
| Dữ liệu | 1.985 ngày hợp lệ đúng như `split.yaml`; không ngày nào nằm ở hai split; ngày bị loại có lý do; tổng 24 inverter ≈ công tơ (trong giới hạn η) |
| Generator | Toàn bộ bộ kiểm tra ở 4.4 |
| Rò rỉ | Mô hình AI không nhận cột O1–O3; ngoài `metrics` và `gate/auditor.py`, không module nào import file nhãn |
| Contract (Hardhat) | D1–D6 đúng điểm chặn, insider, chữ ký, O1 xung đột, kỳ phát hành §8.2, chuyển đăng ký §16.3, retire đủ trường §10, quyền Code Manager §11 (khóa, rút, không mint, không chạm chứng chỉ đã retire), ví dụ 5,0 + 1,67 MWh; bất biến qua chuỗi thao tác ngẫu nhiên (không MWh nào bị tính hai lần; tổng cung = phát hành − retire) |
| Tuân thủ | Mỗi dòng "Đã thiết kế" trong `COMPLIANCE.md` có ít nhất một test mang mã điều khoản |
| Parity | Mẫu E2a: chain và `gate/sim.py` cho cùng quyết định |

## 7. Quyết định thiết kế

Toàn bộ quyết định đã chốt nằm ở `SPEC.md` mục 10.

## 8. Lệnh chạy dự kiến

```
pip install -e .[dev]
python -m rec.data.preprocess --paths configs/paths.yaml
python -m rec.generator.cli --scenarios configs/scenarios.yaml --split test
cd contracts && npx hardhat test
python -m rec.experiments.e1                      # 3 backend × 5 seed; --run-only/--metrics-only để chạy chain song song
python -m rec.experiments.e2 --variant prereg     # E2a + E2b, đúng spec-v1
python -m rec.experiments.e2 --select             # chọn biến thể hậu kiểm, chỉ trên val
python -m rec.experiments.e2 --variant day_only   # biến thể hậu kiểm đã chọn
python -m rec.experiments.e3
streamlit run dashboard/app.py
python -m rec.experiments.run_all
```
