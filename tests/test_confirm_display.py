"""Readable confirmation text must preserve the exact profile's consent boundary."""

import hashlib

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from ask_hdb import confirm, tools
from ask_hdb.check_cases import PROFILE
from ask_hdb.confirm_display import CHECK

QUESTION = "Can a couple earning $6200 a month, both first-timers, get the EHG?"
EXAMPLE = {"scheme": "family", "citizenships": "SC,SC", "ages": "30,30",
           "monthly_household_income": 6200, "family_timers": "both_first",
           "first_timer": "not_applicable", "marital_status": "married", "previous_hdb_loans": 0,
           "works_12_months": True, "owns_private_property": False, "buying_with": "alone",
           "extended_family": False, "room": 4, "lease_left_months": 600}


def test_example_is_readable_and_marks_only_unsupplied_numbers():
    text = confirm.question_text(EXAMPLE, QUESTION)
    assert f"- Ages (years): 30,30{CHECK}" in text
    assert "- Citizenships: Singapore citizen, Singapore citizen (SC,SC)\n" in text
    assert "- Family timers: both first-timers (both_first)\n" in text
    assert f"- Lease remaining (months): 600{CHECK}" in text
    assert "- Monthly household income: $6,200\n" in text
    assert f"- Previous HDB loans taken: 0{CHECK}" in text
    assert f"- Flat rooms: 4{CHECK}" in text
    assert "Buying with:" not in text and "Marital status:" not in text
    assert "- Worked continuously for the past 12 months: yes\n" in text


def test_hash_still_uses_sorted_raw_canonical_lines():
    # Build these independently of the display code to pin the reference format.
    canonical = ("- Ages: 30,30\n- Citizenships: SC,SC\n- Extended family: no\n"
                 "- Family timers: both_first\n- Lease left months: 600\n"
                 "- Monthly household income: $6,200\n- Owns private property: no\n"
                 "- Previous hdb loans: 0\n- Room: 4\n- Scheme: family\n- Works 12 months: yes")
    expected = hashlib.sha256(canonical.encode()).hexdigest()[:8]
    assert confirm.ref(EXAMPLE) == expected
    for words in ("", QUESTION, "Ages 30, lease 600, income 6200, loans 0, room 4"):
        assert confirm._shown_ref(confirm.question_text(EXAMPLE, words)) == expected


@pytest.mark.parametrize("old,new", [
    ("$6,200", "$6,201"), ("30,30", "31, 30 (31,30)"),
    ("both first-timers (both_first)", "one first-timer (one_first)"),
    ("Singapore citizen, Singapore citizen (SC,SC)", "Singapore citizen, Singapore permanent resident (SC,SPR)"),
    ("both first-timers", "one first-timer"), ("(both_first)", "(one_first)"),
])
def test_a_copy_with_a_changed_value_fails(old, new):
    text = confirm.question_text(EXAMPLE, QUESTION).replace(old, new)
    assert confirm._shown_ref(text) is None
    history = [HumanMessage(content=QUESTION), AIMessage(content=text)]
    assert confirm.confirmed(history, "yes") == (set(), [])


def test_a_copy_with_an_old_ref_fails():
    text = confirm.question_text(EXAMPLE, QUESTION)
    stale = text.replace(confirm.ref(EXAMPLE), confirm.ref(EXAMPLE | {"monthly_household_income": 6100}))
    assert confirm._shown_ref(stale) is None


@pytest.mark.parametrize("key,value,words", [
    ("ages", "30,31", "Ages 30"), ("monthly_household_income", 6200, "Income 62000"),
    ("lease_left_months", 600, "Lease 1600"), ("price", 600000, "Price 60000"),
    ("previous_hdb_loans", 0, "Income 6200"), ("room", 4, "Income 4400"),
    ("qualifying_rate_pct", 3.5, "Rate 3"), ("other_number", 27, "Number 127"),
])
def test_each_numeric_field_requires_a_whole_matching_number(key, value, words):
    text = confirm.question_text({key: value}, words)
    assert CHECK in text
    assert CHECK not in confirm.question_text({key: value}, str(value).replace(",", ", "))


@pytest.mark.parametrize("words", ["Income $6,200.", "Income $6200", "Income 6200.00"])
def test_income_formats_match_the_same_number(words):
    assert CHECK not in confirm.question_text({"monthly_household_income": 6200}, words)


def test_enums_and_boolean_values_are_not_flagged():
    text = confirm.question_text({"flat_type": "4-room", "works_12_months": True,
                                  "family_timers": "both_first", "citizenships": "SC,SPR,foreigner"})
    assert CHECK not in text
    assert "Singapore citizen, Singapore permanent resident, foreigner (SC,SPR,foreigner)" in text


@pytest.mark.parametrize("key,value", [("first_timer", "yes"), ("marital_status", "divorced"),
                                        ("buying_with", "parents"), ("own_monthly_income", 999)])
def test_family_ignores_only_fields_not_used_by_family_rules(key, value):
    assert confirm.ref(PROFILE | {key: value}) == confirm.ref(PROFILE)
    assert key not in confirm.profile(PROFILE | {key: value})


def test_single_ignores_family_timer_but_keeps_fields_that_can_affect_rules():
    args = PROFILE | {"scheme": "single", "first_timer": "yes", "marital_status": "unmarried",
                      "buying_with": "parents", "own_monthly_income": 2000, "extended_family": False}
    assert confirm.ref(args | {"family_timers": "none_first"}) == confirm.ref(args)
    for key, value in {"first_timer": "no", "marital_status": "widowed", "buying_with": "alone",
                       "own_monthly_income": 2100, "extended_family": True}.items():
        assert confirm.ref(args | {key: value}) != confirm.ref(args)
    assert confirm._shown_ref(confirm.question_text(args)) == confirm.ref(args)


@pytest.mark.parametrize("name", sorted(confirm.GATED))
@pytest.mark.parametrize("scheme", ["family", "single"])
def test_dropped_fields_leave_actual_tool_results_unchanged(name, scheme):
    tool = getattr(tools, name)
    values = PROFILE | {"scheme": scheme, "relation": "near", "flat_type": "4-room",
                        "hfe_after_revision": True}
    if name == "can_apply_bto":
        values["category"] = "Standard"
    if scheme == "single":
        values |= {"first_timer": "yes", "marital_status": "unmarried"}
    args = {key: value for key, value in values.items() if key in tool.args_schema.model_fields}
    ignored = ({"first_timer": "yes", "marital_status": "divorced", "buying_with": "parents",
                "own_monthly_income": 999} if scheme == "family" else {"family_timers": "none_first"})
    result = tool.invoke(args)
    assert "error" not in result
    assert tool.invoke(args | ignored) == result
