"""Check grant boundaries with independently specified expected awards."""

import pytest

from ask_hdb.rules import cpf_housing_grant, ehg_amount, phg_amount


@pytest.mark.parametrize("income,amount", [(4500, 70000), (4501, 65000), (9000, 5000), (9001, 0)])
def test_family_ehg_tier_edges(family, flat, income, amount):
    assert ehg_amount(family(monthly_household_income=income), flat()).amount == amount


@pytest.mark.parametrize(
    "income,extended,amount",
    [(16000, False, 80000), (16001, False, 0), (24000, True, 80000), (24001, True, 0)],
)
def test_family_grant_ceiling(family, flat, income, extended, amount):
    profile = family(monthly_household_income=income, extended_family=extended)
    assert cpf_housing_grant(profile, flat()).amount == amount


@pytest.mark.parametrize(
    "income,company,amount",
    [
        (8000, "alone", 40000),
        (8001, "alone", 0),
        (16000, "family_or_singles", 40000),
        (16001, "family_or_singles", 0),
        (9000, "parents", 40000),
    ],
)
def test_single_grant_ceiling(single, flat, income, company, amount):
    profile = single(monthly_household_income=income, buying_with=company)
    assert cpf_housing_grant(profile, flat()).amount == amount


@pytest.mark.parametrize(
    "household,own,amount",
    [(9000, 2000, 40000), (9001, 2000, 0), (9000, 4501, 0), (4500, 4500, 2500)],
)
def test_single_with_parents_uses_own_income(single, flat, household, own, amount):
    profile = single(
        monthly_household_income=household, own_monthly_income=own, buying_with="parents"
    )
    assert ehg_amount(profile, flat()).amount == amount


def test_single_alone_household_ceiling_still_applies(single, flat):
    profile = single(monthly_household_income=4501, own_monthly_income=2000)
    assert ehg_amount(profile, flat()).amount == 0


@pytest.mark.parametrize("income,amount", [(4400, 35000), (9000, 2500), (9001, 0)])
def test_mixed_couple_halves_income(family, flat, income, amount):
    profile = family(monthly_household_income=income, family_timers="one_first")
    assert ehg_amount(profile, flat()).amount == amount


@pytest.mark.parametrize("months,amount", [(240, 0), (241, 80000)])
def test_grant_lease_is_strict(family, flat, months, amount):
    assert cpf_housing_grant(family(), flat(lease_left_months=months)).amount == amount


@pytest.mark.parametrize("months,flag", [(719, True), (720, False)])
def test_ehg_prorating_preserves_full_amount(family, flat, months, flag):
    result = ehg_amount(family(ages=[35, 40]), flat(lease_left_months=months))
    assert result.amount == 70000
    assert ("ehg_pro_rating" in result.needs_check) is flag


@pytest.mark.parametrize(
    "timer,amount", [("both_first", 80000), ("one_first", 40000), ("none_first", 0)]
)
def test_family_timer_types(family, flat, timer, amount):
    assert cpf_housing_grant(family(family_timers=timer), flat()).amount == amount


def test_missing_timer_and_unsupported_composition(family, flat):
    assert cpf_housing_grant(family(family_timers=None), flat()).eligible is None
    assert cpf_housing_grant(family(citizenships=["SC"], ages=[35]), flat()).eligible is None


def test_second_timer_single_and_private_owner(single, family, flat):
    assert cpf_housing_grant(single(first_timer=False), flat()).amount == 0
    for function in (cpf_housing_grant, ehg_amount):
        assert function(family(owns_private_property=True), flat()).eligible is False


@pytest.mark.parametrize(
    "timer,company,amount",
    [
        ("family", "with", 30000),
        ("family", "near", 20000),
        ("single", "with", 15000),
        ("single", "near", 10000),
    ],
)
def test_phg_has_no_income_ceiling(family, single, flat, timer, company, amount):
    profile = (family if timer == "family" else single)(monthly_household_income=100000)
    result = phg_amount(profile, flat(), company)
    assert result.amount == amount
    assert result.eligible is True
    assert "phg_previous_use" in result.needs_check


def test_phg_relationship_timers_and_lease(family, single, flat):
    assert phg_amount(family(), flat(), None).amount == 0
    # The PHG has no first-timer rule, so second-timers get the same amounts.
    assert phg_amount(family(family_timers="none_first"), flat(), "near").amount == 20000
    assert phg_amount(single(first_timer=False), flat(), "with").amount == 15000
    assert phg_amount(single(), flat(lease_left_months=240), "near").amount == 0
    assert phg_amount(single(), flat(lease_left_months=241, room=2), "near").amount == 10000


def test_joint_single_ehg_requires_separate_assessment(single, flat):
    result = ehg_amount(single(buying_with="family_or_singles", own_monthly_income=2000), flat())
    assert result.eligible is None
    assert "ehg_joint_singles_assessment" in result.needs_check


@pytest.mark.parametrize("function", [cpf_housing_grant, ehg_amount])
def test_foreigner_grants_are_undecidable(function, family, flat):
    result = function(family(citizenships=["SC", "foreigner"]), flat())
    assert result.eligible is None
    assert result.amount == 0
    assert "foreigner_not_supported_v1" in result.needs_check


@pytest.mark.parametrize("months,amount", [(240, 0), (241, 70000)])
def test_ehg_lease_boundary(family, flat, months, amount):
    result = ehg_amount(family(), flat(lease_left_months=months))
    assert result.amount == amount


def test_single_larger_flat_and_widow_grant(single, flat):
    assert cpf_housing_grant(single(), flat(room=5)).amount == 25000
    assert cpf_housing_grant(single(ages=[21], marital_status="widowed"), flat()).amount == 40000


@pytest.mark.parametrize("buying_with", ["parents", "family_or_singles"])
@pytest.mark.parametrize("income", [2000, 10000])
def test_joint_single_missing_own_income(single, flat, buying_with, income):
    profile = single(buying_with=buying_with, monthly_household_income=income)
    assert profile.own_monthly_income is None
    result = ehg_amount(profile, flat())
    assert result.eligible is None
    assert result.amount == 0
    assert result.needs_check == ["own_monthly_income"]


def test_alone_assesses_household_as_own_income(single, flat):
    result = ehg_amount(single(monthly_household_income=2000, own_monthly_income=1000), flat())
    assert result.amount == 40000


@pytest.mark.parametrize("room", [2, 4, 5, 6])
@pytest.mark.parametrize("timer,small,large", [
    ("both_first", 80000, 50000), ("one_first", 40000, 25000),
])
def test_family_room_tiers(family, flat, room, timer, small, large):
    result = cpf_housing_grant(family(family_timers=timer), flat(room=room))
    assert result.eligible is True
    assert result.amount == (small if room <= 4 else large)


def test_single_cannot_get_grants_for_executive_flat(single, flat):
    # Singles' grants stop at 5-room flats (eligibility.singles.max_flat_room_with_grants).
    for function in (cpf_housing_grant, ehg_amount):
        result = function(single(), flat(room=6))
        assert (result.eligible, result.amount) == (False, 0)


def test_family_executive_flat_uses_large_tier(family, flat):
    # Families get the 5-room-or-larger amount: SC+SC first-timers, 50000.
    result = cpf_housing_grant(family(), flat(room=6))
    assert (result.eligible, result.amount) == (True, 50000)


def test_one_room_flat_has_no_published_grant_amount(family, single, flat):
    for profile in (family(), single()):
        result = cpf_housing_grant(profile, flat(room=1))
        assert result.eligible is None
        assert result.amount == 0
        assert "room_below_grant_tables" in result.needs_check
