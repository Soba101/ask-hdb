"""Solar geometry sanity checks independent of the map and the model."""

from datetime import date

import pytest

from ask_hdb.sun import facade_day, positions, wall_exposure


def test_equinox_solar_noon_and_sunrise_in_singapore():
    samples = positions(date(2026, 3, 20))
    noon = max(samples, key=lambda p: p["altitude"])
    assert noon["altitude"] == pytest.approx(88, abs=1.5)
    assert "13:00" <= noon["time"] <= "13:30"  # longitude and the civil timezone differ
    sunrise = next(p for p in samples if p["altitude"] > 0)
    assert sunrise["azimuth"] == pytest.approx(90, abs=3)


def test_west_wall_receives_more_afternoon_sun():
    samples = {s["time"]: s for s in positions("2026-03-20")}
    exposure = lambda t: wall_exposure(samples[t]["azimuth"], samples[t]["altitude"], 270)
    assert exposure("16:00") > exposure("09:00")


def test_away_and_perpendicular_walls_have_no_exposure():
    assert wall_exposure(90, 30, 270) == 0
    assert wall_exposure(90, 30, 0) == 0
    assert wall_exposure(90, 0, 90) == 1


@pytest.mark.parametrize("day", ["2024-02-29", "2026-06-21", "2026-12-21"])
def test_whole_local_day_and_facade_totals(day):
    samples = positions(day)
    assert len(samples) == 96 and samples[0]["time"] == "00:00" and samples[-1]["time"] == "23:45"
    assert all(0 <= s["azimuth"] < 360 and -90 <= s["altitude"] <= 90 for s in samples)
    facades = facade_day(day, [90, 270])
    for facade in facades:
        values = facade["exposure"]
        assert len(values) == 96 and all(0 <= v <= 1 for v in values)
        assert all(v == 0 for s, v in zip(samples, values) if s["altitude"] <= 0)
        assert facade["hours"] == sum(v > 0 for v in values) / 4
        assert facade["peak_time"] == samples[values.index(max(values))]["time"]
