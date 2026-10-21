"""Tools return the thresholds and counts that answers explain, so the grounding check passes
without being loosened. Each case is an answer the 9B model wrote from memory in the week 5-1 eval."""

import pandas as pd
import pytest

from ask_hdb import tools
from ask_hdb.bto import scenario
from ask_hdb.check_cases import PROFILE
from ask_hdb.geo import filters
from ask_hdb.grounding import check

SINGLE = PROFILE | {"scheme": "single", "citizenships": "SC", "ages": "34", "first_timer": "yes",
                    "family_timers": "not_applicable", "marital_status": "unmarried",
                    "buying_with": "alone", "monthly_household_income": 4000}
BTO = {key: value for key, value in PROFILE.items()
       if key not in {"room", "lease_left_months", "price", "category"}}


@pytest.fixture(autouse=True)
def fake_sales(monkeypatch, sales):
    monkeypatch.setattr(tools, "load_sales", lambda: sales)


def grounded(answer, result, question=""):
    assert "error" not in result, result
    assert check(answer, question, [result])["ungrounded"] == []


def test_single_minimum_ages_are_quotable():
    result = tools.can_buy_resale.invoke(SINGLE)
    assert result["eligible"] is False
    grounded("Singles must be at least 35 (21 if widowed or orphaned).", result)


def test_family_minimum_age_is_quotable():
    grounded("Both of you must be at least 21.", tools.can_buy_resale.invoke(PROFILE | {"ages": "20,20"}))


def test_ehg_work_months_are_quotable():
    result = tools.ehg_amount.invoke(PROFILE | {"works_12_months": False})
    grounded("EHG needs 12 months of continuous work.", result)
    assert check("EHG needs 24 months of work.", "", [result])["ungrounded"] == ["24"]  # still strict


def test_bto_revision_date_ceiling_and_ltv_are_quotable():
    result = tools.can_apply_bto.invoke(BTO | {"monthly_household_income": 17000, "category": "Standard",
                                               "flat_type": "4-room", "hfe_after_revision": True})
    assert result["eligible"] is False
    grounded("Your $17,000 is above the revised ceiling of $16,000 (HFE from 24 Aug 2026). "
             "The HDB loan limit is 75%.", result, question="Income $17000, can we apply?")


def test_bto_scenario_quotes_its_ltv():
    out = scenario.bto_scenario(pd.DataFrame(), 380000, 0, "hdb", None)
    assert out["ltv_pct"] == 75
    grounded("At 75% loan-to-value the HDB loan is $285,000.", out)


def test_nearest_places_counts_within_a_radius(monkeypatch):
    monkeypatch.setattr(filters, "load_blocks", lambda: pd.DataFrame({
        "block_id": ["blk_1"], "lat": [1.0], "lng": [103.0]}))
    monkeypatch.setattr(filters, "load_places", lambda: pd.DataFrame({
        "place_id": ["s_a", "s_b", "s_c", "m_a"], "name": ["A", "B", "C", "M"],
        "kind": ["primary_school"] * 3 + ["mrt"], "lat": [1.0, 1.005, 1.02, 1.0],
        "lng": [103.0] * 4}))
    result = tools.nearest_places.invoke({"block_id": "blk_1", "kind": "primary_school", "within_km": 1})
    assert result["n_within"] == 2 and len(result["places"]) == 2  # 0 km and about 0.56 km; 2.2 km is out
    grounded("2 primary schools are within 1 km.", result)
    assert "n_within" not in tools.nearest_places.invoke({"block_id": "blk_1", "kind": "primary_school"})
    # Small results for 8k-context servers: only the nearest n are listed, but n_within counts all.
    one = tools.nearest_places.invoke({"block_id": "blk_1", "kind": "primary_school", "within_km": 5, "n": 1})
    assert one["n_within"] == 3 and [p["place_id"] for p in one["places"]] == ["s_a"]
    assert "within_km" in tools.nearest_places.invoke({"block_id": "blk_1", "kind": "mrt", "within_km": 11})["error"]


def test_scenario_growth_figures_are_numbers():
    years = {2017 + i: 100 + 4 * i for i in range(9)}
    frame = pd.DataFrame([{"sale_month": pd.Timestamp(f"{y}-06-01"), "town": "BEDOK", "flat_type": "4 ROOM",
                           "resale_price": p} for y, p in years.items()])
    out = scenario.bto_scenario(frame, 400000, 0, "hdb", "Standard", 3.0, 25, "BEDOK", "4-room")
    low = out["past_low_growth_pct"]
    grounded(f"From 2017 to 2024 the past low growth was {low}%, capped at 3% a year.", out)
