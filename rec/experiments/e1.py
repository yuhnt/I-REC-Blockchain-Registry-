"""E1 (RQ1, chế độ R1): cùng một dòng sự kiện qua b0_separate, b0_shared và chain (SPEC mục 4.1, 7).

Chạy: python -m rec.experiments.e1 [--backends b0_separate,b0_shared,chain] [--seeds 101,102] [--streams D1,D3]
           [--run-only --port 8546]   chỉ chạy và ghi nhật ký (để chạy song song mỗi seed một node Hardhat)
           [--metrics-only]           chỉ tính chỉ số từ nhật ký đã ghi
Ghi vào artifacts/results/e1/:
  decisions/<backend>/<dòng>.csv   nhật ký quyết định
  cases.csv                        mỗi ca tấn công: kết cục, điểm chặn, Wh lọt, exposure window
  summary.csv                      theo backend × kịch bản: tỉ lệ lọt, DCR, exposure, insider
  false_reject.csv                 REJECT nhầm trên yêu cầu hợp lệ (L1, L3, L4)
  gas.csv                          gas theo thao tác (chỉ chain)
Nhãn chỉ được đọc ở bước tính chỉ số, sau khi mọi dòng đã chạy xong.
"""
from __future__ import annotations

import math
import sys
import time

import pandas as pd

from rec import config
from rec.experiments.runner import load_stream, plant_from_config, run_stream
from rec.registry.base import DAY_S
from rec.registry.sqlite_registry import SeparateRegistry, SqliteRegistry

T_REC = (7, 30)
LIFECYCLE = {"D6", "insider"}


def _arg(argv: list[str], name: str, default: list[str]) -> list[str]:
    return argv[argv.index(name) + 1].split(",") if name in argv else default


def streams_for(attacks: list[str], seeds: list[int]) -> list[tuple[str, str, str | None]]:
    """(tên dòng, dòng hợp lệ nền, dòng tấn công) cho mọi seed."""
    out = []
    for s in seeds:
        out.append((f"honest_s{s}", f"honest_s{s}", None))
        out.append((f"honest_group_s{s}", f"honest_group_s{s}", None))
        out += [(f"{a}_s{s}", f"honest_s{s}", f"{a}_s{s}") for a in attacks]
    return out


def run(backends: list[str], streams: list[tuple[str, str, str | None]], port: int = 8545
        ) -> dict[str, dict[str, pd.DataFrame]]:
    scen = config.load("scenarios")
    plant = plant_from_config(scen["plant"])
    artifacts = config.resolve_path("artifacts")
    e1_dir = artifacts / "testset" / "e1"
    days = pd.read_parquet(artifacts / "days.parquet")
    sun = dict(zip(days["day"].astype(int), days["sun_slots"].astype(int)))
    out_dir = artifacts / "results" / "e1" / "decisions"
    issuer_a = scen["plant"]["issuers"][0]
    logs: dict[str, dict[str, pd.DataFrame]] = {}
    chain = node = None
    if "chain" in backends:
        from rec.registry.chain_registry import ChainRegistry, HardhatNode
        node = HardhatNode(port)
        chain = ChainRegistry(plant, node.url)
    gas_rows = []
    try:
        for backend_name in backends:
            (out_dir / backend_name).mkdir(parents=True, exist_ok=True)
            logs[backend_name] = {}
            for name, base, overlay in streams:
                t0 = time.time()
                if backend_name == "chain":
                    chain.reset()
                    chain.gas_log = []
                    backend = chain
                else:
                    backend = (SeparateRegistry if backend_name == "b0_separate" else SqliteRegistry)(plant)
                events = load_stream(e1_dir, base, overlay)
                log = pd.DataFrame(run_stream(backend, events, sun, issuer_a))
                if backend_name == "b0_separate":
                    found = pd.DataFrame(backend.reconcile(events[-1].t))
                    log["detected_rule"] = log["id"].map(dict(zip(found.get("req_id", []), found.get("rule", []))))
                else:
                    log["detected_rule"] = None
                log["stream_t0"], log["stream_t1"] = events[0].t, events[-1].t
                if backend_name == "chain":
                    gas_rows += [{"stream": name, "op": op, "gas": g} for op, g in chain.gas_log]
                log.to_csv(out_dir / backend_name / f"{name}.csv", index=False)
                logs[backend_name][name] = log
                print(f"{backend_name:12s} {name:18s} {len(log):6d} thao tác  {time.time() - t0:6.1f} s", flush=True)
    finally:
        if node is not None:
            node.close()
    if gas_rows:
        tag = "_".join(sorted({n.rsplit("_s", 1)[1] for n, _, _ in streams}))
        pd.DataFrame(gas_rows).to_csv(artifacts / "results" / "e1" / f"gas_s{tag}.csv", index=False)
    return logs


