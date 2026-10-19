"""Purchase eligibility is separate from access to grants and loans."""

from ._checks import RuleUse, applicant_checks, income_key
from .loader import Rules
from .profile import BuyerProfile, Flat
from .result import RuleResult


def can_buy_resale(profile: BuyerProfile, flat: Flat, rules: Rules | None = None) -> RuleResult:
    use = RuleUse(rules)
    applicant_checks(use, profile, purchase=True)
    above_ceiling = False
    for label, loan in (("CPF grant", False), ("HDB loan", True)):
        within = profile.monthly_household_income <= use.get(income_key(profile, loan=loan))
        above_ceiling |= not within
        use.result.reasons.append(
            f"Income is {'within' if within else 'above'} the {label} ceiling"
        )
    if profile.scheme == "family":
        use.get(
            "eligibility.families.resale_unclassified_standard_no_grant_no_hdb_loan_income_ceiling"
        )
        use.get("eligibility.families.previous_housing_subsidy_affects_resale_purchase")
    else:
        use.get("eligibility.singles.resale_unclassified_standard_income_ceiling")
        room_limit = use.get("eligibility.singles.max_flat_room_with_grants")
        if flat.room > room_limit:
            use.result.reasons.append("Flat exceeds the singles grant room limit")
    if flat.category == "standard":
        use.result.reasons.append("Purchase itself has no income ceiling for a Standard resale flat")
    elif flat.category is None and above_ceiling:
        use.unknown("flat_category")
    if profile.owns_private_property:
        use.get(
            "eligibility.families.private_residential_property_owned_or_interest_with_grant_or_hdb_loan"
        )
        use.result.reasons.append("Private property ownership prevents grants or an HDB loan")
    if flat.category in {"plus", "prime"}:
        # The snapshot has no project-specific resale ceiling table.
        use.unknown(f"{flat.category}_resale_project_ceiling")
        if flat.room == use.get("eligibility.families.plus_prime_project_ceiling_room"):
            use.result.needs_check.append(f"{flat.category}_{flat.room}room_project_ceiling")
    return use.result
