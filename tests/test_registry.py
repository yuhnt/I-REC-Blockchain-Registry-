import pytest

from rec.experiments.e1 import _exposure_days
from rec.generator.common import REQUEST_AT, local_t
from rec.registry.base import LotEvidence, Plant
from rec.registry.sqlite_registry import SeparateRegistry, SqliteRegistry
from rec.schema import (Device, EditAction, IssueRequest, OperatorEdit, OracleId, OracleReport, RegistrationTransfer,
                        Retire, Transfer)

CP = "CP-1"
PLANT = Plant(cp_capacity_w={CP: 720_000}, holder_of={CP: "plant"}, issuers=("issuerA", "issuerB"))
DAY = 19200  # 27/7/2022, giờ mùa hè (PDT)
SUN = 52


def evidence(day: int, o1: int, flags: int = 0) -> LotEvidence:
    reps = tuple(OracleReport(o, CP, day, o1 if o is OracleId.O1 else 1000, o1 // 40 if o is OracleId.O1 else 10, 48)
                 for o in (OracleId.O1, OracleId.O2, OracleId.O3, OracleId.O4))
    return LotEvidence(CP, day, reps, flags, SUN)


def t_req(day: int) -> int:
    return local_t(day + 1, REQUEST_AT)


def setup(reg, devices=("B1", "B2")):
    for d in devices:
        assert reg.register_device(Device(d, CP, 120_000, "issuerA", effective_day=DAY - 10), 0).kind == "ok"
    reg.submit_lot_evidence(evidence(DAY, 600_000), "issuerA", t_req(DAY))
    return reg


def req(rid, dev, wh, issuer="issuerA", day=DAY):
    return IssueRequest(rid, issuer, dev, day, (wh,))


def test_key_budget_and_duplicate_device_on_shared_db():
    reg = setup(SqliteRegistry(PLANT))
    assert reg.issue(req("a", "B1", 400_000), t_req(DAY)).kind == "mint"
    assert reg.issue(req("b", "B1", 1), t_req(DAY)).reason == "key"                       # D1
    assert reg.issue(req("c", "B2", 200_001), t_req(DAY)).reason == "budget"              # D4a
    assert reg.register_device(Device("B1", CP, 120_000, "issuerB"), 0).reason == "DuplicateDevice"  # D3
    assert reg.issue(req("d", "B1", 1, issuer="issuerB"), t_req(DAY)).reason == "not_issuer"


def test_period_rules_follow_contract():
    reg = setup(SqliteRegistry(PLANT))
    assert reg.issue(req("early", "B1", 1), t_req(DAY) - 2 * 3600).reason == "period"   # trước khi ngày kết thúc
    assert reg.issue(req("ok", "B1", 1), t_req(DAY) - 1).kind == "mint"                    # 00:59:59 PDT vẫn hợp lệ
    two_years = IssueRequest("y", "issuerA", "B2", 19357, (1, 1))                          # 31/12/2022 → 1/1/2023
    assert reg.issue(two_years, t_req(19358)).reason == "period"


def test_capacity_rule():
    reg = setup(SqliteRegistry(PLANT))
    limit = 120_000 * SUN // 4
    reg.submit_lot_evidence(evidence(DAY + 1, 10_000_000), "issuerA", t_req(DAY + 1))
    assert reg.issue(req("c", "B1", limit + 1, day=DAY + 1), t_req(DAY + 1)).reason == "capacity"


def test_review_is_held_then_resolved():
    reg = setup(SqliteRegistry(PLANT))
    reg.submit_lot_evidence(evidence(DAY + 1, 600_000, flags=4), "issuerA", t_req(DAY + 1))
    assert reg.issue(req("a", "B1", 1, day=DAY + 1), t_req(DAY + 1)).kind == "held"
    assert reg.resolve_review(CP, DAY + 1, False, 0).kind == "ok"
    assert reg.issue(req("b", "B1", 1, day=DAY + 1), t_req(DAY + 1)).reason == "lot_rejected"


def test_lifecycle_and_code_manager():
    reg = setup(SqliteRegistry(PLANT))
    reg.issue(req("a", "B1", 100_000), t_req(DAY))
    assert reg.transfer(Transfer("B1", DAY, "plant", "buyer1", 60_000), 0).kind == "ok"
    r = Retire("B1", DAY, "buyer1", 60_000, "buyer1 (ESG)", "Scope 2", "California, US", "2022")
    assert reg.retire(r, 0).kind == "ok"
    assert reg.retire(r, 0).reason == "ERC1155InsufficientBalance"                                # D6
    assert reg.suspend("B1", DAY, True, "nghi", 0).kind == "ok"
    assert reg.transfer(Transfer("B1", DAY, "plant", "buyer2", 1), 0).reason == "TokenSuspended"
    assert reg.withdraw("B1", DAY, "plant", 40_000, "sai", 0).kind == "ok"
    assert reg.issue(req("b", "B1", 1), t_req(DAY)).reason == "key"                       # đã retire một phần


def test_withdraw_all_reopens_key():
    reg = setup(SqliteRegistry(PLANT))
    reg.issue(req("a", "B1", 100_000), t_req(DAY))
    reg.withdraw("B1", DAY, "plant", 100_000, "sai", 0)
    assert reg.issue(req("b", "B1", 90_000), t_req(DAY)).kind == "mint"


def test_operator_edit_leaves_no_trace():
    reg = setup(SqliteRegistry(PLANT))
    reg.issue(req("a", "B1", 100_000), t_req(DAY))
    out = reg.operator_edit(OperatorEdit("issuerA", "a", EditAction.REISSUE), 0)
    assert out.kind == "ok" and not out.trace
    assert reg.ledger.balance("B1:%d" % DAY, "plant") == 200_000


def test_separate_dbs_miss_duplicates_until_reconcile():
    reg = setup(SeparateRegistry(PLANT))
    assert reg.register_device(Device("B1", CP, 120_000, "issuerB", effective_day=DAY - 10), 0).kind == "ok"
    reg.issue(req("h", "B1", 300_000), t_req(DAY))
    assert reg.issue(req("d3", "B1", 300_000, issuer="issuerB"), t_req(DAY) + 60).kind == "mint"
    found = reg.reconcile(t_req(DAY) + 3600)
    assert [f["req_id"] for f in found] == ["d3"] and found[0]["rule"] == "key"


def test_separate_transfer_registration_moves_device():
    reg = setup(SeparateRegistry(PLANT))
    assert reg.transfer_registration(RegistrationTransfer("B2", "issuerA", "issuerB", DAY + 1), 0).kind == "ok"
    reg.submit_lot_evidence(evidence(DAY + 1, 600_000), "issuerA", t_req(DAY + 1))
    assert reg.issue(req("a", "B2", 1, day=DAY + 1), t_req(DAY + 1)).reason == "period"
    assert reg.issue(req("b", "B2", 1, issuer="issuerB", day=DAY + 1), t_req(DAY + 1)).kind == "mint"


def test_exposure_window():
    day = 86_400
    assert _exposure_days(t_mint=3 * day, t0=0, t1=100 * day, detected=True, t_rec=7) == (4.0, False)
    assert _exposure_days(t_mint=3 * day, t0=0, t1=100 * day, detected=False, t_rec=7) == (97.0, True)
    days, cens = _exposure_days(t_mint=95 * day, t0=0, t1=100 * day, detected=True, t_rec=30)
    assert cens and days == pytest.approx(5.0)
