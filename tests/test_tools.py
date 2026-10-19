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
                                        "price": 150000, "flat_type": "4 ROOM", "min_n": 1})
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
