import os

import numpy as np
import pandas as pd
import pytest

from rec import config
from rec.oracles.encoding import data_root
from rec.oracles.store import FileStore
from rec.schema import OracleId

ARTIFACTS = config.resolve_path("artifacts")
HAS_MODEL = (ARTIFACTS / "model" / "prereg" / "layer_b.json").exists() and (ARTIFACTS / "days.parquet").exists()


def test_store_roundtrip_and_tamper(tmp_path):
    store = FileStore(tmp_path)
    values = np.array([0.0, 12.4, np.nan, 99.6])
    root = store.put(OracleId.O1, "CP-1", 19000, values)
    assert root == data_root(values)
    assert store.get(root)["values"] == [0, 12, None, 100]
    path = store.path(root)
    path.write_text(path.read_text(encoding="utf-8").replace("100", "101"), encoding="utf-8")
    assert not store.verify(root)
    assert not store.verify(b"\x01" * 32)


@pytest.mark.skipif(not HAS_MODEL, reason="cần artifacts/model/prereg (chạy rec.experiments.e2)")
@pytest.mark.parametrize("profile", ["B2", "Proposed"])
def test_verifier_flags_match_offline_decision(profile):
    """Verifier (từng lô, tham số đọc từ file đã khóa) cho cùng cờ với `decide` của E2 (vector hóa)."""
    from rec.experiments.e2 import _lot_row
    from rec.gate.sim import PROFILES
    from rec.gate.verifier import Verifier
    from rec.generator.cases_e2 import apply_case
    from rec.generator.common import load_days
    from rec.metrics.e2 import decide

    _, data = load_days()
    slots = pd.read_parquet(ARTIFACTS / "slots.parquet")
    temps = {int(d): g["site_temp_c"].to_numpy(float) for d, g in slots.groupby("day", sort=True)}
    cases = pd.read_parquet(ARTIFACTS / "testset" / "e2" / "cases.parquet").sample(120, random_state=1)
    devices = list(config.load("scenarios")["plant"]["devices"])
    v = Verifier(profile)
    rows, flags = [], []
    for row in cases.to_dict("records"):
        applied = apply_case(row, data, devices)
        dd = data[int(row["day"])]
        rows.append(_lot_row(applied.series, dd, temps[dd.day], v.cons, v.window))
        flags.append(v.evaluate(dd.day, applied.series, dd.sun, temps[dd.day]).flags != 0)
    feat = pd.DataFrame(rows).assign(minted_a_wh=0, a_reject=False)
    base = np.array([v.base[int(d)] for d in cases["day"]])
    sim = decide(feat, PROFILES[profile], v.tau_cons, base, v.tau_ceiling, v.min_cov)["flag_b"].to_numpy()
    assert (np.array(flags) == sim).all()
    assert 0 < sim.sum() < len(sim)  # mẫu có cả lô bị cờ và lô sạch


@pytest.mark.skipif(os.environ.get("REC_CHAIN_TESTS") != "1", reason="đặt REC_CHAIN_TESTS=1 để chạy test cần Hardhat")
def test_parity_small_sample():
    from rec.experiments.parity import main
    assert main(["--per-scenario", "2", "--port", "8570"]) == 0
