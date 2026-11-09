"""Readable profile lines that can be checked against their raw, canonical values."""

import re
from decimal import Decimal

LABELS = {
    "ages": "Ages (years)",
    "lease_left_months": "Lease remaining (months)",
    "previous_hdb_loans": "Previous HDB loans taken",
    "room": "Flat rooms",
    "price": "Flat price",
    "works_12_months": "Worked continuously for the past 12 months",
}
VALUES = {
    "family_timers": {"both_first": "both first-timers", "one_first": "one first-timer",
                      "none_first": "neither applicant is a first-timer"},
    "scheme": {"family": "family scheme", "single": "singles scheme"},
    "buying_with": {"parents": "with parents", "family_or_singles": "with family or other singles"},
    "category": {"standard": "Standard", "plus": "Plus", "prime": "Prime"},
    "relation": {"with": "living with parents or child", "near": "living near parents or child"},
}
CITIZENSHIPS = {"SC": "Singapore citizen", "SPR": "Singapore permanent resident", "foreigner": "foreigner"}
CHECK = " (you did not give this: please check)"
# Match whole numeric tokens, so an income cannot supply a missing age or loan count.
NUMBER = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?(?!\w|\.\d)")


def label(key):
    return LABELS.get(key, key.replace("_", " ").capitalize())


def readable(key, raw):
    """Keep the exact tool value in brackets whenever the words differ."""
    words = VALUES.get(key, {}).get(raw, raw)
    if key == "citizenships":
        words = ", ".join(CITIZENSHIPS.get(part.strip(), part.strip()) for part in raw.split(","))
    return f"{words} ({raw})" if words != raw else raw


def numbers(text):
    return {Decimal(match.group().replace(",", "")) for match in NUMBER.finditer(text)}


def missing_number(key, value, user_numbers):
    # Booleans and enums describe choices, even when their labels contain digits.
    if isinstance(value, bool):
        return False
    if key == "ages":
        # Applicant ages are separate numbers, never a thousands-grouped amount.
        values = numbers(str(value).replace(",", " "))
    elif isinstance(value, (int, float)) or NUMBER.fullmatch(str(value)):
        values = {Decimal(str(value).replace(",", ""))}
    else:
        return False
    return not values <= user_numbers


def canonical_line(line):
    """Rebuild a raw line only if all its readable words match that raw value."""
    if not line.startswith("- ") or ": " not in line:
        return None
    shown_label, value = line[2:].split(": ", 1)
    key = next((key for key, words in LABELS.items() if words == shown_label),
               shown_label.lower().replace(" ", "_"))
    if shown_label != label(key):
        return None
    value = value.removesuffix(CHECK)
    raw = value
    if value.endswith(")") and " (" in value:
        raw = value.rsplit(" (", 1)[1][:-1]
    # Checking both parts prevents a changed friendly label from hiding an unchanged raw value.
    if readable(key, raw) != value:
        return None
    return f"- {key.replace('_', ' ').capitalize()}: {raw}"
