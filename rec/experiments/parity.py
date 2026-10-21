"""Test parity (FLOW.md mục 11): một mẫu ca E2a chạy qua contract và qua `gate/sim.py` phải cho cùng quyết định.

Với mỗi ca và mỗi cấu hình (B1, B2, Proposed; biến thể prereg; trần 4%):
- phía chain: verifier tính cờ và ký verdict → issuer gửi bằng chứng của lô → `issue` từng yêu cầu. Lô REVIEW được
  auditor phân xử theo nhãn thật (duyệt nếu ca không khai khống), rồi issuer gửi lại;
- phía mô phỏng: `layer_a` và `decide` của E2 trên cùng chuỗi đã sửa.
So từng yêu cầu: kết cục (mint / reject + lý do / held) ở lần gửi đầu và sau phân xử, cùng lượng Wh được MINT.

Chạy: python -m rec.experiments.parity [--per-scenario 50] [--port 8551]
Ghi artifacts/results/parity/parity.csv và summary.json.
"""
from __future__ import annotations

import json
import sys
import time

import numpy as np
import pandas as pd

from rec import config
from rec.experiments.e2 import _lot_row
from rec.experiments.runner import plant_from_config
from rec.gate.sim import PROFILES, device_caps, layer_a
from rec.gate.verifier import Verifier
from rec.generator.cases_e2 import apply_case
from rec.generator.common import EVIDENCE_AT, INVERTER_MAX_W, REQUEST_AT, load_days, local_t, reports_for
from rec.metrics.e2 import decide
from rec.oracles.store import FileStore
from rec.registry.base import LotEvidence
from rec.schema import Device, IssueRequest

CONFIGS = ("B1", "B2", "Proposed")


def _arg(argv, name, default):
    return argv[argv.index(name) + 1] if name in argv else default


