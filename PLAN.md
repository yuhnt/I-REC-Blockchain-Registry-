# Kế hoạch code – Đồ án A.5 (thư mục `source/`)

Tài liệu này biến [Final Proposal](<D:/notes/Work/Master/HK1/Blockchain/Đồ án/Proposal/Final Proposal.md>) thành kế hoạch code. Khi hai bên lệch nhau, **proposal là chuẩn**; nếu phải đổi thiết kế thì sửa proposal trước rồi mới sửa code.

## 0. Nguyên tắc

1. **Hai lớp, hai phần code.** Lớp A (sổ cái: khóa, ngân sách CP, vòng đời) nằm trong contract và trong B0 (SQLite). Lớp B (kiểm tra số liệu: nhất quán, trần, khớp lịch sử, AI) là Python thuần, không phụ thuộc nơi lưu trữ.
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
├─ README.md                 # cách cài, cách chạy từng thí nghiệm
├─ pyproject.toml            # package `rec` + dependencies
├─ configs/
│  ├─ paths.yaml             # trỏ tới ../dataset, artifacts/
│  ├─ split.yaml             # train 2018–2020, val 2021, test 2022–2023 (mốc 1)
│  ├─ scenarios.yaml         # Bảng 3.2, 3.3: kịch bản, lưới tham số, seed tập test (mốc 1)
│  ├─ features.yaml          # đặc trưng được phép của AI: chỉ O4 + thông số tĩnh (mốc 1)
│  └─ thresholds.yaml        # luật chọn ngưỡng, phân bổ 5% REVIEW nhầm (mốc 1)
├─ rec/                      # Python package
│  ├─ schema.py              # dataclass dùng chung (mục 3)
│  ├─ timeutil.py            # ngày địa phương PST8PDT ↔ số ngày; slot 15 phút
│  ├─ data/                  # load_pvdaq, load_nsrdb, preprocess, daytype
│  ├─ physics/               # pvwatts.py: PVWatts(NSRDB) hiệu chỉnh trên train
│  ├─ generator/             # honest, attacks, labels, checks, cli
│  ├─ oracles/               # sources (O1–O4 đọc từ dữ liệu), signer (EIP-712)
│  ├─ checks/                # capacity ③, consistency (a), ceiling_pvlib (b), history (c), ceiling_ai (C)
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

### 3.2 Đối tượng dùng chung (`rec/schema.py`)

| Đối tượng | Trường chính | Ghi chú |
|---|---|---|
| `Device` | `device_id`, `cp_id`, `ac_capacity_w`, `issuer` | 6 thiết bị = 6 khối × 4 inverter, cùng `CP-1`. Mã là chuỗi; tầng chain đổi sang bytes32/address |
| `IssueRequest` | `req_id`, `issuer`, `device_id`, `day_start`, `wh_per_day[]` | Nhiều ngày một lần để mô phỏng D2 (kỳ 7/30 ngày) |
| `OracleReport` | `oracle_id` (O1–O4), `cp_id` hoặc `device_id`, `day`, `wh_day`, `max_slot_wh`, `data_root`, `signature` | `data_root` = hash chuỗi 15 phút; chuỗi đầy đủ nằm off-chain |
| `Verdict` | `batch_key`, `flags` (inconsistent / history / over_ceiling), `ceiling_wh`, `model_hash`, `reasons[]`, `signature` | Kết quả lớp B, do verifier của issuer ký |
| `Decision` | `REJECT(①/②/③)` · `REVIEW(flags)` · `MINT(wh)` | Giống nhau cho mọi cấu hình |
| `Event` | `t` (giây mô phỏng), `kind` (register / report / request / transfer / retire / operator_edit), payload | Dòng sự kiện do generator sinh; kiểu payload phải khớp `kind` |
| `Label` (file riêng) | `req_id` → `scenario`, `kind` (honest / D / M / L), `excess_wh_true` | Chỉ `metrics` đọc |

### 3.3 Mô hình chế độ R1 / R2 bằng quyền giữ khóa

