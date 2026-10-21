"""Dựng chain demo cho dashboard (FLOW.md mục 12): node Hardhat chạy nền, đã có dữ liệu cho mọi màn hình.

- 20 ngày đầu của dòng hợp lệ (seed 101), cấu hình Proposed, auditor duyệt lô REVIEW lúc 23:00 ngày d + 1;
- D1: nộp lại một (thiết bị, ngày) đã phát hành → IssueRejected(KEY);
- D4a: issuerB đăng ký thiết bị mới cùng CP, chép sản lượng → IssueRejected(BUDGET);
- sau 20 ngày: O1 khai tăng 45% (M2, k = 1) → lô nằm trong hàng đợi REVIEW, chưa phân xử (để thử nút duyệt / bác);
- Code Manager tạm khóa một chứng chỉ rồi rút một phần, kèm lý do;
- issuer thử gọi `withdraw` (insider) → revert, không ghi được gì.

Chạy: python -m rec.experiments.demo [--port 8545]   (node tiếp tục chạy; dừng bằng --stop)
Ghi artifacts/demo/deployment.json cho dashboard; chuỗi 15 phút ở artifacts/store/.
Sau đó: streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pandas as pd

from rec import config
from rec.experiments.e3 import make_verdict, truncate
from rec.experiments.runner import load_stream, plant_from_config, run_stream
from rec.gate.verifier import Verifier
from rec.generator.common import EVIDENCE_AT, REQUEST_AT, allocate, load_days, local_t, reports_for
from rec.oracles.signer import token_id
from rec.oracles.store import FileStore
from rec.registry.base import LotEvidence
from rec.schema import Device, EditAction, IssueRequest, OperatorEdit, OracleId

DEMO_DAYS = 20
GAIN = 1.45


def _arg(argv, name, default):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from rec.registry.chain_registry import ChainRegistry, HardhatNode

    artifacts = config.resolve_path("artifacts")
    dep_path = artifacts / "demo" / "deployment.json"
    if "--stop" in argv:
        if dep_path.exists():
            pid = json.loads(dep_path.read_text(encoding="utf-8"))["node_pid"]
            subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
            print("đã dừng node", pid)
        return 0

    port = int(_arg(argv, "--port", "8545"))
    scen = config.load("scenarios")
    pcfg = scen["plant"]
    plant = plant_from_config(pcfg)
    cp, (issuer_a, issuer_b) = pcfg["cp_id"], pcfg["issuers"]
    days_df, data = load_days()
    slots = pd.read_parquet(artifacts / "slots.parquet")
    temps = {int(d): g["site_temp_c"].to_numpy(float) for d, g in slots.groupby("day", sort=True)}
    slot_ends = {int(d): [t.isoformat() for t in g.index] for d, g in slots.groupby("day", sort=True)}
    sun = dict(zip(days_df["day"].astype(int), days_df["sun_slots"].astype(int)))
    test_days = sorted(int(d) for d in days_df.loc[days_df["split"] == "test", "day"])
    store = FileStore(artifacts / "store")
    verifier = Verifier("Proposed")

    node = HardhatNode(port)
    chain = ChainRegistry(plant, node.url)
    events = truncate(load_stream(artifacts / "testset" / "e1", "honest_s101"), test_days[0], DEMO_DAYS)
    log = pd.DataFrame(run_stream(chain, events, sun, issuer_a, make_verdict(verifier, data, temps, slot_ends, store),
                                  auditor=lambda c, d: True))
    print("dòng hợp lệ:", len(log), "thao tác; MINT", int((log["outcome"] == "mint").sum()), "yêu cầu")

    first = test_days[0]
    t_after = local_t(test_days[DEMO_DAYS - 1] + 2, REQUEST_AT)
    # D1: nộp lại một (thiết bị, ngày) đã phát hành.
    d1 = chain.issue(IssueRequest("demo-D1", issuer_a, "B1", first, (100_000,)), t_after)
    # D4a: issuerB đăng ký thiết bị mới cùng CP rồi chép sản lượng của B2.
    chain.register_device(Device("X-D4a", cp, 120_000, issuer_b, effective_day=first), t_after + 10)
    wh_b2 = int(log.loc[(log["kind"] == "request") & (log["device"] == "B2") & (log["day"] == first), "wh"].iloc[0])
    d4a = chain.issue(IssueRequest("demo-D4a", issuer_b, "X-D4a", first, (wh_b2,)), t_after + 20)
    print("D1:", d1.kind, d1.reason, "| D4a:", d4a.kind, d4a.reason)

    # Sau 20 ngày: O1 khai tăng 45% (M2, k = 1) → REVIEW, để trống cho auditor trên dashboard. Chọn ngày mà slot
    # lớn nhất sau khi tăng vẫn dưới công suất CP × 0,25 h, để lô không bị luật công suất REJECT trước.
    slot_cap = plant.cp_capacity_w[cp] / 4
    day = next(d for d in test_days[DEMO_DAYS:] if np.nanmax(data[d].series[OracleId.O1]) * GAIN < slot_cap)
    dd = data[day]
    series = {o: v.copy() for o, v in dd.series.items()}
    series[OracleId.O1] = series[OracleId.O1] * GAIN
    reports = reports_for(dd, cp, series)
    for o, r in zip(OracleId, reports):
        store.put(o, cp, day, series[o], slot_ends.get(day))
    v = verifier.evaluate(day, series, dd.sun, temps[day])
    ev = LotEvidence(cp, day, tuple(reports), v.flags, v.sun_slots, v.ceiling_wh, v.model_hash,
                     store.put_json(v.reasons))
    chain.submit_lot_evidence(ev, issuer_a, local_t(day + 1, EVIDENCE_AT))
    shares = allocate(reports[0].wh_day, {b: dd.block_wh.get(b, 0.0) for b in pcfg["devices"]})
    held = [chain.issue(IssueRequest(f"demo-M2-{b}", issuer_a, b, day, (wh,)), local_t(day + 1, REQUEST_AT) + i)
            for i, (b, wh) in enumerate(shares.items()) if wh > 0]
    print(f"ngày {day}: cờ {v.flags}, kết cục {[o.kind + ':' + o.reason for o in held]}")

    # Code Manager: tạm khóa rồi rút một phần một chứng chỉ chưa retire; insider thử withdraw.
    t_cm = local_t(day + 2, 12 * 3600)
    minted = log[(log["outcome"] == "mint")][["device", "day"]].itertuples(index=False)
    dev3, d3, bal = next((m.device, int(m.day), b) for m in minted
                         if (b := chain.certs.functions.balanceOf(chain.addr["plant"], token_id(m.device, int(m.day)))
                             .call()) > 0)
    chain.suspend(dev3, d3, True, "Nghi khai khống, đang điều tra (demo)", t_cm)
    wd = chain.withdraw(dev3, d3, "plant", max(1, bal // 10), "Rút 10% phát hành sai (demo)", t_cm + 60)
    ins = chain.operator_edit(OperatorEdit(issuer_a, "h-0-B1", EditAction.UPDATE), t_cm + 120)
    print("Code Manager rút:", wd.kind, "| insider:", ins.kind, ins.reason)

    dep = {"url": node.url, "node_pid": node.proc.pid, "store": str(artifacts / "store"),
           "contracts": {"DeviceRegistry": chain.devices.address, "CertificateRegistry": chain.certs.address,
                         "DecisionGate": chain.gate.address},
           "roles": chain.addr, "review_day": day, "profile": "Proposed", "variant": "prereg"}
    dep_path.parent.mkdir(parents=True, exist_ok=True)
    dep_path.write_text(json.dumps(dep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("đã ghi", dep_path, "| node vẫn chạy ở", node.url, "(PID", node.proc.pid, ")")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
