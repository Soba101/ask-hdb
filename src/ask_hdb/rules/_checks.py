"""Shared checks keep grant and purchase decisions separate."""

from .loader import Rules, load_rules
from .profile import BuyerProfile, Flat
from .result import RuleResult


class RuleUse:
    def __init__(self, rules: Rules | None = None, result: RuleResult | None = None):
        self.rules = rules if rules is not None else load_rules()
        self.result = result if result is not None else RuleResult(eligible=True)

    def get(self, path: str):
        value = self.rules.get(path)
        citation = self.rules.cite(path)
        if citation not in self.result.rules:
            self.result.rules.append(citation)
        return value

    def deny(self, reason: str):
        self.result.eligible = False
        self.result.amount = 0
        self.result.reasons.append(reason)

    def unknown(self, check: str):
        if self.result.eligible is not False:
            self.result.eligible = None
        self.result.needs_check.append(check)


def applicant_checks(use: RuleUse, profile: BuyerProfile, *, purchase=False):
    """Grant tables cover citizen/permanent-resident couples; purchase scope is narrower."""
    if profile.scheme == "family":
        use.get("eligibility.families.citizenship_min")
        minimum = use.get("eligibility.families.min_age_years")
        if "foreigner" in profile.citizenships:
            use.unknown("foreigner_not_supported_v1")
        if "SPR" in profile.citizenships and purchase:
            use.unknown("spr_not_supported_v1")
        elif "SC" not in profile.citizenships and "foreigner" not in profile.citizenships:
            use.deny("A citizen applicant is required")
    else:
        use.get("eligibility.singles.citizenship")
        age_key = (
            "min_age_years_widowed_or_orphan"
            if profile.marital_status == "widowed"
            else "min_age_years_unmarried_or_divorced"
        )
        minimum = use.get(f"eligibility.singles.{age_key}")
        if any(c != "SC" for c in profile.citizenships):
            use.deny("The singles scheme requires citizen applicants")
        if profile.marital_status == "married":
            use.deny("A married applicant needs a family scheme assessment")
        if profile.marital_status is None and min(profile.ages) < minimum:
            widow_minimum = use.get("eligibility.singles.min_age_years_widowed_or_orphan")
            if min(profile.ages) >= widow_minimum:
                use.unknown("marital_status")
                return
    if min(profile.ages) < minimum:
        use.deny("An applicant is below the minimum age")


def first_timer_checks(use: RuleUse, profile: BuyerProfile):
    if profile.scheme == "family":
        if profile.family_timers is None:
            use.unknown("family_timers")
        elif profile.family_timers == "none_first":
            use.deny("No first-timer applicant")
    else:
        use.get("eligibility.singles.only_first_timer_may_get_grants")
        if profile.first_timer is None:
            use.unknown("first_timer")
        elif not profile.first_timer:
            use.deny("A first-timer applicant is required")


def lease_check(use: RuleUse, flat: Flat, path: str):
    if flat.lease_left_months <= use.get(path) * 12:
        use.deny("The remaining lease must exceed the minimum")


def property_check(use: RuleUse, profile: BuyerProfile):
    if profile.owns_private_property:
        use.get(
            "eligibility.families.private_residential_property_owned_or_interest_with_grant_or_hdb_loan"
        )
        use.deny("Private property ownership prevents grants or an HDB loan")


def income_key(profile: BuyerProfile, *, loan=False) -> str:
    if loan:
        suffix = (
            "singles"
            if profile.scheme == "single"
            else "extended_families"
            if profile.extended_family
            else "families"
        )
        return f"loan.income_ceiling_{suffix}"
    if profile.scheme == "family":
        suffix = "income_ceiling_extended_family" if profile.extended_family else "income_ceiling"
    else:
        suffix = (
            "singles_income_ceiling_alone"
            if profile.buying_with == "alone"
            else "singles_income_ceiling_with_family_or_other_singles"
        )
    return f"grants.cpf_family.{suffix}"
