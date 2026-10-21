"""BTO rules checked against the HDB annex values in rules/bto/2026-10.yaml and the EHG tables."""

import pytest

from ask_hdb import tools
from ask_hdb.rules import BuyerProfile
from ask_hdb.rules.bto import bto_ehg, can_apply_bto


def family(income, timers="both_first", **kw):
    return BuyerProfile(scheme="family", citizenships=["SC", "SC"], ages=[32, 31], monthly_household_income=income,
                        family_timers=timers, **kw)


def single(income, age=35, **kw):
    return BuyerProfile(scheme="single", citizenships=["SC"], ages=[age], monthly_household_income=income,
                        first_timer=True, marital_status="unmarried", **kw)


@pytest.mark.parametrize("income,hfe,eligible", [
    (13000, None, True), (15000, None, None), (15000, True, True), (15000, False, False), (17000, None, False)])
def test_family_income_ceiling_depends_on_the_hfe_date(income, hfe, eligible):
    result = can_apply_bto(family(income), "Standard", "4-room", hfe)
    assert result.eligible is eligible
    assert ("hfe_application_date" in result.needs_check) is (income == 15000 and hfe is None)


def test_flexi_ceiling_extended_family_and_cited_sources():
    assert can_apply_bto(family(7500), "Standard", "2-room Flexi", True).eligible is True
    assert can_apply_bto(family(7500), "Standard", "2-room Flexi", False).eligible is False
    assert can_apply_bto(family(23000, extended_family=True), "Standard", "4-room", True).needs_check == ["each_family_nucleus_income_cap"]
    result = can_apply_bto(family(5000), "Prime", "4-room", True)
    assert result.detail == {"mop_years": 10, "hdb_loan_ltv": 0.75}
    assert all(r["source"].startswith("https://www.hdb.gov.sg/") for r in result.rules)
    assert can_apply_bto(family(5000), "Standard", "4-room", True).detail["mop_years"] == 5


def test_singles_can_only_buy_flexi_and_second_timers_are_flagged_not_decided():
    assert can_apply_bto(single(3000), "Standard", "4-room", True).eligible is False
    assert can_apply_bto(single(3000), "Standard", "2-room Flexi", True).eligible is True
    assert can_apply_bto(single(3000, age=30), "Standard", "2-room Flexi", True).eligible is False
    second = can_apply_bto(family(4000, "none_first"), "Standard", "4-room", True)
    assert second.eligible is None and "second_timer_flat_types_and_quota" in second.needs_check


@pytest.mark.parametrize("profile,amount", [
    (family(4400), 70000), (family(1400), 120000), (family(9000), 5000), (family(4400, "one_first"), 35000), (single(2000), 40000)])
def test_ehg_matches_the_hdb_tables(profile, amount):
    assert bto_ehg(profile).amount == amount


def test_ehg_denials_and_flags():
    assert bto_ehg(family(9500)).eligible is False
    assert bto_ehg(family(4000, "none_first")).eligible is False
    result = bto_ehg(family(4000, works_12_months=False))
    assert result.eligible is None and "ehg_work_rule_for_new_flats" in result.needs_check


def test_tools_accept_the_buyer_fields_only():
    base = {"scheme": "family", "citizenships": "SC,SC", "ages": "32,31", "monthly_household_income": 4400,
            "family_timers": "both_first", "first_timer": "not_applicable", "marital_status": "married",
            "previous_hdb_loans": 0, "works_12_months": True, "owns_private_property": False}
    result = tools.bto_ehg_amount.invoke(base)
    assert result["amount"] == 70000 and result["rules"]
    bto = tools.can_apply_bto.invoke(base | {"category": "Plus", "flat_type": "4-room", "hfe_after_revision": None})
    assert bto["eligible"] is True and bto["detail"]["mop_years"] == 10
    assert "hfe_after_revision" in tools.can_apply_bto.invoke(base | {"category": "Plus", "flat_type": "4-room"})["error"]