- **R1:** khóa ký của O1 thuộc "điện lực" mô phỏng. Kẻ gian không ký được O1 đã sửa.
- **R2:** khóa ký của O1 (và O2, O3) thuộc chủ dự án. Kẻ gian ký được O1 tùy ý, trong phạm vi k nguồn.
- O4 và verifier luôn thuộc issuer.

Cách này cho phép chạy hai chế độ trên cùng một contract, chỉ khác nhau ở việc ai giữ khóa nào.

## 4. Thiết kế từng phần

### 4.1 Lớp A – contract (`contracts/`)

| Contract | Trách nhiệm |
|---|---|
| `DeviceRegistry` | Đăng ký thiết bị → CP, công suất AC, issuer. Chỉ issuer được cấp quyền lúc deploy mới đăng ký được |
| `CertificateRegistry` | ERC-1155 theo Wh; `tokenId = keccak256(deviceId, day)`. Giữ **bitmap ngày theo thiết bị** (①) và **ngân sách `issued[cp][day] ≤ o1[cp][day]`** (②). `transfer`; `retire(id, wh, beneficiary)` = burn + event `Retired`. Chỉ `DecisionGate` có quyền mint |
| `DecisionGate` | Nhận `IssueRequest` + báo cáo O1–O4 có chữ ký + `Verdict` có chữ ký. Kiểm tra chữ ký theo allowlist, luật công suất ③, rồi gọi `CertificateRegistry` (nơi thực thi ① ②). `Verdict.flags ≠ 0` → event `Review`, không mint |

Các quyết định cụ thể:

- **Bất biến nằm trong `CertificateRegistry`**, không nằm trong gate. Nhờ vậy dù gate có lỗi cũng không phát hành trùng được.
- **Lưu O1 lần đầu.** O1 của một (CP, ngày) được lưu ở lần đầu tiên xuất hiện. Một O1 khác cho cùng (CP, ngày) gửi sau bị từ chối và phát event riêng. Kẻ gian ở R2 vì vậy phải khai tăng ngay từ đầu, đúng với mệnh đề trong proposal.
- **Luật ③ không cần chuỗi 15 phút on-chain.** Báo cáo O1 mang `max_slot_wh`; contract kiểm `max_slot_wh ≤ cap × 0,25 h` và `wh_day ≤ cap × số giờ có nắng`.
- **Không có hàm admin.** Không có mint đặc quyền, không cho nâng cấp; allowlist oracle và verifier đặt trong constructor. Đây là phần trả lời kịch bản insider.
- **Test Hardhat** gồm: D1–D6 bị revert; mint hợp lệ; chữ ký sai hoặc ngoài allowlist; O1 xung đột; ví dụ trong proposal (đã phát hành 5,0 MWh tại CP-1, thiết bị X xin thêm 1,67 MWh → REJECT); gas report.

### 4.2 B0 – SQLite (`rec/registry/sqlite_registry.py`)

- Cùng các kiểm tra như contract: khóa, ngân sách CP, vòng đời, luật công suất.
- Hai biến thể:
  - **tách biệt:** mỗi issuer một file DB; đối soát chéo mỗi `T_rec ∈ {7, 30}` ngày theo đồng hồ mô phỏng;
  - **dùng chung:** một file DB.
- Có hàm `operator_edit` (UPDATE/DELETE/phát hành lại) để chạy kịch bản insider. Contract không có hàm tương đương.

Cả ba backend cài cùng một interface `Registry` (`register`, `issue`, `transfer`, `retire`, `operator_edit`), để E1 chạy **cùng một dòng sự kiện** qua cả ba.

### 4.3 Dữ liệu (`rec/data/`)

Chuyển code từ `analysis/trackA_01_prep.py` và `check_nsrdb_vs_pvdaq.py` vào package. Môi trường hiện dùng **pandas 3.x** (copy-on-write mặc định, kiểu chuỗi mặc định), còn hai script trên viết cho pandas 2.3, nên phải kiểm lại từng bước khi chuyển. Sửa lại để:

