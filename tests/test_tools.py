"""Tool wrappers preserve the facts and citations from the plain functions."""

import json
from dataclasses import asdict

import pytest

from ask_hdb import tools
from ask_hdb.check_cases import PROFILE
from ask_hdb.rules import BuyerProfile, Flat, eligibility, grants, loan


@pytest.fixture(autouse=True)
def fake_data(monkeypatch, sales):
    monkeypatch.setattr(tools, "load_sales", lambda: sales)


def test_sales_tools():
    result = tools.price_stats.invoke({"town": "TAMPINES", "flat_type": "4 ROOM"})
    assert result["n_sales"] == 5
    assert result["median"] == 200000
    rows = tools.find_sales.invoke({"town": "TAMPINES", "limit": 1})["sales"]
    assert len(rows) == 1
    assert rows[0]["price"] == 500001
    assert rows[0]["sale_month"] == "2024-05"
    result = tools.compare_price.invoke({"block_id": "blk_001a_tampines-st-11",
                                        "price": 150000, "flat_type": "4 ROOM", "min_n": 1,
                                        "as_of": "latest", "storey_mid": None,
                                        "lease_left_months": None, "floor_area_sqm": None})
    assert result["n_comparables"] == 3
    assert result["median"] == 100000
    assert "not a valuation" in result["notes"][0]
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("name,function,extra", [
    ("can_buy_resale", eligibility.can_buy_resale, {}),
    ("cpf_housing_grant", grants.cpf_housing_grant, {}),
    ("ehg_amount", grants.ehg_amount, {}),
    ("phg_amount", grants.phg_amount, {"relation": "with"}),
    ("max_loan", loan.max_loan, {}),
])
def test_rules_keep_dicts_and_citations(name, function, extra):
    profile = BuyerProfile(scheme="family", citizenships=["SC", "SC"], ages=[35, 35],
                           monthly_household_income=4400, family_timers="both_first")
    flat = Flat(room=4, lease_left_months=960, price=600000, category="standard")
    result = getattr(tools, name).invoke(PROFILE | extra)
    assert result == asdict(function(profile, flat, **extra))
    assert result["rules"]
    assert all({"source", "as_of"} <= rule.keys() for rule in result["rules"])
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("name,args", [
    ("price_stats", {"since": "bad date"}),
    ("price_stats", {"unknown_filter": "TAMPINES"}),
    ("find_sales", {"limit": -1}),
    ("compare_price", {"block_id": "missing", "price": -1, "flat_type": "4 ROOM"}),
    ("can_buy_resale", {}),
    ("cpf_housing_grant", PROFILE | {"ages": "unknown"}),
    ("ehg_amount", PROFILE | {"citizenships": "XX,SC"}),
    ("phg_amount", PROFILE | {"relation": "far"}),
    ("max_loan", PROFILE | {"qualifying_rate_pct": float("nan")}),
])
def test_bad_arguments_return_error(name, args):
    result = getattr(tools, name).invoke(args)
    assert isinstance(result["error"], str)
    json.dumps(result, allow_nan=False)


def test_lazy_load_once(monkeypatch, sales):
    # Patch the cached function's reader, rather than relying on local data files.
    from importlib import reload

    reload(tools)
    reads = []
    monkeypatch.setattr(tools.pd, "read_parquet", lambda path: reads.append(path) or sales)
    try:
        tools.price_stats.invoke({})
        tools.find_sales.invoke({})
        assert len(reads) == 1
    finally:
        tools.load_sales.cache_clear()


def test_bare_year_means_whole_year():
    # "2025" as an end date must not cut the year to January.
    year = tools.price_stats.invoke({"town": "TAMPINES", "since": "2024", "until": "2024"})
    months = tools.price_stats.invoke({"town": "TAMPINES", "since": "2024-01", "until": "2024-12"})
    assert year == months


SINGLE = {"scheme": "single", "citizenships": "SC", "ages": "35", "monthly_household_income": 2000,
          "room": 3, "lease_left_months": 960} | {
    "previous_hdb_loans": 0, "works_12_months": True, "owns_private_property": False,
    "marital_status": "unmarried", "family_timers": "not_applicable"}


def test_single_with_both_timer_fields_still_works():
    # Models send family_timers too; the wrapper keeps only first_timer for a single.
    result = tools.ehg_amount.invoke(SINGLE | {"first_timer": "yes", "family_timers": "none_first"})
    assert "error" not in result and result["amount"] == 40000


def test_missing_required_profile_fields_are_named():
    args = {k: v for k, v in SINGLE.items() if k != "works_12_months"}
    result = tools.ehg_amount.invoke(args | {"first_timer": "yes"})
    assert "works_12_months" in result["error"]


def test_single_without_marital_status_gets_an_error():
    args = {k: v for k, v in SINGLE.items() if k != "marital_status"}
    result = tools.can_buy_resale.invoke(args | {"first_timer": "yes"})
    assert "marital_status" in result["error"]


def test_unknown_marital_status_is_a_needs_check_not_a_guess():
    args = SINGLE | {"ages": "30", "first_timer": "yes", "marital_status": "unknown"}
    result = tools.can_buy_resale.invoke(args)
    assert result["eligible"] is None and "marital_status" in result["needs_check"]


def test_as_of_is_required_and_latest_means_newest_month():
    args = {"block_id": "blk_001a_tampines-st-11", "price": 150000, "flat_type": "4 ROOM", "min_n": 1,
            "storey_mid": None, "lease_left_months": None, "floor_area_sqm": None}
    assert "as_of" in tools.compare_price.invoke(args)["error"]
    latest = tools.compare_price.invoke(args | {"as_of": "latest", "storey_mid": None,
                                        "lease_left_months": None, "floor_area_sqm": None})
    explicit = tools.compare_price.invoke(args | {"as_of": "2024-06"})
    assert latest == explicit  # the fixture's newest month is 2024-06


def test_compare_filters_are_required_but_nullable():
    args = {"block_id": "blk_001a_tampines-st-11", "price": 150000, "flat_type": "4 ROOM", "min_n": 1,
            "as_of": "latest", "storey_mid": None, "lease_left_months": None}
    assert "floor_area_sqm" in tools.compare_price.invoke(args)["error"]
    assert "n_comparables" in tools.compare_price.invoke(args | {"floor_area_sqm": None})


def test_calculate_does_arithmetic_and_rejects_everything_else():
    assert tools.calculate.invoke({"expression": "$80,000 + 70,000 + 30,000"})["result"] == 180000
    assert tools.calculate.invoke({"expression": "(650000 - 625000) - (620000 - 523000)"})["result"] == -72000
    assert tools.calculate.invoke({"expression": "10 / 4"})["result"] == 2.5
    for bad in ("__import__('os').system('x')", "2 ** 9999", "abs(-1)", "1; 2", "a + 1"):
        assert "error" in tools.calculate.invoke({"expression": bad})


def test_text_none_means_no_filter():
    args = {"block_id": "blk_001a_tampines-st-11", "price": 150000, "flat_type": "4 ROOM", "min_n": 1,
            "as_of": "latest", "storey_mid": "None", "lease_left_months": "null", "floor_area_sqm": "None", "max_examples": "None"}
    assert "n_comparables" in tools.compare_price.invoke(args)
