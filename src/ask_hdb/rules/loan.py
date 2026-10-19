"""Size an HDB loan from the payment and price caps."""

import math

from ._checks import RuleUse, applicant_checks, income_key, lease_check, property_check
from .loader import Rules
from .profile import BuyerProfile, Flat
from .result import RuleResult


def max_loan(
    profile: BuyerProfile,
    flat: Flat,
    qualifying_rate_pct: float | None = None,
    rules: Rules | None = None,
) -> RuleResult:
    if qualifying_rate_pct is not None and (
        not math.isfinite(qualifying_rate_pct) or qualifying_rate_pct < 0
    ):
        raise ValueError("qualifying_rate_pct must be finite and nonnegative")
    use = RuleUse(rules)
    applicant_checks(use, profile)
    use.get("loan.eligibility_citizenship")
    property_check(use, profile)
    if profile.previous_hdb_loans >= use.get(
        "loan.max_previous_hdb_loans_in_core_nucleus_exclusive"
    ):
        use.deny("Too many previous HDB loans")
    if profile.monthly_household_income > use.get(income_key(profile, loan=True)):
        use.deny("Income exceeds the HDB loan ceiling")
    if profile.scheme == "single":
        if min(profile.ages) < use.get("loan.singles_min_age_years"):
            use.deny("Applicant is below the HDB loan minimum age")
        if flat.room > use.get("loan.singles_max_resale_room"):
            use.deny("Flat exceeds the HDB loan room limit")
    lease_check(use, flat, "loan.min_remaining_lease_years_exclusive")
    if use.result.eligible is not True:
        return use.result
    payment = profile.monthly_household_income * use.get("loan.msr_pct_of_monthly_income") / 100
    # Calculate in months first so a partial year never becomes an extra payment.
    average_age = sum(profile.ages) / len(profile.ages)
    months = math.floor(
        min(
            use.get("loan.max_tenure_years") * 12,
            (use.get("loan.tenure_cap_age_minus_avg_age") - average_age) * 12,
            flat.lease_left_months - use.get("loan.tenure_cap_remaining_lease_minus_years") * 12,
        )
    )
    rate_pct = max(use.get("loan.qualifying_rate_floor_pct"), qualifying_rate_pct or 0)
    rate = rate_pct / 100 / 12
    use.result.detail = {
        "monthly_payment_cap": payment,
        "tenure_years": max(0, months) / 12,
        "rate_pct": rate_pct,
    }
    if months <= 0:
        use.deny("No positive loan tenure remains")
        return use.result
    present_value = (
        payment * (-math.expm1(-months * math.log1p(rate))) / rate if rate else (payment * months)
    )
    bound = "msr"
    if flat.price is None:
        use.result.needs_check.append("ltv_not_applied")
    else:
        # Valuation can reduce the base below the supplied purchase price.
        use.result.needs_check.append("ltv_valuation_not_modelled")
        price_cap = flat.price * use.get("loan.ltv_max_pct") / 100
        if price_cap < present_value:
            present_value, bound = price_cap, "ltv"
    use.result.amount = math.floor(present_value)
    use.result.detail["binding_cap"] = bound
    use.result.reasons.append(f"The {bound.upper()} cap binds the estimate")
    cover_age = use.get("loan.ltv_pro_rated_if_lease_covers_youngest_to_age_below")
    if min(profile.ages) * 12 + flat.lease_left_months < cover_age * 12:
        use.result.needs_check.append("ltv_pro_rating")
        use.result.reasons.append("LTV uses the full limit before an unpublished lease reduction")
    return use.result