1. Đọc 24 inverter (5 phút), công tơ (15 phút, dịch +15 phút), POA tại chỗ, nhiệt độ/gió tại chỗ; NSRDB 2018–2023 (UTC → `PST8PDT`).
2. Gom về slot 15 phút; giữ ngày có ≥ 95% dữ liệu ban ngày (POA > 20 W/m²) → kỳ vọng ra **2.058 ngày**, chia **1.057 / 360 / 641**. Lệch con số này nghĩa là pipeline đã khác bản sơ bộ, phải giải thích được.
3. Gắn cờ: thiếu dữ liệu, đoạn treo, clipping (30 kW), ban đêm.
4. Tạo 6 thiết bị (khối 4 inverter) sau `CP-1`.
5. Tính POA từ NSRDB qua pvlib (nghiêng 25°, hướng 180°, tọa độ 38.996306, −122.134111 trong metadata); đặc trưng ngày; phân loại ngày (quang / mây vừa / nhiều mây).
6. Ghi `artifacts/p2107_15m.parquet`, `artifacts/days.parquet` (một dòng mỗi ngày: sản lượng thật theo khối và CP, đặc trưng O4, loại ngày, split).

### 4.4 Generator (`rec/generator/`)

- **Đầu vào:** `days.parquet`, `scenarios.yaml`, seed.
- **Đầu ra:** `events.jsonl` (dòng sự kiện + báo cáo O1–O4, có thể đã bị sửa ở k nguồn) và `labels.parquet` (ẩn).
- **Dòng hợp lệ:** đăng ký 6 thiết bị; mỗi thiết bị mỗi ngày một yêu cầu đúng sản lượng thật; chuyển nhượng; retire; L3 (chuyển issuer), L4 (Production Group).
- **Tấn công:** D1–D6, insider, M1–M3 đúng tham số Bảng 3.2. Ở R2, D4b và D5 khai O1 tăng tương ứng; M2 có thêm mức α = f để so với D4b (H2b).
- **Bộ kiểm tra** (`checks.py`, chạy như test):
  - dòng sạch có DCR = 0;
  - mọi bản ghi qua cùng bước định dạng (0,1 kW, clipping, 0 ban đêm, mẫu thiếu);
  - adversarial validation AUC ≈ 0,5;
  - bản gốc và bản sao cùng tập;
  - xuất 20 mẫu mỗi kịch bản ra ảnh để xem tay.

### 4.5 Lớp B (`rec/checks/`, `rec/model/`, `rec/gate/`)

| Luật | Công thức | Dùng ở |
|---|---|---|
| ③ công suất | slot ≤ cap × 0,25 h; ngày ≤ cap × giờ có nắng | B0, B1, B2, Proposed |
| (a) nhất quán | \|O1 / (η·O2) − 1\| > τ₁₂ ở mức ngày và slot; tương tự với O3 | B2, Proposed |
| (b) trần vật lý | O1 > PVWatts(NSRDB) · (1 + τ₄) | B2 |
| (c) khớp lịch sử | khoảng cách phần dư (so với pvlib) giữa ngày khai và một ngày đã phát hành < δ | B2, Proposed |
| C trần AI | O1 > C, với C là phân vị trên của hồi quy phân vị | Proposed |

- **Mô hình AI:** `HistGradientBoostingRegressor(loss="quantile")` của scikit-learn. Đầu vào chỉ lấy từ `features.yaml`; có một test để chặn việc lỡ đưa cột O1–O3 vào. Mục tiêu là năng lượng ngày tại công tơ. Huấn luyện trên 2018–2020, chọn phân vị trên 2021.
- **Hiệu chỉnh ngưỡng:** tất cả trên ngày trung thực của 2021, theo `thresholds.yaml`, sao cho tổng REVIEW nhầm của luật ④ bằng 5% (thêm một bản ở 1% để phân tích độ nhạy).
- **`gate/sim.py`:** hàm thuần `decide(request, reports, state, profile) → Decision`, với `profile` ∈ {B0, B1, B2, Proposed, A1, A2, A3}.
- **Verifier:** gói kết quả lớp B thành `Verdict`, ký EIP-712 kèm hash mô hình.
- **`gate/auditor.py` – Production Auditor mô phỏng** (§8.5.4), áp dụng cho mọi cấu hình ở R2:
  - batch bị REVIEW được xử lý đúng theo nhãn thật (quy ước của proposal);
  - lấy mẫu ngẫu nhiên p% batch đã MINT để kiểm toán; phân tích độ nhạy theo p.
  
  Đây là module duy nhất ngoài `metrics` được đọc nhãn, và chỉ đọc đúng nhãn của batch mà nó đang kiểm toán.

