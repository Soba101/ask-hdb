"""bto_history returns the stored comparison rows with the limits that must travel with them."""

import pytest

from ask_hdb import tools
from ask_hdb.bto import queries


@pytest.fixture(autouse=True)
def history_table(monkeypatch):
    import pandas as pd
    table = pd.DataFrame([
        {"financial_year": 2008, "town": "PUNGGOL", "flat_type": "4 ROOM", "launch_low": 223000, "launch_high": 327000,
         "n_resales": 1000, "resale_median": 460000.0, "resale_p25": 433666.0, "resale_p75": 505000.0,
         "median_minus_launch_high": 133000.0},
        {"financial_year": 2013, "town": "PUNGGOL", "flat_type": "4 ROOM", "launch_low": 1, "launch_high": 2,
         "n_resales": 40, "resale_median": 3.0, "resale_p25": 2.0, "resale_p75": 4.0, "median_minus_launch_high": 1.0},
    ])
    monkeypatch.setattr(queries, "load_history", lambda: table)


def test_rows_for_one_year_carry_the_limits():
    out = queries.bto_history("punggol", "4-room", 2008)
    assert out["n_rows"] == 1 and out["rows"][0]["resale_median"] == 460000.0
    assert any("not a forecast" in text for text in out["limits"])


def test_all_years_are_ordered_and_a_missing_town_is_empty():
    assert [r["financial_year"] for r in queries.bto_history("PUNGGOL", "4-room")["rows"]] == [2008, 2013]
    assert queries.bto_history("BEDOK", "4-room")["n_rows"] == 0


def test_tool_rejects_a_year_outside_the_table():
    out = tools.bto_history.invoke({"town": "PUNGGOL", "flat_type": "4-room", "financial_year": 2024})
    assert "error" in out or "Not accepted" in str(out) or "Missing or invalid" in str(out)
