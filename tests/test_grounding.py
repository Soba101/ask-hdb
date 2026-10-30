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
    ("Sales from October 2025 to September 2026: 57.", [{"window": "2025-10..2026-09", "n": 57}]),
    ("In 2025 the median was $500,000.", [{"period": "2025-01..2025-12", "median": 500000}]),
    ("12 sales.", [{"n": "12"}]),  # a whole-number string
    ("Revised from 24 Aug 2026.", [{"value": "2026-08-24"}]),
    ("Revised from August 24, 2026.", [{"value": "2026-08-24"}]),
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
    # Digits inside labels, dates, citations and sentences are not evidence.
    ("$314.", [{"block_id": "blk_314_ang-mo-kio-ave-3"}]),
    ("Rule 2026 applies.", [{"as_of": "2026-10-20"}]),
    ("$12.", [{"id": "loan.rule_12"}]),
    ("The ceiling is $16,000.", [{"reasons": ["Income is above the ceiling of 16000"]}]),
    ("It is 20 years.", [{"value": "2026-10-20"}]),
    ("Revised from 25 Aug 2026.", [{"value": "2026-08-24"}]),
])
def test_unsupported_numbers_are_caught(answer, results):
    assert bad(answer, results)


def test_arguments_and_booleans_are_not_evidence():
    # True would otherwise count as 1.
    assert bad("1 grant.", [{"eligible": True}]) == ["1"]


def test_question_echoes_are_left_out():
    result = check("At $600,000 you are 35.", "Flat $600000, age 35?", [])
    assert result == {"numbers": [], "ungrounded": []}


@pytest.mark.parametrize("answer", ["The minimum age is 35.", "You must be at least 35.",
                                    "The income ceiling is $4,000."])
def test_question_numbers_are_not_rule_thresholds(answer):
    # The user said 35 and $4000; that does not make either one HDB's threshold.
    assert check(answer, "I am 35, income $4000. Can I buy?", [])["ungrounded"]


@pytest.mark.parametrize("text", [
    "1. Price\n2) Lease\n- 3. Age\n**4.** Income",  # list labels
    "In 2025, sales rose.", "Since 1990.", "As of 2026-10-20.", "In September 2026.",  # years and dates
    "A 4-room or 3 ROOM flat.", "Your 1st and 21st sale.", "See blk_12_tampines-st-1.",
    "Blk 314 Ang Mo Kio Ave 3.", "Block 648A Jurong West St 61.",  # addresses
])
def test_labels_are_not_claims(text):
    assert claims(text) == []


@pytest.mark.parametrize("text", ["$2025 a month", "2025 dollars", "income 2000/month",
                                  "2,025", "2025.5", "2025%",
                                  "Your monthly instalment is 2050.", "Income of SGD 2000",
                                  "The price in 2025 was 2050.", "Sales rose 2030 times."])
def test_amounts_that_look_like_years_are_claims(text):
    assert claims(text)


def test_cannot_answer_is_not_a_decline_or_clarification():
    # The fallback must never pass a refuse question by accident.
    text = CANNOT_ANSWER.lower()
    assert not any(phrase.lower() in text for phrase in DECLINES + CLARIFIES)
    assert claims(CANNOT_ANSWER) == []


def test_comparing_the_users_number_to_a_ceiling_is_an_echo():
    # From the week 5-2 eval (q_eligibility_005): the user's income in brackets after "ceiling".
    answer = "Income is within the ceiling ($4000 < $8000). The ceiling is $8000 (your income is $4000)."
    assert check(answer, "income $4000 monthly", [{"value": 8000}])["ungrounded"] == []


def test_the_3gen_flat_type_is_a_label_not_a_number():
    assert check("The Tengah project offers 3Gen and 4-room flats.", "", [{"flat_types": ["3Gen", "4-room"]}])["ungrounded"] == []
    assert check("It has 3 sales.", "", [{"n": 4}])["ungrounded"] == ["3"]
