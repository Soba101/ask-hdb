import pandas as pd
import pytest

from ask_hdb import tools
from ask_hdb.bto import scenario


def test_instalment_and_balance():
    assert scenario.instalment(120000, 0, 10) == pytest.approx(1000)
    assert scenario.instalment(300000, 3, 25) == pytest.approx(1422.6, abs=0.5)
    assert scenario.balance(120000, 0, 10, 60) == pytest.approx(60000)
    assert scenario.balance(300000, 3, 25, 300) == pytest.approx(0, abs=1)
    assert scenario.balance(300000, 3, 25, 0) == pytest.approx(300000)


def sales(prices_by_year):
    rows = [{"sale_month": pd.Timestamp(f"{y}-06-01"), "town": "BEDOK", "flat_type": "4 ROOM", "resale_price": p}
            for y, p in prices_by_year.items()]
    return pd.DataFrame(rows)


def run(frame, **over):
    args = {"price": 400000, "grants": 50000, "loan_kind": "hdb", "interest_rate_pct": 3.0, "loan_years": 25,
            "category": "Standard", "town": "BEDOK", "flat_type": "4-room"} | over
    return scenario.bto_scenario(frame, **args)


def test_scenarios_use_low_growth_as_headline_and_floor_at_zero():
    frame = sales({2018: 100, 2019: 110, 2020: 105, 2021: 120, 2022: 130, 2023: 140, 2024: 150, 2025: 160})
    out = run(frame)
    low, median = out["scenarios"][1], out["scenarios"][2]
    assert out["loan_amount"] == 300000 and out["mop_years"] == 5 and out["upfront_needed_cash_or_cpf"] == 50000
    assert out["scenarios"][0]["sale_price"] == 400000
    assert 0 <= low["annual_growth_pct"] <= median["annual_growth_pct"] <= 3.0
    assert low["cash_before_cpf_refund"] == low["sale_price"] - low["loan_balance_at_sale"]
    assert {"cpf_refund_and_accrued_interest_on_sale", "grant_refund_on_sale"} <= set(out["needs_check"])
    assert "not a forecast" in out["note"]


def test_falling_prices_give_flat_scenarios_and_missing_history_is_flagged():
    falling = sales({2018: 160, 2019: 150, 2020: 140, 2021: 130, 2022: 120, 2023: 110, 2024: 100, 2025: 90})
    assert run(falling)["scenarios"][2]["annual_growth_pct"] == 0
    out = run(sales({2024: 100, 2025: 110}))
    assert out["scenarios"] == [] and "growth_history_for_town_and_flat_type" in out["needs_check"]
    assert "plus_prime_subsidy_recovery" in run(falling, category="Prime")["needs_check"]
    assert run(falling, category="Prime")["mop_years"] == 10


def test_tool_registered_and_rejects_missing_rate():
    assert any(t.name == "bto_scenario" for t in tools.TOOLS)
    assert "interest_rate_pct" in tools.bto_scenario.invoke(
        {"price": 1, "grants": 0, "loan_kind": "hdb", "loan_years": 25, "category": "Standard"})["error"]
