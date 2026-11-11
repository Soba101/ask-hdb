"""A purchase can pass even when its financing does not."""

import pytest

from ask_hdb.rules import can_buy_resale


@pytest.mark.parametrize("scheme", ["family", "single"])
def test_high_income_does_not_block_standard_purchase(family, single, flat, scheme):
    profile = (family if scheme == "family" else single)(monthly_household_income=100000)
    result = can_buy_resale(profile, flat(category="standard"))
    assert result.eligible is True
    assert "Income is above the CPF grant ceiling" in result.reasons
    assert "Income is above the HDB loan ceiling" in result.reasons


def test_private_property_is_reason_only(family, flat):
    result = can_buy_resale(family(owns_private_property=True), flat())
    assert result.eligible is True
    assert any("Private property" in reason for reason in result.reasons)


@pytest.mark.parametrize(
    "citizenship,check",
    [("SPR", "spr_not_supported_v1"), ("foreigner", "foreigner_not_supported_v1")],
)
def test_family_citizenship_outside_purchase_scope(family, flat, citizenship, check):
    result = can_buy_resale(family(citizenships=["SC", citizenship]), flat())
    assert result.eligible is None
    assert check in result.needs_check


@pytest.mark.parametrize("ages,eligible", [([21, 21], True), ([20, 21], False)])
def test_family_age(family, flat, ages, eligible):
    assert can_buy_resale(family(ages=ages), flat()).eligible is eligible


@pytest.mark.parametrize(
    "age,status,eligible",
    [
        (35, "unmarried", True),
        (34, "unmarried", False),
        (21, "widowed", True),
        (20, "widowed", False),
        (35, "married", False),
        (34, None, None),
        (20, None, False),
    ],
)
def test_single_age_and_status(single, flat, age, status, eligible):
    profile = single(ages=[age], marital_status=status)
    assert can_buy_resale(profile, flat()).eligible is eligible


def test_single_requires_citizen(single, flat):
    assert can_buy_resale(single(citizenships=["SPR"]), flat()).eligible is False


def test_unknown_plus_project_ceiling(family, flat):
    result = can_buy_resale(family(), flat(room=3, category="plus"))
    assert result.eligible is None
    assert "plus_3room_project_ceiling" in result.needs_check


@pytest.mark.parametrize("scheme,company,extended,ceiling", [
    ("family", "alone", False, 16000), ("family", "alone", True, 24000),
    ("single", "alone", False, 8000), ("single", "parents", False, 8000),
])
@pytest.mark.parametrize("above", [False, True])
def test_unknown_category_income_boundary(family, single, flat, scheme, company,
                                         extended, ceiling, above):
    profile = (family if scheme == "family" else single)(
        monthly_household_income=ceiling + int(above), buying_with=company,
        extended_family=extended,
    )
    result = can_buy_resale(profile, flat())
    assert result.eligible is (None if above else True)
    assert result.needs_check == (["flat_category"] if above else [])
    assert not any("no income ceiling" in reason for reason in result.reasons)


@pytest.mark.parametrize("category", ["standard", "plus", "prime", None])
def test_only_standard_has_no_income_ceiling_reason(family, flat, category):
    result = can_buy_resale(family(), flat(category=category))
    assert any("no income ceiling" in reason for reason in result.reasons) is (
        category == "standard"
    )


def test_family_with_one_listed_applicant_asks_for_the_household_first():
    # Reproduced from a full app test: one family applicant passed every check as eligible.
    from ask_hdb.rules import (
        BuyerProfile,
        Flat,
        can_buy_resale,
        cpf_housing_grant,
        ehg_amount,
        max_loan,
    )
    from ask_hdb.rules.bto import bto_ehg, can_apply_bto

    one = BuyerProfile(scheme="family", citizenships=["SC"], ages=[30], monthly_household_income=5000,
                       family_timers="both_first", confirmed=True)
    flat = Flat(room=4, lease_left_months=80 * 12, price=500_000)
    for result in [can_buy_resale(one, flat), max_loan(one, flat), cpf_housing_grant(one, flat),
                   ehg_amount(one, flat), bto_ehg(one), can_apply_bto(one, "Standard", "4-room")]:
        assert result.eligible is None and "family_second_applicant" in result.needs_check
    two = one.model_copy(update={"citizenships": ["SC", "SC"], "ages": [30, 29]})
    assert can_buy_resale(two, flat).eligible is True and "family_second_applicant" not in can_buy_resale(two, flat).needs_check