### 4.6 Chỉ số (`rec/metrics/`)

- **DCR, exposure window:** từ quyết định của từng backend so với nhãn (E1).
- **OIR, precision, recall, recall@FPR 1%/5%, tỷ lệ REVIEW nhầm theo L1–L5:** từ quyết định của `gate/sim.py` so với nhãn (E2a). Precision báo cáo ở 3 mức tỷ lệ gian lận (1%, 5%, 20%). D4b và D5 tách dòng trong OIR.
- **M3 (oracle lỗi):** tỷ lệ REVIEW và sai số MWh phát hành, không tính là gian lận.
- **MWh thật bị giữ lại:** tổng sản lượng thật của các batch trung thực bị REVIEW (E2a, E2b).
- **LMAX:** tính **giải tích** trên 641 ngày test, không cần mô phỏng. Với mỗi ngày, cấu hình và k, A là mức chặt nhất trong các kiểm tra mà kẻ gian không sửa được (công suất; nhất quán với nguồn chưa bị sửa; trần pvlib hoặc C). LMAX = Σ max(0, A − y) / Σ y, báo cáo theo k và loại ngày (E2b).
- **Khoảng tin cậy 95%:** bootstrap theo ngày; 5 seed.

### 4.7 Thí nghiệm (`rec/experiments/`)

| Exp | Chạy trên | Cách chạy |
|---|---|---|
| E1 | SQLite tách biệt, SQLite dùng chung, chain | Cùng một dòng sự kiện D1–D6 + insider qua interface `Registry`; ghi pass/fail và exposure window |
| E2a | `gate/sim.py` (off-chain) | Mỗi tổ hợp (cấu hình × kịch bản × tham số × seed) 200 trường hợp tấn công; mẫu âm là mọi ngày test hợp lệ |
| Parity | chain + `gate/sim.py` | Lấy mẫu vài trăm trường hợp của E2a chạy qua contract; quyết định phải trùng 100% |
| E2b | `metrics/lmax.py` | Giải tích theo k ∈ {1, 2, 3} và loại ngày |
| E3 | chain | Dòng sự kiện hợp lệ 1 năm; gas mỗi thao tác và mỗi MWh; độ trễ p50/p95 (đào theo khoảng thời gian); lineage completeness từ event |
| Ablation | `gate/sim.py` + `lmax.py` | A1 (O3 thay O4), A2 (bỏ luật (c)), A3 (hồi quy phân vị tuyến tính) |

E2a ước tính khoảng 10⁵ quyết định. Chạy trên chain thì quá chậm, nên E2 chạy off-chain và dựa vào test parity để chứng minh kết quả giống chain.

### 4.8 Dashboard (`dashboard/app.py`)

Streamlit + web3.py đọc event từ Hardhat:

- lineage từng chứng chỉ: thiết bị → báo cáo O1–O4 → verdict + reason code → mint → transfer → retire;
- hàng đợi REVIEW, lý do REJECT;
- tỷ lệ lineage completeness.

## 5. Các giai đoạn

