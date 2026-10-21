"""Grounding rules: formatting variants match, approximations and memory do not."""

import pytest

from ask_hdb.evalrun.scoring import CLARIFIES, DECLINES
from ask_hdb.grounding import CANNOT_ANSWER, check, claims


def bad(answer, results, question=""):
    return check(answer, question, results)["ungrounded"]


@pytest.mark.parametrize("answer,results", [
    ("Median **$1,531**.", [{"median": 1531}]),
    ("Median $1531.", [{"median": 1531.0}]),
    ("It is 4.8% below.", [{"pct_vs_median": -4.8}]),
    ("$20,000 below the median.", [{"diff": -20000}]),
    ("$1.2 million.", [{"price": 1200000}]),
    ("$500k.", [{"median": 500000}]),
    ("0.09 km away.", [{"km": 0.09063643749715133}]),
    ("4.80%", [{"rate": 4.8}]),
    ("Window 2025-10..2026-09, 57 sales.", [{"window": "2025-10..2026-09", "n": 57}]),
    ("Blk 314 Ang Mo Kio Ave 3.", [{"block_id": "blk_314_ang-mo-kio-ave-3"}]),
])
def test_formatting_variants_are_grounded(answer, results):
    assert bad(answer, results) == []


@pytest.mark.parametrize("answer,results", [
    ("About 1.5k.", [{"n": 1531}]),           # scaled numbers never round
    ("About $420,000.", [{"median": 419876}]),  # whole numbers never round
    ("0.1 km away.", [{"km": 0.16}]),          # rounding must be correct
    ("0.090 km away.", [{"km": 0.0906}]),      # three decimals is not 0.0906
    ("Minimum age 35.", [{"eligible": True}]),  # a rule threshold from memory
    ("You get $20000.", [{"error": "Missing: room 20000"}]),  # errors are not evidence
    ("Total 1e+06.", []),
])
def test_unsupported_numbers_are_caught(answer, results):
    assert bad(answer, results)


def test_arguments_and_booleans_are_not_evidence():
    # True would otherwise count as 1.
    assert bad("1 grant.", [{"eligible": True}]) == ["1"]


def test_question_echoes_are_left_out():
    result = check("At $600,000 you are 35.", "Flat $600000, age 35?", [])
    assert result == {"numbers": [], "ungrounded": []}


@pytest.mark.parametrize("text", [
    "1. Price\n2) Lease\n- 3. Age\n**4.** Income",  # list labels
    "In 2025, sales rose.", "Since 1990.", "As of 2026-10-20.",  # years and dates
    "A 4-room or 3 ROOM flat.", "Your 1st and 21st sale.", "See blk_12_tampines-st-1.",
])
def test_labels_are_not_claims(text):
    assert claims(text) == []


@pytest.mark.parametrize("text", ["$2025 a month", "2025 dollars", "income 2000/month",
                                  "2,025", "2025.5", "2025%"])
def test_amounts_that_look_like_years_are_claims(text):
    assert claims(text)


def test_cannot_answer_is_not_a_decline_or_clarification():
    # The fallback must never pass a refuse question by accident.
    text = CANNOT_ANSWER.lower()
    assert not any(phrase.lower() in text for phrase in DECLINES + CLARIFIES)
    assert claims(CANNOT_ANSWER) == []
