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