| GĐ | Việc | Phụ trách | Đầu ra / xong khi |
|---|---|---|---|
| 0. Dựng repo | `git init`; `pyproject.toml`; `npx hardhat init` trong `contracts/`; `.gitignore` (`artifacts/`, `.venv/`, `node_modules/`); README cài đặt; `rec/schema.py`, `rec/timeutil.py` | TV1, TV4 | `pytest` và `npx hardhat test` chạy được trên repo rỗng |
| 1. Đặc tả (mốc 1) | `split.yaml`, `scenarios.yaml`, `features.yaml`, `thresholds.yaml`; định nghĩa chỉ số và quy tắc gán nhãn R1/R2 viết trong README | TV2 (kịch bản), TV3 (split, features), TV4 (chỉ số) | **Tag `spec-v1`** + `manifests/spec-v1.sha256` |
| 2. Dữ liệu + generator (mốc 2) | `rec/data`, `rec/physics`; tính lại sai lệch vệ tinh và độ rộng trần theo loại ngày trên 2018–2021 (ngày địa phương); `rec/generator` + bộ kiểm tra; sinh tập test | TV3 (dữ liệu), TV2 (generator) | 2.058 ngày đúng như bản sơ bộ; bộ kiểm tra generator qua; **tag `testset-v1`** + sha256 tập test |
| 3. Lớp A | 3 contract + test Hardhat; `sqlite_registry` (2 biến thể); `chain_registry`; E1 | TV1 (contract), TV4 (B0, E1) | D1–D6 bị chặn trên SQLite dùng chung và chain; bảng E1 ra được |
| 4. Lớp B | `oracles` + signer; `checks`; `model` (train, calibrate); `gate/sim.py`; `metrics`; E2a, E2b chạy off-chain | TV3 (model, checks), TV4 (metrics, E2) | Bảng E2a, E2b có khoảng tin cậy; test chặn rò đặc trưng O1–O3 qua |
| 5. Tích hợp | Verifier ký `Verdict`; nối vào `DecisionGate`; test parity; E3; dashboard; ablation | Cả nhóm | Parity 100%; bảng E3; dashboard hiện đủ lineage |
| 6. Kết quả | `run_all` sinh lại toàn bộ bảng và hình từ tag; `manifests/results.sha256` | Cả nhóm | Chạy lại trên máy khác ra cùng số |

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
| Đơn vị (pytest) | `timeutil` (ranh giới ngày địa phương, đổi giờ mùa hè); từng luật ③, (a), (b), (c), C với ca dựng tay; DCR, OIR, LMAX trên ví dụ tính tay |
| Dữ liệu | Số ngày hợp lệ = 2.058; không có ngày nào nằm ở hai split; tổng 6 khối ≈ công tơ (trong giới hạn η) |
| Generator | Toàn bộ bộ kiểm tra ở 4.4 |
| Rò rỉ | Mô hình AI không nhận cột O1–O3; ngoài `metrics` và `gate/auditor.py`, không module nào import file nhãn |
| Contract (Hardhat) | D1–D6, insider, chữ ký, O1 xung đột, ví dụ 5,0 + 1,67 MWh |
| Parity | Mẫu E2a: chain và `gate/sim.py` cho cùng quyết định |

## 7. Việc phải chốt ở mốc 1

1. **Phân bổ 5% REVIEW nhầm** giữa (a), (c) và trần. Đề xuất: (a) và (c) mỗi luật 1% trên validation, trần lấy phần còn lại. Phân bổ này dùng chung cho B2 và Proposed.
2. **Công thức nhất quán với O3:** O1 so với sản lượng kỳ vọng từ POA tại chỗ (mô hình tuyến tính có hiệu chỉnh nhiệt độ, khớp trên train), cùng ngưỡng τ₁₂ hay ngưỡng riêng.
3. **Đồng hồ mô phỏng cho exposure window:** báo cáo hằng ngày, đối soát mỗi `T_rec`; exposure tính bằng ngày.
4. **Chế độ đào của Hardhat cho E3:** khoảng thời gian giữa các block.
5. **Định nghĩa "giờ có nắng"** cho luật ③ theo ngày: từ góc thiên đỉnh của pvlib.
6. **Lưới p của Production Auditor**, ví dụ p ∈ {0%, 1%, 5%}, và cách kiểm toán phát hiện một batch gian lận (phát hiện chắc chắn khi batch được chọn).

## 8. Lệnh chạy dự kiến

```
pip install -e .[dev]
python -m rec.data.preprocess --paths configs/paths.yaml
python -m rec.generator.cli --scenarios configs/scenarios.yaml --split test
cd contracts && npx hardhat test
python -m rec.experiments.e1
python -m rec.experiments.e2a
python -m rec.experiments.e2b
python -m rec.experiments.e3
streamlit run dashboard/app.py
python -m rec.experiments.run_all
```