def _exposure_days(t_mint: int, t0: int, t1: int, detected: bool, t_rec: int) -> tuple[float, bool]:
    """Số ngày từ lúc MINT bản trùng tới lần đối soát kế tiếp; bị cắt ở cuối dòng nếu không phát hiện."""
    if not detected:
        return (t1 - t_mint) / DAY_S, True
    period = t_rec * DAY_S
    t_det = t0 + math.ceil((t_mint - t0) / period) * period
    if t_det > t1:
        return (t1 - t_mint) / DAY_S, True
    return (t_det - t_mint) / DAY_S, False


def _per_day(col: pd.Series) -> dict[int, int]:
    out: dict[int, int] = {}
    for cell in col.dropna():
        for part in str(cell).split(";"):
            if part:
                d, w = part.split(":")
                out[int(d)] = out.get(int(d), 0) + int(w)
    return out


def _lifecycle_cases(backend, scenario, seed, att, by_id, minted_total) -> list[dict]:
    rows = []
    for lb in att.itertuples():
        r = by_id.loc[lb.id] if lb.id in by_id.index else None
        success = r is not None and r["outcome"] == "ok"
        rows.append({"backend": backend, "scenario": scenario, "seed": seed, "case": lb.id, "success": success,
                     "trace": bool(r["trace"]) if r is not None else True,
                     "blocked_at": "not_blocked" if success else ("lifecycle" if scenario == "D6"
                                                                  else "no_admin_function"),
                     "reason": "" if r is None else str(r["reason"]), "excess_submitted": int(lb.excess_wh_true),
                     "excess_leaked": int(lb.excess_wh_true) if success else 0, "minted_total_stream": minted_total,
                     **{f"exposure_d_T{tr}": 0.0 for tr in T_REC}, **{f"censored_T{tr}": False for tr in T_REC}})
    return rows


def _lot_cases(backend, scenario, seed, att, log, minted_total, t0, t1) -> list[dict]:
    """Mỗi lô bị tấn công một ca; phần vượt = max(0, Σ MINT tại (CP, ngày) − y), y = O1 ở chế độ R1."""
    reqs = log[log["kind"] == "request"]
    ev = log[log["kind"] == "evidence"]
    o1 = dict(zip(ev["day"].astype(int), ev["wh"].astype(int)))
    req_all, mint_all = _per_day(reqs["req_days"]), _per_day(reqs["minted_days"])
    att_reqs = reqs[reqs["id"].isin(set(att["id"]))]
    rows = []
    for case, g in att_reqs.groupby("day" if scenario == "D5" else "id"):  # D5 thay cả 6 yêu cầu của một lô
        days_hit = sorted(_per_day(g["req_days"]))
        y = {d: o1.get(d, 0) for d in days_hit}
        submitted = sum(max(0, req_all.get(d, 0) - y[d]) for d in days_hit)
        leaked = sum(max(0, mint_all.get(d, 0) - y[d]) for d in days_hit)
        minted_att = g[g["outcome"] == "mint"]
        reg_blocked = False
        if scenario == "D3":
            regs = log[(log["kind"] == "register") & log["device"].isin(g["device"]) & log["issuer"].isin(g["issuer"])]
            reg_blocked = len(regs) > 0 and bool((regs["outcome"] == "revert").all())
        if leaked > 0:
            blocked_at = "not_blocked"
        elif reg_blocked:
            blocked_at = "registration"
        else:
            rejected = g[g["outcome"] != "mint"]
            blocked_at = "issuance:" + (str(rejected["reason"].mode().iloc[0]) if len(rejected) else "budget")
        rec = {"backend": backend, "scenario": scenario, "seed": seed, "case": str(case), "success": leaked > 0,
               "trace": True, "blocked_at": blocked_at,
               "reason": ",".join(sorted(set(g["reason"].dropna().astype(str)) - {""})),
               "excess_submitted": submitted, "excess_leaked": leaked, "minted_total_stream": minted_total}
        detected = bool(minted_att["detected_rule"].apply(lambda v: isinstance(v, str)).any()) if len(minted_att) \
            else False
        for tr in T_REC:
            days, cens = (_exposure_days(int(minted_att["t"].min()), t0, t1, detected, tr) if leaked > 0
                          else (0.0, False))
            rec[f"exposure_d_T{tr}"], rec[f"censored_T{tr}"] = days, cens
        rows.append(rec)
    return rows


