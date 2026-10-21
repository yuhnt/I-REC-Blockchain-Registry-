import pytest

from rec.gate.auditor import Auditor, Lifecycle


def test_draw_is_fixed_per_lot_so_checked_sets_are_nested():
    a = Auditor(seed=0)
    keys = [f"case-{i}" for i in range(2000)]
    u = [a.draw(k) for k in keys]
    assert u == [Auditor(seed=0).draw(k) for k in keys]          # tái lập được
    at1 = {k for k, x in zip(keys, u) if x < 0.01}
    at5 = {k for k, x in zip(keys, u) if x < 0.05}
    assert at1 <= at5 and 0.03 < len(at5) / len(keys) < 0.07     # p = 1% nằm trong p = 5%


def test_unchecked_or_p0_leaves_excess():
    a = Auditor()
    assert a.after_check("x", 1000.0, [500, 500], 0.0) == 1000.0
    assert a.after_check("x", 0.0, [500, 500], 1.0) == 0.0


def test_checked_lot_is_withdrawn_except_retired_part():
    instant = Lifecycle(transfer_prob=1.0, transfer_delay=(0, 0), retire_prob=1.0, retire_delay=(0, 0))
    never = Lifecycle(transfer_prob=0.0, transfer_delay=(0, 0), retire_prob=0.0, retire_delay=(0, 0))
    assert Auditor(lifecycle=instant).after_check("x", 1000.0, [400, 600], 1.0) == pytest.approx(1000.0)
    assert Auditor(lifecycle=never).after_check("x", 1000.0, [400, 600], 1.0) == 0.0


def test_default_lifecycle_rarely_retires_before_check():
    """Theo honest_stream, chứng chỉ chỉ retire trước 12:00 ngày d + 2 khi cả hai độ trễ bằng 0."""
    a = Auditor()
    shares = [a.retired_share(f"lot-{i}", [100] * 6) for i in range(3000)]
    assert sum(shares) / len(shares) < 0.002


def test_resolve_review_follows_truth():
    assert Auditor.resolve(0) and not Auditor.resolve(1)
