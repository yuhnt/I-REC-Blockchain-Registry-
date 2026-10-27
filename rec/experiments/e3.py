"""E3: chi phí và truy vết trên chain (SPEC mục 7; scenarios.yaml `experiments.E3`).

Hai phần:
1. **Gas và lineage** (automine): dòng hợp lệ 365 ngày đầu của tập test (seed 101, 6 thiết bị, có L3) qua contract,
   với verdict do verifier ký theo từng cấu hình B1, B2, Proposed. Lô REVIEW được auditor duyệt lúc 23:00 ngày d + 1
   (dòng hợp lệ, nên đều đúng) rồi issuer gửi lại. Chuỗi 15 phút của 4 oracle và file reason code ghi vào kho file
   `artifacts/store/`. Gas không phụ thuộc chế độ đào block.
2. **Độ trễ** (block mỗi 2 giây, SPEC mục 10.18): 30 ngày đầu, cấu hình B1, gửi tuần tự từng giao dịch rồi chờ
   receipt. Trước mỗi giao dịch chờ một khoảng ngẫu nhiên đều trong [0, 2) giây, để thời điểm đến không bám nhịp
   block (gửi ngay sau receipt thì giao dịch nào cũng chờ trọn 2 giây). Chain khởi đầu sau dòng sự kiện, nên luật
   "kỳ đã kết thúc" luôn qua mà không cần đặt timestamp.

Lineage completeness = % chứng chỉ dựng lại được đủ chuỗi chỉ từ event on-chain và kho file:
đăng ký thiết bị → bằng chứng của lô (4 data_root, file khớp hash) → [REVIEW: reason code, phân xử] → Issued
→ mọi lần chuyển nhượng, retire và rút của Code Manager khớp số dư.

Chạy: python -m rec.experiments.e3 [--days 365] [--latency-days 30]
Ghi artifacts/results/e3/: gas.csv, gas_summary.csv, lineage.csv, summary.json (tất định);
latency.csv, latency_summary.json (đo theo đồng hồ thật, không vào manifest kết quả).
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd

from rec import config
from rec.gate.verifier import Verifier
from rec.generator.common import load_days
from rec.oracles.store import FileStore
from rec.registry.lineage import lineage
from rec.sim.evidence import make_verdict
from rec.sim.runner import load_stream, plant_from_config, run_stream, truncate

CONFIGS = ("B1", "B2", "Proposed")
SEED = 101


def _arg(argv, name, default):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from rec.registry.chain_registry import ChainRegistry
    from rec.registry.hardhat import HardhatNode

    n_days = int(_arg(argv, "--days", str(config.load("scenarios")["experiments"]["E3"]["stream_days"])))
    lat_days = int(_arg(argv, "--latency-days", "30"))
    port = int(_arg(argv, "--port", "8552"))
    scen = config.load("scenarios")
    plant = plant_from_config(scen["plant"])
    artifacts = config.resolve_path("artifacts")
    out = artifacts / "results" / "e3"
    out.mkdir(parents=True, exist_ok=True)
    days_df, data = load_days()
    slots = pd.read_parquet(artifacts / "slots.parquet")
    temps = {int(d): g["site_temp_c"].to_numpy(float) for d, g in slots.groupby("day", sort=True)}
    slot_ends = {int(d): [t.isoformat() for t in g.index] for d, g in slots.groupby("day", sort=True)}
    sun = dict(zip(days_df["day"].astype(int), days_df["sun_slots"].astype(int)))
    test_days = sorted(int(d) for d in days_df.loc[days_df["split"] == "test", "day"])
    events = load_stream(artifacts / "testset" / "e1", f"honest_s{SEED}")
    store = FileStore(artifacts / "store")
    issuer_a = scen["plant"]["issuers"][0]

    gas_rows, lin_frames, summary = [], [], {"days": n_days, "configs": {}}
    node = HardhatNode(port)
    try:
        chain = ChainRegistry(plant, node.url)
        for c in CONFIGS:
            chain.reset()
            chain.gas_log = []
            verifier = None if c == "B1" else Verifier(c)
            ev = truncate(events, test_days[0], n_days)
            t0 = time.time()
            log = pd.DataFrame(run_stream(chain, ev, sun, issuer_a, make_verdict(verifier, data, temps, slot_ends, chain,
                                                                                    store), auditor=lambda cp, d: True))
            gas_rows += [{"config": c, "op": op, "gas": g} for op, g in chain.gas_log]
            lin = lineage(chain, store).assign(config=c)
            lin_frames.append(lin)
            minted_wh = int(log["minted_wh"].sum())
            issuance_gas = sum(g for op, g in chain.gas_log if op in ("evidence", "issue", "resolve_review"))
            summary["configs"][c] = {
                "transactions": len(chain.gas_log), "minted_mwh": minted_wh / 1e6,
                "review_lots": int((log["kind"] == "resolve_review").sum()),
                "gas_total": int(sum(g for _, g in chain.gas_log)), "gas_issuance": int(issuance_gas),
                "gas_per_mwh_issuance": issuance_gas / (minted_wh / 1e6),
                "gas_per_mwh_all": sum(g for _, g in chain.gas_log) / (minted_wh / 1e6),
                "certificates": len(lin), "lineage_complete": float(lin["complete"].mean())}
            print(c, json.dumps(summary["configs"][c], ensure_ascii=False), f"({time.time() - t0:.0f} s)", flush=True)
    finally:
        node.close()

    # Độ trễ: block mỗi 2 giây.
    node = HardhatNode(port + 1, initial_date="2024-06-01T00:00:00Z", interval_ms=2000)
    try:
        chain = ChainRegistry(plant, node.url, interval_mining=True)
        chain.lat_log = []
        chain.arrival_jitter_s = 2.0  # mỗi giao dịch đến sau một khoảng ngẫu nhiên đều trong [0, 2) giây
        ev = truncate(events, test_days[0], lat_days)
        run_stream(chain, ev, sun, issuer_a, make_verdict(None, data, temps, slot_ends, chain, store))
        lat = pd.DataFrame(chain.lat_log, columns=["op", "seconds"])
    finally:
        node.close()

    gas = pd.DataFrame(gas_rows)
    gas.to_csv(out / "gas.csv", index=False)
    gs = gas.groupby(["config", "op"])["gas"].agg(["count", "median", "mean", "max"]).reset_index()
    gs.to_csv(out / "gas_summary.csv", index=False)
    lat.to_csv(out / "latency.csv", index=False)
    pd.concat(lin_frames).to_csv(out / "lineage.csv", index=False)
    latency = {"transactions": len(lat), "block_interval_s": 2,
                          "p50_s": float(np.quantile(lat["seconds"], 0.5)),
                          "p95_s": float(np.quantile(lat["seconds"], 0.95)),
                          "max_s": float(lat["seconds"].max()),
                          "by_op_p50": lat.groupby("op")["seconds"].median().round(3).to_dict()}
    # summary.json tất định (vào manifests/results.sha256); độ trễ đo theo đồng hồ thật nên ghi riêng.
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "latency_summary.json").write_text(json.dumps(latency, indent=2, ensure_ascii=False), encoding="utf-8")
    print(gs.to_string(index=False))
    print(json.dumps(latency, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
