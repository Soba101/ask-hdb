"""Verify loan arithmetic independently from the implementation."""

import math

import pytest

from ask_hdb.rules import max_loan


def test_loan_annuity_by_hand(family, flat):
    profile = family(monthly_household_income=6000, ages=[40, 40])
    result = max_loan(profile, flat())
    # Payment is 30% of income, over 25 years at the 3% qualifying floor.
    payment, monthly_rate, payments = 1800, 0.03 / 12, 25 * 12
    expected = math.floor(payment * (1 - (1 + monthly_rate) ** -payments) / monthly_rate)
    assert result.amount == expected
    assert result.detail == {
        "monthly_payment_cap": payment,
        "tenure_years": 25,
        "rate_pct": 3.0,
        "binding_cap": "msr",
    }


def test_ltv_cap_binds(family, flat):
    result = max_loan(family(), flat(price=100000))
    assert result.amount == 75000
    assert result.detail["binding_cap"] == "ltv"


@pytest.mark.parametrize("months,flag", [(719, True), (720, False)])
def test_ltv_prorating_preserves_full_limit(family, flat, months, flag):
    result = max_loan(family(), flat(price=100000, lease_left_months=months))
    assert result.amount == 75000
    assert ("ltv_pro_rating" in result.needs_check) is flag


@pytest.mark.parametrize(
    "ages,lease,months",
    [([55, 56], 960, 114), ([35, 35], 241, 1), ([65, 65], 960, 0), ([70, 70], 960, 0)],
)
def test_tenure_uses_average_age_and_whole_months(family, flat, ages, lease, months):
    result = max_loan(family(ages=ages), flat(lease_left_months=lease))
    assert result.detail["tenure_years"] == months / 12
    assert result.eligible is (months > 0)


@pytest.mark.parametrize(
    "income,extended,eligible",
    [(16000, False, True), (16001, False, False), (24000, True, True), (24001, True, False)],
)
def test_family_loan_income_ceiling(family, flat, income, extended, eligible):
    profile = family(monthly_household_income=income, extended_family=extended)
    assert max_loan(profile, flat()).eligible is eligible


@pytest.mark.parametrize(
    "income,age,eligible", [(8000, 35, True), (8001, 35, False), (2000, 34, False)]
)
def test_single_loan_income_and_age(single, flat, income, age, eligible):
    profile = single(monthly_household_income=income, ages=[age], marital_status="widowed")
    assert max_loan(profile, flat()).eligible is eligible


def test_loan_lease_and_private_property(family, flat):
    assert max_loan(family(), flat(lease_left_months=240)).eligible is False
    assert max_loan(family(owns_private_property=True), flat()).eligible is False


def test_higher_qualifying_rate_reduces_loan(family, flat):
    normal = max_loan(family(), flat())
    higher = max_loan(family(), flat(), qualifying_rate_pct=4.0)
    assert higher.amount < normal.amount
    assert higher.detail["rate_pct"] == 4.0
    assert max_loan(family(), flat(), qualifying_rate_pct=0).amount == normal.amount


@pytest.mark.parametrize("rate", [-1, float("inf"), float("nan")])
def test_invalid_qualifying_rate(family, flat, rate):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        max_loan(family(), flat(), qualifying_rate_pct=rate)


@pytest.mark.parametrize("price,check", [
    (None, "ltv_not_applied"), (100000, "ltv_valuation_not_modelled"),
])
def test_ltv_assumptions_are_explicit(family, flat, price, check):
    result = max_loan(family(), flat(price=price, lease_left_months=719))
    assert result.eligible is True
    assert result.needs_check == [check, "ltv_pro_rating"]


@pytest.mark.parametrize("previous,eligible", [(0, True), (1, True), (2, False), (3, False)])
def test_previous_loan_limit(family, flat, previous, eligible):
    result = max_loan(family(previous_hdb_loans=previous), flat(price=100000))
    assert result.eligible is eligible
    assert result.amount == (75000 if eligible else 0)
    assert ("Too many previous HDB loans" in result.reasons) is (not eligible)