def metrics(logs: dict[str, dict[str, pd.DataFrame]]) -> dict[str, pd.DataFrame]:
    """Chỉ số E1 theo SPEC mục 7.

    D1–D5: mỗi lô bị tấn công là một ca; phần vượt tính theo lô (SPEC mục 4.2). D6, insider: mỗi thao tác vòng đời
    là một ca; thành công nghĩa là Wh bị dùng hơn một lần (retire lại, chuyển sau retire, sửa hay phát hành lại).
    """
    labels = pd.read_parquet(config.resolve_path("artifacts") / "testset" / "e1" / "labels.parquet")
    case_rows, fr_rows = [], []
    for backend, streams in logs.items():
        for name, log in streams.items():
            scenario, seed = name.rsplit("_s", 1)
            log = log.assign(id=log["id"].astype(str))
            by_id = log.drop_duplicates("id", keep="first").set_index("id")
            minted_total = int(log["minted_wh"].sum())
            t0, t1 = int(log["stream_t0"].iloc[0]), int(log["stream_t1"].iloc[0])

            # REJECT nhầm trên yêu cầu hợp lệ của dòng (L1 = các khối hợp lệ cùng CP, L3, L4).
            base = "honest_group_s" + seed if scenario == "honest_group" else "honest_s" + seed
            ok_labels = labels[(labels["stream"] == base) & labels["id"].isin(by_id.index)]
            for lab, g in ok_labels.groupby("scenario"):
                res = by_id.loc[g["id"], "outcome"]
                fr_rows.append({"backend": backend, "stream": name, "scenario": scenario,
                                "label": "L1" if lab == "honest" else lab, "requests": len(g),
                                "not_minted": int((res != "mint").sum())})
            if scenario in ("honest", "honest_group"):
                continue
            att = labels[labels["stream"] == name]
            if scenario in LIFECYCLE:
                case_rows += _lifecycle_cases(backend, scenario, int(seed), att, by_id, minted_total)
            else:
                case_rows += _lot_cases(backend, scenario, int(seed), att, log, minted_total, t0, t1)

    cases = pd.DataFrame(case_rows)
    sum_rows = []
    for (backend, scenario), g in cases.groupby(["backend", "scenario"]):
        streams_minted = g.drop_duplicates("seed")["minted_total_stream"].sum()
        leaked = g["excess_leaked"].sum()
        row = {"backend": backend, "scenario": scenario, "cases": len(g), "succeeded": int(g["success"].sum()),
               "leak_rate": leaked / max(g["excess_submitted"].sum(), 1), "dcr": leaked / max(streams_minted, 1),
               "attack_share": g["excess_submitted"].sum() / max(streams_minted, 1),
               "blocked_at": "; ".join(f"{k} ({v})" for k, v in g["blocked_at"].value_counts().items())}
        if scenario == "insider":
            row["insider"] = "fail" if bool((g["success"] & ~g["trace"]).any()) else "pass"
        lk = g[g["success"]]
        for tr in T_REC:
            col = f"exposure_d_T{tr}"
            row[f"exposure_median_T{tr}"] = float(lk[col].median()) if len(lk) else 0.0
            row[f"exposure_max_T{tr}"] = float(lk[col].max()) if len(lk) else 0.0
            row[f"censored_T{tr}"] = int(lk[f"censored_T{tr}"].sum()) if len(lk) else 0
        sum_rows.append(row)
    fr = pd.DataFrame(fr_rows).groupby(["backend", "label", "scenario"], as_index=False)[["requests", "not_minted"]].sum()
    fr["false_reject_rate"] = fr["not_minted"] / fr["requests"]
    return {"cases": cases, "summary": pd.DataFrame(sum_rows), "false_reject": fr}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    scen = config.load("scenarios")
    exp = scen["experiments"]["E1"]
    backends = _arg(argv, "--backends", list(exp["backends"]))
    seeds = [int(s) for s in _arg(argv, "--seeds", [str(s) for s in scen["seeds"]["test"]])]
    attacks = _arg(argv, "--streams", list(exp["attacks"]))
    streams = streams_for(attacks, seeds)
    if "--metrics-only" in argv:  # đọc nhật ký đã chạy (ví dụ chạy song song từng seed bằng --run-only)
        dec = config.resolve_path("artifacts") / "results" / "e1" / "decisions"
        logs = {b: {n: pd.read_csv(dec / b / f"{n}.csv", keep_default_na=False, na_values=[""])
                    for n, _, _ in streams} for b in backends}
    else:
        port = int(_arg(argv, "--port", ["8545"])[0])
        logs = run(backends, streams, port)
        if "--run-only" in argv:
            return 0
    res = metrics(logs)
    out = config.resolve_path("artifacts") / "results" / "e1"
    for k, df in res.items():
        df.to_csv(out / f"{k}.csv", index=False)
    pd.set_option("display.width", 200)
    print(res["summary"][["backend", "scenario", "cases", "succeeded", "leak_rate", "dcr", "exposure_median_T7",
                          "exposure_median_T30", "blocked_at"]].to_string(index=False))
    print(res["false_reject"].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
