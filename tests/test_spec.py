import copy

import pytest

from rec import config
from rec.config import SpecError


def test_spec_files_are_consistent():
    config.check_all()


def test_paths_resolve_to_dataset():
    assert config.resolve_path("dataset").name == "dataset"


def test_split_rejects_overlapping_years():
    s = copy.deepcopy(config.load("split"))
    s["splits"]["val"].append(2020)
    with pytest.raises(SpecError):
        config.check_split(s)


def test_scenarios_require_alpha_for_every_f():
    s = copy.deepcopy(config.load("scenarios"))
    s["attacks"]["M2"]["params"]["alpha"] = [0.1, 0.3]
    with pytest.raises(SpecError, match="H2b"):
        config.check_scenarios(s)


def test_scenarios_reject_r2_only_attack_in_e1():
    s = copy.deepcopy(config.load("scenarios"))
    s["experiments"]["E1"]["attacks"].append("M2")
    with pytest.raises(SpecError):
        config.check_scenarios(s)


@pytest.mark.parametrize("column", ["meter_wh_day", "inv01", "poa_site_whm2", "O2_ratio"])
def test_feature_leakage_is_blocked(column):
    with pytest.raises(SpecError):
        config.assert_feature_columns(["clearsky_index", column])


def test_features_reject_on_site_source():
    f = copy.deepcopy(config.load("features"))
    f["features"]["site_poa"] = {"source": "O3", "desc": "POA tại chỗ"}
    with pytest.raises(SpecError):
        config.check_features(f)


def test_thresholds_give_ceiling_the_larger_share():
    t = copy.deepcopy(config.load("thresholds"))
    t["consistency_a"]["false_review"] = 0.04
    with pytest.raises(SpecError):
        config.check_thresholds(t)


def test_thresholds_require_one_sided_consistency():
    t = copy.deepcopy(config.load("thresholds"))
    t["consistency_a"]["one_sided"] = False
    with pytest.raises(SpecError, match="một phía"):
        config.check_thresholds(t)


def test_sweep_must_contain_main_point():
    t = copy.deepcopy(config.load("thresholds"))
    t["ceiling"]["false_review_sweep"] = [0.01, 0.02, 0.05]
    with pytest.raises(SpecError):
        config.check_thresholds(t)


def test_negatives_measured_in_matching_layer():
    s = copy.deepcopy(config.load("scenarios"))
    s["experiments"]["E2a"]["negatives"].append("L3")
    with pytest.raises(SpecError):
        config.check_scenarios(s)
