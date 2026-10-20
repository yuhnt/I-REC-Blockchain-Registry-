import pytest

from rec.schema import (
    Decision,
    DecisionKind,
    Deregistration,
    Device,
    Event,
    EventKind,
    Flag,
    IssueRequest,
    Label,
    LabelKind,
    OracleId,
    OracleReport,
    RegistrationTransfer,
    RejectReason,
    Retire,
    Suspension,
    Transfer,
    Verdict,
    Withdrawal,
    lot_key,
    token_key,
)


def test_issue_request_days_and_total():
    req = IssueRequest("r1", "issuerA", "dev1", 19174, (1000, 2000, 3000))
    assert list(req.days) == [19174, 19175, 19176]
    assert req.total_wh == 6000


@pytest.mark.parametrize("wh_per_day", [(), (-1,), (1.5,), (True,), [100]])
def test_issue_request_rejects_bad_energy(wh_per_day):
    with pytest.raises(ValueError):
        IssueRequest("r1", "issuerA", "dev1", 19174, wh_per_day)


def test_device_requires_positive_capacity():
    with pytest.raises(ValueError):
        Device("dev1", "CP-1", 0, "issuerA")


def test_oracle_report_validation():
    OracleReport(OracleId.O1, "CP-1", 19174, 5_000_000, 200_000, slots_present=56)
    with pytest.raises(ValueError):
        OracleReport(OracleId.O1, "CP-1", 19174, 1000, 2000, slots_present=56)  # slot lớn hơn cả ngày
    with pytest.raises(ValueError):
        OracleReport(OracleId.O1, "CP-1", 19174, 1000, 100, slots_present=-1)
    with pytest.raises(ValueError):
        OracleReport(OracleId.O1, "CP-1", 19174, 1000, 100, slots_present=56, data_root=b"\x00" * 31)


def test_decision_constructors():
    assert Decision.reject(RejectReason.PERIOD).kind is DecisionKind.REJECT
    assert Decision.reject(RejectReason.LOT_REJECTED).reason.value == "lot_rejected"
    assert Decision.review(Flag.OVER_CEILING | Flag.INCONSISTENT).flags == 5
    assert Decision.mint(1_670_000).wh == 1_670_000


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": DecisionKind.REJECT},
        {"kind": DecisionKind.REVIEW},
        {"kind": DecisionKind.MINT, "wh": 0},
        {"kind": DecisionKind.MINT, "wh": 10, "flags": Flag.INCONSISTENT},
    ],
)
def test_decision_rejects_inconsistent_fields(kwargs):
    with pytest.raises(ValueError):
        Decision(**kwargs)


def test_verdict_needs_review():
    key = lot_key("CP-1", 19174)
    assert not Verdict(key, Flag.NONE, 6_000_000, "abc").needs_review
    assert Verdict(key, Flag.MISSING_REPORT, None, "abc").needs_review


def test_token_and_lot_keys_differ():
    assert token_key("B1", 19174) == "B1:19174"
    assert lot_key("CP-1", 19174) == "CP-1:19174"


def test_event_payload_must_match_kind():
    t = Transfer("dev1", 19174, "plantA", "buyerB", 200_000)
    Event(0, EventKind.TRANSFER, t)
    Event(0, EventKind.DEREGISTER, Deregistration("dev1", "issuerA", 19200))
    with pytest.raises(ValueError):
        Event(0, EventKind.RETIRE, t)


def test_registration_transfer_needs_new_issuer():
    Event(0, EventKind.TRANSFER_REGISTRATION, RegistrationTransfer("dev1", "issuerA", "issuerB", 19200))
    with pytest.raises(ValueError):
        RegistrationTransfer("dev1", "issuerA", "issuerA", 19200)


def test_retire_records_redemption_details():
    Retire("dev1", 19174, "buyerB", 200_000, "Cong ty B", "ESG 2026", "TP.HCM", "2026")
    with pytest.raises(ValueError):
        Retire("dev1", 19174, "buyerB", 200_000, "Cong ty B", "", "TP.HCM", "2026")


def test_code_manager_actions_need_reason():
    Event(0, EventKind.SUSPEND, Suspension("dev1", 19174, True, "nghi khai khống, chờ điều tra"))
    Event(0, EventKind.WITHDRAW, Withdrawal("dev1", 19174, "buyerB", 100_000, "kiểm tra ngẫu nhiên phát hiện gian lận"))
    with pytest.raises(ValueError):
        Suspension("dev1", 19174, True, "")
    with pytest.raises(ValueError):
        Withdrawal("dev1", 19174, "buyerB", 0, "lý do")


def test_label_honest_has_no_excess():
    Label("r1", "M2", LabelKind.M, excess_wh_true=500_000)
    with pytest.raises(ValueError):
        Label("r2", "honest", LabelKind.HONEST, excess_wh_true=1)
