import math

import pytest

from rec.oracles.encoding import MISSING, data_root, encode, to_ints


def test_missing_values_encode_as_minus_one():
    assert to_ints([1.4, None, math.nan, 2.6]) == [1, MISSING, MISSING, 3]
    assert encode([None]) == (-1).to_bytes(8, "big", signed=True)


def test_each_value_takes_eight_bytes():
    assert len(encode([0.0] * 96)) == 96 * 8
    assert len(encode([0.0] * 92)) == 92 * 8  # ngày sang giờ mùa hè


def test_root_changes_when_one_slot_changes():
    base = [100.0] * 96
    changed = base.copy()
    changed[40] = 101.0
    assert data_root(base) != data_root(changed)
    assert data_root(base) == data_root(list(base))
    assert len(data_root(base)) == 32


def test_missing_differs_from_zero():
    assert data_root([0.0, 5.0]) != data_root([None, 5.0])


def test_negative_value_rejected():
    with pytest.raises(ValueError):
        to_ints([-3.0])
