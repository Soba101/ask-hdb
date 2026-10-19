"""Compute sourced grant amounts and preserve unresolved assessments."""

from typing import Literal

from ._checks import (
    RuleUse,
    applicant_checks,
    first_timer_checks,
    income_key,
    lease_check,
    property_check,
)
from .loader import Rules
from .profile import BuyerProfile, Flat
from .result import RuleResult


def _cpf(use: RuleUse, profile: BuyerProfile, flat: Flat):
    applicant_checks(use, profile)
    first_timer_checks(use, profile)
    property_check(use, profile)
    single = profile.scheme == "single"
    prefix = "grants.cpf_family."
    lease_check(
        use,
        flat,
        prefix
        + (
            "singles_min_remaining_lease_years_exclusive"
            if single
            else "min_remaining_lease_years_exclusive"
        ),
    )
    if profile.monthly_household_income > use.get(income_key(profile)):
        use.deny("Income exceeds the CPF grant ceiling")
    large = flat.room >= use.get("eligibility.singles.max_flat_room_with_grants")
    if single:
        key = "singles_first_timer_5_room" if large else "singles_first_timer_2_to_4_room"
    else:
        if len(profile.citizenships) != 2:
            use.unknown("family_grant_applicant_composition")
        tier = "5_room_plus" if large else "2_to_4_room"
        if profile.family_timers == "one_first":
            key = f"first_and_second_timer_{tier}"
        else:
            citizenship = "sc_spr" if "SPR" in profile.citizenships else "sc_sc"
            key = f"first_timer_{tier}_{citizenship}"
    if use.result.eligible is True:
        use.result.amount = use.get(prefix + key)
        use.result.reasons.append("Qualifies for the CPF Housing Grant")


def cpf_housing_grant(profile: BuyerProfile, flat: Flat, rules: Rules | None = None) -> RuleResult:
    use = RuleUse(rules)
    _cpf(use, profile, flat)
    return use.result


def ehg_amount(profile: BuyerProfile, flat: Flat, rules: Rules | None = None) -> RuleResult:
    use = RuleUse(rules)
    use.get("grants.ehg.must_first_qualify_for_family_grant_on_resale")
    _cpf(use, profile, flat)
    # The prerequisite's amount is not an EHG award.
    use.result.amount = 0
    if use.result.eligible is not True:
        return use.result
    use.get("grants.ehg.min_continuous_work_months")
    if not profile.works_12_months:
        use.deny("Continuous employment requirement is not met")
    lease_check(use, flat, "grants.ehg.min_remaining_lease_years_exclusive")
    if use.result.eligible is not True:
        return use.result
    income = profile.monthly_household_income
    prefix = "grants.ehg."
    if profile.scheme == "family":
        if profile.family_timers == "one_first":
            income /= 2
            ceiling_key = "mixed_couple_assessed_income_ceiling_half_of_household"
            tiers_key = "mixed_couple_tiers_on_half_income"
        else:
            ceiling_key, tiers_key = "families_income_ceiling", "families_tiers"
    else:
        ceiling_key = (
            "singles_income_ceiling_alone"
            if profile.buying_with == "alone"
            else "singles_income_ceiling_household_with_other_singles_or_parents"
        )
        tiers_key = "singles_tiers_alone_or_with_parents"
        if profile.buying_with == "family_or_singles":
            use.unknown("ehg_joint_singles_assessment")
    if income > use.get(prefix + ceiling_key):
        use.deny("Income exceeds the EHG ceiling")
        return use.result
    if use.result.eligible is not True:
        return use.result
    assessed_income = profile.own_monthly_income if profile.scheme == "single" else income
    tiers = use.get(prefix + tiers_key)
    amount = next((band["amount"] for band in tiers if assessed_income <= band["up_to"]), 0)
    if not amount:
        use.deny("Assessed income exceeds the EHG amount table")
        return use.result
    use.result.amount = amount
    cover_age = use.get(prefix + "full_amount_lease_must_cover_youngest_to_age")
    if min(profile.ages) * 12 + flat.lease_left_months < cover_age * 12:
        # Keep the full award visible because the reduction formula is unpublished.
        use.result.needs_check.append("ehg_pro_rating")
        use.result.reasons.append("Full EHG shown before an unpublished lease reduction")
    return use.result


def phg_amount(
    profile: BuyerProfile,
    flat: Flat,
    relation: Literal["with", "near"] | None,
    rules: Rules | None = None,
) -> RuleResult:
    use = RuleUse(rules)
    if relation is None:
        use.deny("No proximity relationship supplied")
        return use.result
    if relation not in {"with", "near"}:
        raise ValueError("relation must be 'with', 'near' or None")
    applicant_checks(use, profile)
    # The PHG pages set no first-timer rule: second-timers qualify too (read 2026-10-20).
    property_check(use, profile)
    prefix = "grants.phg."
    lease_check(use, flat, prefix + "min_remaining_lease_years_exclusive")
    use.get(prefix + "income_ceiling")
    if profile.scheme == "single" and relation == "near":
        low, high = use.get(prefix + "singles_near_flat_room_range")
        if not low <= flat.room <= high:
            use.deny("Flat is outside the singles near-parent room range")
    if use.result.eligible is True:
        scheme = "families" if profile.scheme == "family" else "singles"
        use.result.amount = use.get(prefix + f"{scheme}_live_{relation}_parents_or_child")
        use.get(prefix + "once_only")
        # First-timer status does not establish previous use of this particular grant.
        use.result.needs_check.append("phg_previous_use")
    return use.result
