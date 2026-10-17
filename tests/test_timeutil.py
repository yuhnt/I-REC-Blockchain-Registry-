from datetime import date, datetime, timezone

import pandas as pd
import pytest

from rec.timeutil import (
    PLANT_TZ,
    day_bounds_utc,
    day_date,
    day_number,
    local_day,
    local_days,
    localize_plant,
    slot_day,
    slot_days,
    slot_ends,
    slots_per_day,
)

UTC = timezone.utc


def test_day_number_round_trip():
    assert day_number(date(1970, 1, 1)) == 0
    d = date(2022, 7, 1)
    assert day_date(day_number(d)) == d


def test_afternoon_belongs_to_previous_utc_day():
    # 02:00 UTC ngày 01/07 là 19:00 PDT ngày 30/06: vẫn là ngày sản xuất 30/06.
    ts = datetime(2022, 7, 1, 2, 0, tzinfo=UTC)
    assert local_day(ts) == day_number(date(2022, 6, 30))


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError):
        local_day(datetime(2022, 7, 1, 12, 0))
    with pytest.raises(ValueError):
        local_days(pd.DatetimeIndex(["2022-07-01 12:00"]))


@pytest.mark.parametrize(
    ("d", "expected"),
    [(date(2022, 7, 1), 96), (date(2022, 3, 13), 92), (date(2022, 11, 6), 100)],
)
def test_slots_per_day_handles_dst(d, expected):
    n = day_number(d)
    assert slots_per_day(n) == expected
    assert len(slot_ends(n)) == expected


def test_day_bounds_utc_summer():
    start, end = day_bounds_utc(day_number(date(2022, 7, 1)))
    assert start == datetime(2022, 7, 1, 7, 0, tzinfo=UTC)
    assert end == datetime(2022, 7, 2, 7, 0, tzinfo=UTC)


def test_slot_ending_at_midnight_belongs_to_previous_day():
    midnight = datetime(2022, 7, 2, 0, 0, tzinfo=PLANT_TZ)
    assert slot_day(midnight) == day_number(date(2022, 7, 1))


def test_every_slot_end_maps_back_to_its_day():
    for d in (date(2022, 3, 13), date(2022, 7, 1), date(2022, 11, 6)):
        n = day_number(d)
        assert {slot_day(t) for t in slot_ends(n)} == {n}


def test_vectorized_matches_scalar_across_dst():
    idx = pd.date_range("2022-11-05 00:15", "2022-11-07 00:00", freq="15min", tz=UTC)
    expected = [slot_day(t.to_pydatetime()) for t in idx]
    assert slot_days(idx).tolist() == expected
    assert local_days(idx).tolist() == [local_day(t.to_pydatetime()) for t in idx]


def test_localize_plant_marks_ambiguous_and_nonexistent_as_nat():
    idx = pd.DatetimeIndex(["2022-11-06 01:30", "2022-03-13 02:30", "2022-07-01 12:00"])
    out = localize_plant(idx)
    assert out[0] is pd.NaT and out[1] is pd.NaT
    assert out[2] == pd.Timestamp("2022-07-01 19:00", tz=UTC)
