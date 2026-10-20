import json

import numpy as np
import pytest

from rec import config
from rec.generator import checks
from rec.generator.attacks_e1 import e1_overlay
from rec.generator.cases_e2 import apply_case, build_cases, labels_for
from rec.generator.common import DayData, allocate
from rec.generator.honest import honest_stream
from rec.generator.io import event_from_dict, event_to_dict
from rec.oracles.encoding import to_ints
from rec.schema import EventKind, OracleId

SCEN = config.load("scenarios")
PLANT = SCEN["plant"]
DEVICES = list(PLANT["devices"])
FIRST = 19_000


def _day(d: int, scale: float = 1.0, day_type: str = "clear", outage: bool = False) -> DayData:
    sun = np.zeros(96, dtype=bool)
    sun[24:72] = True
    o1 = np.where(sun, 100_000.0 * scale, 0.0)
    series = {OracleId.O1: o1, OracleId.O2: o1 / 0.984, OracleId.O3: np.where(sun, 200.0 * scale, 0.0),
              OracleId.O4: np.where(sun, 210.0 * scale, 0.0)}
    y = sum(to_ints(o1))  # giống load_days: cộng các slot đã làm tròn, khớp wh_day của báo cáo O1
    return DayData(d, series, sun, {b: y / 6 * (1 + 0.01 * i) for i, b in enumerate(DEVICES)}, y, day_type, outage)


@pytest.fixture
def world():
    days = list(range(FIRST, FIRST + 90))
    data = {d: _day(d, scale=1 + 0.3 * np.sin(d), day_type="cloudy" if d % 9 == 0 else "clear",
                    outage=d % 5 == 0) for d in days}
    return days, data


def test_allocate_never_exceeds_total():
    shares = allocate(1000, {"a": 1.0, "b": 1.0, "c": 1.0})
    assert sum(shares.values()) <= 1000 and shares["a"] == 333
    assert allocate(0, {"a": 1.0}) == {"a": 0}


def test_honest_stream_is_clean_and_has_l3(world):
    days, data = world
    hs = honest_stream(days, data, PLANT, 101, SCEN["honest_stream"])
    assert checks.check_clean_stream(hs.events) == []
    assert checks.check_time_order(hs.events) == []
    kinds = {e.kind for e in hs.events}
    assert EventKind.TRANSFER_REGISTRATION in kinds and EventKind.RETIRE in kinds
    assert any(lb.scenario == "L3" for lb in hs.labels)


def test_group_variant_is_one_device(world):
    days, data = world
    hs = honest_stream(days, data, PLANT, 101, SCEN["honest_stream"], variant="group")
    assert checks.check_clean_stream(hs.events) == []
    devices = {e.payload.device_id for e in hs.events if e.kind is EventKind.REQUEST}
    assert devices == {"G1"} and all(lb.scenario == "L4" for lb in hs.labels)


def test_e1_overlays(world):
    days, data = world
    hs = honest_stream(days, data, PLANT, 101, SCEN["honest_stream"])
    attacks = SCEN["attacks"]
    d1 = e1_overlay("D1", hs, days, data, PLANT, attacks["D1"]["params"], 10, 101)
    issued = {(it.device_id, it.day) for it in hs.issued}
    assert all((e.payload.device_id, e.payload.day_start) in issued for e in d1.events)
    assert checks.check_clean_stream(hs.events + d1.events)  # chèn D1 thì dòng không còn sạch
    d5 = e1_overlay("D5", hs, days, data, PLANT, attacks["D5"]["params"], 4, 101)
    assert d5.removed and all(r.startswith("h-") for r in d5.removed)
    d6 = e1_overlay("D6", hs, days, data, PLANT, attacks["D6"]["params"], 6, 101)
    assert {e.payload.ref for e in d6.events} == {lb.req_id for lb in d6.labels}


def test_e2_cases_transform_only_controlled_sources(world):
    days, data = world
    cases = build_cases(days[-30:], data, SCEN["attacks"], [101])
    rows = {r["case_id"]: r for r in cases.to_dict("records")}
    d = days[-1]
    m2_k1 = rows[f"s101-M2-1-0.3-{d}"]
    a = apply_case(m2_k1, data, DEVICES)
    assert np.allclose(a.series[OracleId.O1], data[d].series[OracleId.O1] * 1.3)
    assert np.allclose(a.series[OracleId.O2], data[d].series[OracleId.O2])
    m2_k3 = apply_case(rows[f"s101-M2-3-0.3-{d}"], data, DEVICES)
    assert np.allclose(m2_k3.series[OracleId.O3], data[d].series[OracleId.O3] * 1.3)
    assert np.allclose(m2_k3.series[OracleId.O4], data[d].series[OracleId.O4])  # O4 không bao giờ bị sửa
    assert a.excess_wh == pytest.approx(0.3 * data[d].y_wh, rel=1e-3)


def test_d4b_adds_issuer_b_request(world):
    days, data = world
    cases = build_cases(days[-5:], data, SCEN["attacks"], [101])
    row = cases[(cases["scenario"] == "D4b")].iloc[0].to_dict()
    a = apply_case(row, data, DEVICES)
    f = json.loads(row["params"])["f"]
    assert a.requests[-1][0] == "issuerB"
    assert sum(wh for _, _, wh in a.requests) == pytest.approx(data[row["day"]].y_wh * (1 + f), rel=0.02)


def test_clock_shift_and_determinism(world):
    days, data = world
    cases = build_cases(days[-5:], data, SCEN["attacks"], [101])
    shift = cases[cases["params"].str.contains("clock_shift")].iloc[0].to_dict()
    a = apply_case(shift, data, DEVICES)
    o = OracleId[json.loads(shift["params"])["oracle"]]
    assert np.isnan(a.series[o][0])
    m1 = cases[cases["scenario"] == "M1"].iloc[0].to_dict()
    x, y = apply_case(m1, data, DEVICES), apply_case(m1, data, DEVICES)
    assert all(np.array_equal(x.series[k], y.series[k], equal_nan=True) for k in x.series)


def test_labels_and_case_checks(world):
    days, data = world
    cases = build_cases(days[-20:], data, SCEN["attacks"], [101])
    labels = labels_for(cases, data, DEVICES)
    assert (labels.loc[labels["kind"].isin(["honest", "L"]), "excess_wh_true"] == 0).all()
    assert (labels.loc[labels["scenario"] == "M2", "excess_wh_true"] > 0).all()
    assert checks.check_cases(cases, labels, data, DEVICES, sample=300) == []


def test_event_json_round_trip(world):
    days, data = world
    hs = honest_stream(days[:3], data, PLANT, 101, SCEN["honest_stream"])
    for e in hs.events:
        assert event_from_dict(event_to_dict(e)) == e
