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
    assert out["scenarios"][0]["sale_price"] == 400000 and "can also fall" in out["note"]
    assert 0 <= low["annual_growth_pct"] <= median["annual_growth_pct"] <= 3.0
    assert low["cash_before_cpf_refund"] == pytest.approx(low["sale_price"] - low["loan_balance_at_sale"], abs=1000)
    assert {"cpf_refund_and_accrued_interest_on_sale", "grant_refund_on_sale"} <= set(out["needs_check"])
    assert "not a forecast" in out["note"]


def test_falling_prices_give_flat_scenarios_and_missing_history_is_flagged():
    falling = sales({2018: 160, 2019: 150, 2020: 140, 2021: 130, 2022: 120, 2023: 110, 2024: 100, 2025: 90})
    assert run(falling)["scenarios"][2]["annual_growth_pct"] == 0
    out = run(sales({2024: 100, 2025: 110}))
    assert out["scenarios"] == [] and "growth_history_for_town_and_flat_type" in out["needs_check"]
    assert "plus_prime_subsidy_recovery" in run(falling, category="Prime")["needs_check"]
    assert run(falling, category="Prime")["mop_years"] == 10


def test_tool_registered_and_rate_is_optional():
    assert any(t.name == "bto_scenario" for t in tools.TOOLS)
    out = scenario.bto_scenario(sales({2024: 1}), 380000, 0, "hdb", "Standard")
    assert out["loan_amount"] == 285000 and out["upfront_needed_cash_or_cpf"] == 95000
    assert out["monthly_instalment"] is None and out["scenarios"] == []
    assert "interest_rate_and_loan_years_for_instalment_and_scenarios" in out["needs_check"]


def test_category_is_optional_and_only_needed_for_scenarios():
    out = scenario.bto_scenario(sales({2024: 1}), 450000, 0, "hdb", None, 2.6, 25)
    assert out["monthly_instalment"] == 1531 and out["scenarios"] == []
    assert "category_for_mop_years_and_sale_scenarios" in out["needs_check"]


def test_labels_show_floor_and_cap_and_basis_shows_real_past_low():
    falling = sales({2018: 160, 2019: 150, 2020: 140, 2021: 130, 2022: 120, 2023: 110, 2024: 100, 2025: 90})
    out = run(falling)
    assert "floored at 0" in out["scenarios"][1]["name"] and "past low -" in out["growth_basis"]
    boom = sales({2018: 100, 2019: 120, 2020: 145, 2021: 175, 2022: 210, 2023: 250, 2024: 300, 2025: 360})
    out = run(boom, loan_kind="bank")
    assert "capped at 3%" in out["scenarios"][1]["name"] and out["scenarios"][1]["annual_growth_pct"] == 3.0
    assert "bank_ltv_not_separately_confirmed" in out["needs_check"]
    assert "loan_amount_assumes_max_ltv_check_hle_msr_and_cpf_paid_in" in out["needs_check"]


def test_category_is_required_but_nullable_and_both_hints_appear():
    assert "category" in tools.bto_scenario.invoke({"price": 1, "grants": 0, "loan_kind": "hdb"})["error"]
    out = scenario.bto_scenario(sales({2024: 1}), 380000, 0, "hdb", None)
    assert {"interest_rate_and_loan_years_for_instalment_and_scenarios",
            "category_for_mop_years_and_sale_scenarios"} <= set(out["needs_check"])
