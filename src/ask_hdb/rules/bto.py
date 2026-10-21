"""BTO (new flat) eligibility and EHG. Only values confirmed in HDB annexes are used; the rest is flagged."""

from ._checks import RuleUse, applicant_checks, first_timer_checks, property_check
from .loader import RULES_DIR, Rules, load_rules
from .profile import BuyerProfile
from .result import RuleResult

BTO_FILE = RULES_DIR / "bto/2026-10.yaml"
FLEXI = "2-room Flexi"


def _ceilings(use: RuleUse, profile: BuyerProfile, flat_type: str) -> tuple[int, int]:
    """(previous, revised) monthly household income ceiling for this buyer and flat type."""
    if profile.scheme == "single":
        return use.get("eligibility.singles_flexi_99yr_previous"), use.get("eligibility.singles_flexi_99yr_revised")
    if flat_type == FLEXI:
        return use.get("eligibility.flexi_99yr_previous"), use.get("eligibility.flexi_99yr_revised")
    # A 3Gen flat uses the extended-family ceiling whatever the household shape.
    kind = "extended_families" if profile.extended_family or flat_type == "3Gen" else "families"
    return use.get(f"eligibility.{kind}_previous"), use.get(f"eligibility.{kind}_revised")


def can_apply_bto(profile: BuyerProfile, category: str, flat_type: str, hfe_after_revision: bool | None = None,
                  rules: Rules | None = None, bto_rules: Rules | None = None) -> RuleResult:
    """category: Standard, Plus or Prime. hfe_after_revision: HFE letter applied for on or after 2026-08-24 (None = unknown)."""
    resale = RuleUse(rules)
    use = RuleUse(bto_rules or load_rules(BTO_FILE), resale.result)
    applicant_checks(resale, profile)
    if profile.scheme == "single" and flat_type != use.get("eligibility.singles_bto_flat_type"):
        use.deny("Singles can only buy 2-room Flexi flats in BTO")
    timers_known = profile.family_timers if profile.scheme == "family" else profile.first_timer
    if timers_known is None:
        use.unknown("first_or_second_timer")
    elif timers_known in {"none_first", False}:
        # HDB's second-timer flat-type and supply rules were not found, so no verdict is given.
        use.unknown("second_timer_flat_types_and_quota")
    if flat_type == FLEXI and max(profile.ages) >= 55:
        # Short-lease 2-room Flexi (age 55+) has a higher ceiling that is not modelled; the 99-year one is used below.
        use.unknown("short_lease_flexi_income_ceiling")
    previous, revised = _ceilings(use, profile, flat_type)
    income = profile.monthly_household_income
    if hfe_after_revision is None:
        if income > revised:
            use.deny(f"Income is above the revised ceiling of {revised}")
        elif income > previous:
            use.unknown("hfe_application_date")
            use.result.reasons.append(f"Income is within the revised ceiling ({revised}) but above the previous one ({previous})")
    else:
        ceiling = revised if hfe_after_revision else previous
        if income > ceiling:
            use.deny(f"Income is above the applicable ceiling of {ceiling}")
    if profile.extended_family:
        use.unknown("each_family_nucleus_income_cap")
    if profile.owns_private_property:
        use.unknown("property_ownership_rule_for_bto")
    if use.result.eligible is not False and not profile.works_12_months:
        use.result.reasons.append("Work history does not affect BTO purchase eligibility here, but may affect EHG")
    key = "plus_prime_years" if category in {"Plus", "Prime"} else "standard_years"
    use.result.detail = {"mop_years": use.get(f"mop.{key}"), "hdb_loan_ltv": use.get("loan.hdb_ltv")}
    return use.result


def bto_ehg(profile: BuyerProfile, rules: Rules | None = None) -> RuleResult:
    """Enhanced CPF Housing Grant for a new flat. The income tables are the same ones used for resale."""
    use = RuleUse(rules)
    prefix = "grants.ehg."
    applicant_checks(use, profile)
    first_timer_checks(use, profile)
    property_check(use, profile)
    if use.result.eligible is not True:
        return use.result
    joint = profile.scheme == "single" and profile.buying_with != "alone"
    if joint and profile.own_monthly_income is None:
        use.unknown("own_monthly_income")
        return use.result
    if not profile.works_12_months:
        use.unknown("ehg_work_rule_for_new_flats")
    income = profile.monthly_household_income
    if profile.scheme == "family":
        mixed = profile.family_timers == "one_first"
        income = income * use.get(prefix + "mixed_couple_assessed_income_share") if mixed else income
        ceiling = use.get(prefix + ("mixed_couple_assessed_income_ceiling_half_of_household" if mixed else "families_income_ceiling"))
        tiers = use.get(prefix + ("mixed_couple_tiers_on_half_income" if mixed else "families_tiers"))
    else:
        if profile.buying_with == "family_or_singles":
            use.unknown("ehg_joint_singles_assessment")
        ceiling = use.get(prefix + ("singles_income_ceiling_alone" if not joint
                                    else "singles_income_ceiling_household_with_other_singles_or_parents"))
        income = profile.own_monthly_income if joint else income
        tiers = use.get(prefix + "singles_tiers_alone_or_with_parents")
    if income > ceiling:
        use.deny("Income exceeds the EHG ceiling")
        return use.result
    use.result.amount = next((band["amount"] for band in tiers if income <= band["up_to"]), 0)
    use.result.needs_check.append("ehg_pro_rating_for_short_lease")
    return use.result