def sample_cases(cases: pd.DataFrame, per_scenario: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    parts = []
    for _, g in cases.groupby("scenario", sort=True):
        parts.append(g.iloc[np.sort(rng.choice(len(g), size=min(per_scenario, len(g)), replace=False))])
    return pd.concat(parts, ignore_index=True)


def expected(feat_row: dict, requests: list, check, prof, verifier: Verifier, day: int, fraud: bool
             ) -> tuple[bool, list, list]:
    """Cờ lớp B và kết cục từng yêu cầu theo mô phỏng off-chain: (cờ, lượt gửi đầu, sau khi auditor phân xử).

    `check(reqs)` là `layer_a` của E2. Lô không có cờ: một lượt, ngân sách cộng dồn theo thứ tự. Lô REVIEW: ở lượt
    đầu chưa yêu cầu nào được MINT nên ngân sách xét từng yêu cầu riêng; yêu cầu qua lớp A bị giữ. Auditor duyệt thì
    các yêu cầu bị giữ được gửi lại theo thứ tự (ngân sách cộng dồn); bác thì đều nhận `lot_rejected`.
    """
    feat = pd.DataFrame([{**feat_row, "minted_a_wh": 0, "a_reject": False}])
    base = np.array([verifier.base[day]]) if prof.ceiling else None
    flag = bool(decide(feat, prof, verifier.tau_cons, base, verifier.tau_ceiling, verifier.min_cov)["flag_b"].iloc[0])
    if not flag:
        return flag, [("reject", r) if r else ("mint", "") for r in check(requests)], [None] * len(requests)
    first = [check([r])[0] for r in requests]
    first_out = [("reject", r) if r else ("held", "") for r in first]
    held = [i for i, r in enumerate(first) if r is None]
    after: list = [None] * len(requests)
    if fraud:
        for i in held:
            after[i] = ("reject", "lot_rejected")
    else:
        for i, r in zip(held, check([requests[i] for i in held])):
            after[i] = ("reject", r) if r else ("mint", "")
    return flag, first_out, after


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from rec.registry.chain_registry import ChainRegistry, HardhatNode

    per = int(_arg(argv, "--per-scenario", "50"))
    port = int(_arg(argv, "--port", "8551"))
    scen = config.load("scenarios")
    plant_cfg = scen["plant"]
    devices = list(plant_cfg["devices"])
    caps = device_caps(plant_cfg["devices"], INVERTER_MAX_W)
    cp, cp_cap = plant_cfg["cp_id"], INVERTER_MAX_W * sum(len(v) for v in plant_cfg["devices"].values())
    artifacts = config.resolve_path("artifacts")
    _, data = load_days()
    slots = pd.read_parquet(artifacts / "slots.parquet")
    temps = {int(d): g["site_temp_c"].to_numpy(float) for d, g in slots.groupby("day", sort=True)}
    cases = sample_cases(pd.read_parquet(artifacts / "testset" / "e2" / "cases.parquet"), per)
    labels = pd.read_parquet(artifacts / "testset" / "e2" / "labels.parquet").set_index("case_id")
    verifiers = {c: Verifier(c) for c in CONFIGS}
    store = FileStore(artifacts / "store")
    out_dir = artifacts / "results" / "parity"
    out_dir.mkdir(parents=True, exist_ok=True)

    node = HardhatNode(port)
    rows = []
    try:
        chain = ChainRegistry(plant_from_config(plant_cfg), node.url)
        first = min(int(d) for d in cases["day"]) - 1
        for name, cap in caps.items():  # 6 thiết bị thật ở issuerA, thiết bị giả của D4b ở issuerB
            issuer = plant_cfg["issuers"][1] if name.startswith("X") else plant_cfg["issuers"][0]
            out = chain.register_device(Device(name, cp, cap, issuer, effective_day=first), 0)
            assert out.kind == "ok", (name, out)
        chain.checkpoint()
        t0 = time.time()
        for n, row in enumerate(cases.to_dict("records")):
            applied = apply_case(row, data, devices)
            dd = data[int(row["day"])]
            feat = _lot_row(applied.series, dd, temps[dd.day], verifiers["Proposed"].cons, verifiers["Proposed"].window)
            check = lambda reqs: layer_a(reqs, feat["o1_day"], feat["o1_max"], feat["sun_slots"], caps, cp_cap)
            fraud = int(labels.loc[row["case_id"], "excess_wh_true"]) > 0
            reports = reports_for(dd, cp, applied.series)
            for c in CONFIGS:
                v = verifiers[c].evaluate(dd.day, applied.series, dd.sun, temps[dd.day])
                sim_flag, sim_out, sim_after_all = expected(feat, applied.requests, check, PROFILES[c], verifiers[c],
                                                            dd.day, fraud)
                chain.reset()
                ev = LotEvidence(cp, dd.day, tuple(reports), v.flags, v.sun_slots, v.ceiling_wh, v.model_hash,
                                 store.put_json(v.reasons))
                ev_out = chain.submit_lot_evidence(ev, plant_cfg["issuers"][0], local_t(dd.day + 1, EVIDENCE_AT))
                t_req = local_t(dd.day + 1, REQUEST_AT)
                reqs = [IssueRequest(f"{row['case_id'][:20]}-{i}", iss, dev, dd.day, (wh,))
                        for i, (iss, dev, wh) in enumerate(applied.requests)]
                first_try = [chain.issue(r, t_req + i) for i, r in enumerate(reqs)]
                resolved = []
                if any(o.kind == "held" for o in first_try):
                    chain.resolve_review(cp, dd.day, not fraud, t_req + 3600)
                    resolved = [chain.issue(r, t_req + 7200 + i) if o.kind == "held" else None
                                for i, (r, o) in enumerate(zip(reqs, first_try))]
                for i, (o, (k, rsn)) in enumerate(zip(first_try, sim_out)):
                    after = resolved[i] if resolved and resolved[i] is not None else None
                    sim_after = sim_after_all[i]
                    rows.append({
                        "case_id": row["case_id"], "scenario": row["scenario"], "config": c, "request": i,
                        "evidence": ev_out.kind, "verifier_flags": v.flags, "sim_flag": sim_flag,
                        "chain": f"{o.kind}:{o.reason}", "sim": f"{k}:{rsn}",
                        "chain_after": "" if after is None else f"{after.kind}:{after.reason}",
                        "sim_after": "" if sim_after is None else f"{sim_after[0]}:{sim_after[1]}",
                        "chain_minted": o.minted_wh + (after.minted_wh if after else 0),
                        "sim_minted": applied.requests[i][2] if ((k == "mint") or (sim_after == ("mint", ""))) else 0})
            if (n + 1) % 50 == 0:
                print(f"{n + 1}/{len(cases)} ca  {time.time() - t0:.0f} s", flush=True)
    finally:
        node.close()

    df = pd.DataFrame(rows)
    df["match"] = ((df["chain"] == df["sim"]) & (df["chain_after"] == df["sim_after"])
                   & (df["chain_minted"] == df["sim_minted"]) & ((df["verifier_flags"] != 0) == df["sim_flag"]))
    df.to_csv(out_dir / "parity.csv", index=False)
    summary = {"cases": int(df["case_id"].nunique()), "lots": int(len(df.drop_duplicates(["case_id", "config"]))),
               "requests": int(len(df)), "mismatches": int((~df["match"]).sum()),
               "by_outcome": df.groupby("chain").size().to_dict(),
               "flagged_lots": int(df.drop_duplicates(["case_id", "config"])["sim_flag"].sum())}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["mismatches"]:
        print(df[~df["match"]].head(20).to_string())
    return 0 if summary["mismatches"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
