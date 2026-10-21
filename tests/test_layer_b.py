import numpy as np
import pandas as pd
import pytest

from rec.checks.consistency import ConsistencyModel, coverage, stats
from rec.gate.sim import PROFILES, device_caps, layer_a
from rec.metrics.e2 import decide, lmax, lmax_scale
from rec.model.calibrate import ceiling_tau, consistency_thresholds
from rec.schema import OracleId

CAP_SLOT = 720_000 * 0.25


def _series(o1_scale=1.0):
    sun = np.zeros(96, dtype=bool)
    sun[24:72] = True
    o2 = np.where(sun, 100_000.0, 0.0)
    o1 = o2 * 0.98 * o1_scale
    o3 = np.where(sun, 150.0, 0.0)
    return {OracleId.O1: o1, OracleId.O2: o2, OracleId.O3: o3, OracleId.O4: o3.copy()}, sun


def test_consistency_is_one_sided():
    m = ConsistencyModel(eta=0.98, beta=100_000 * 0.98 / 150, gamma=0.0, cap_slot_wh=CAP_SLOT)
    s, sun = _series()
    t = np.full(96, 25.0)
    honest = stats(s, sun, t, m)
    assert honest["r12_day"] == pytest.approx(0.0) and honest["r13_day"] == pytest.approx(0.0)
    high = stats(_series(1.3)[0], sun, t, m)
    low = stats(_series(0.7)[0], sun, t, m)
    assert high["r12_day"] == pytest.approx(0.3) and low["r12_day"] < 0  # thấp hơn → âm, không vượt ngưỡng dương


def test_coverage_counts_daytime_slots_only():
    s, sun = _series()
    s[OracleId.O2][30:33] = np.nan
    s[OracleId.O2][0] = np.nan  # ban đêm, không tính
    assert coverage(s, sun)["O2"] == pytest.approx(45 / 48)


def test_consistency_thresholds_hit_target():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(1000, 4)), columns=["r12_day", "r12_slot", "r13_day", "r13_slot"])
    tau, q, rate = consistency_thresholds(df, 0.01)
    assert rate <= 0.01 and q < 1.0


def test_ceiling_tau_counts_at_most_target():
    y = np.arange(1, 101, dtype=float)
    base = np.full(100, 50.0)
    tau, rate = ceiling_tau(y, base, 0.04)
    assert rate <= 0.04 and np.sum(y > base * (1 + tau)) == 4


def test_layer_a_capacity_and_budget():
    caps = device_caps({"B1": [1, 2, 3, 4], "B2": [5, 6, 7, 8]}, 30_000)
    assert caps["XD4b-1"] == 120_000
    reasons = layer_a([("A", "B1", 500), ("A", "B2", 600)], o1_day=1000, o1_max_slot=100, sun_slots=48,
                      device_cap_w=caps, cp_cap_w=240_000)
    assert reasons == [None, "budget"]
    over = layer_a([("A", "B1", 10)], o1_day=10, o1_max_slot=70_000, sun_slots=48, device_cap_w=caps,
                   cp_cap_w=240_000)
    assert over == ["capacity"]  # slot O1 vượt công suất CP × 0,25 h
    both = layer_a([("A", "B1", 2_000_000)], o1_day=1000, o1_max_slot=100, sun_slots=48, device_cap_w=caps,
                   cp_cap_w=240_000)
    assert both == ["budget"]  # vi phạm cả hai: ngân sách xét trước, như contract


def _day_table(r12=0.0, y=1e6):
    return pd.DataFrame({"y_wh": [y], "sun_slots": [48], "o1_max": [y / 48], "cov_min": [1.0], "r12_day": [r12],
                         "r12_slot": [r12], "r13_day": [0.0], "r13_slot": [0.0]})


def test_lmax_scale_k1_bounded_by_unmodified_o2():
    tau = {"r12_day": 0.05, "r12_slot": 0.05, "r13_day": 0.2, "r13_slot": 0.2}
    s1 = lmax_scale(_day_table(), 1, tau, PROFILES["B2"], np.array([10e6]), 0.5, 0.95, 720_000)
    s3 = lmax_scale(_day_table(), 3, tau, PROFILES["B2"], np.array([1.2e6]), 0.0, 0.95, 720_000)
    assert s1[0] == pytest.approx(1.05)       # k = 1: O2 chưa bị sửa giới hạn ở 5%
    assert s3[0] == pytest.approx(1.2)        # k = 3: chỉ còn trần
    blocked = lmax_scale(_day_table(r12=0.1), 3, tau, PROFILES["B2"], np.array([2e6]), 0.0, 0.95, 720_000)
    assert blocked[0] == 0.0                  # lô trung thực đã lệch quá ngưỡng thì kẻ gian không mint được
    assert lmax(np.array([1e6]), s3) == pytest.approx(0.2)


def test_decide_b1_never_reviews():
    feat = _day_table().assign(o1_day=[1e6], minted_a_wh=[1e6], a_reject=[False])
    tau = {"r12_day": -1, "r12_slot": -1, "r13_day": -1, "r13_slot": -1}
    assert not decide(feat, PROFILES["B1"], tau, None, None, 0.95)["flag_b"].iloc[0]
    assert decide(feat, PROFILES["B2"], tau, np.array([1e6]), 0.1, 0.95)["flag_b"].iloc[0]


def test_slot_window_variants():
    m = ConsistencyModel(eta=0.98, beta=100_000 * 0.98 / 150, gamma=0.0, cap_slot_wh=CAP_SLOT)
    s, sun = _series()
    s[OracleId.O1][40] *= 3.0  # một slot tăng gấp 3
    t = np.full(96, 25.0)
    per_slot = stats(s, sun, t, m, window=1)
    assert per_slot["r12_slot"] == pytest.approx(2.0)          # đúng cách tính spec-v1
    assert stats(s, sun, t, m, window=4)["r12_slot"] == pytest.approx(0.5)  # (3 + 1 + 1 + 1) / 4 − 1
    day_only = stats(s, sun, t, m, window=None)
    assert np.isnan(day_only["r12_slot"]) and np.isnan(day_only["r13_slot"])
    assert day_only["r12_day"] == pytest.approx(per_slot["r12_day"])


def test_slot_window_skips_incomplete_windows():
    m = ConsistencyModel(eta=0.98, beta=100_000 * 0.98 / 150, gamma=0.0, cap_slot_wh=CAP_SLOT)
    s, sun = _series()
    s[OracleId.O1][40] *= 3.0
    s[OracleId.O2][41] = np.nan  # các cửa sổ 38–41, 39–42, 40–43 bị loại vì thiếu slot 41
    t = np.full(96, 25.0)
    r = stats(s, sun, t, m, window=4)["r12_slot"]
    assert r == pytest.approx(0.5)  # chỉ còn cửa sổ 37–40 đủ số liệu
