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


NOT = re.compile(r"\b(?:no|not|never|none|neither|nor|without|non)\b|n't\b", re.IGNORECASE)
# Words that support one value of a choice. A value with no entry here must appear in the user's words as written.
SAID = {
    "scheme": {"family": r"famil|married|couple|spouse|husband|wife|fianc", "single": r"single|alone|unmarried|divorced|widowed|by myself|on my own"},
    "family_timers": {"both_first": r"both\b.{0,25}first[- ]?timer|first[- ]?timers", "one_first": r"\bone\b.{0,25}first[- ]?timer",
                      "none_first": r"neither\b.{0,25}first|second[- ]?timers"},
    "first_timer": {"yes": r"first[- ]?timer", "no": r"second[- ]?timer"},
    "marital_status": {"married": r"\bmarried|husband|wife|spouse", "unmarried": r"unmarried|never married|\bsingle\b",
                       "divorced": r"divorc", "widowed": r"widow"},
    "buying_with": {"alone": r"\balone\b|by myself|on my own", "parents": r"parent|mother|father|\bmum\b|\bdad\b",
                    "family_or_singles": r"famil|sibling|brother|sister|friend|singles"},
    "relation": {"with": r"\bwith (?:my |our )?(?:parent|child|mother|father)", "near": r"\bnear (?:my |our )?(?:parent|child|mother|father)"},
}
CITIZEN = {"SC": r"\bsc\b|citizen|singaporean", "SPR": r"\bs?pr\b|permanent resident", "foreigner": r"foreign"}
# A yes/no field is supported by its words: without a negation for yes, with one for no.
FACTS = {"works_12_months": r"work|\b(?:un)?employ|\bjob", "owns_private_property": r"private propert|condo|landed|private home|private flat",
         "extended_family": r"extended famil"}


def _hits(pattern, text):
    """For each match, whether a negation sits just before it in the same sentence."""
    for match in re.finditer(pattern, text, re.IGNORECASE):
        before = re.split(r"[.!?;\n]", text[max(0, match.start() - 25):match.start()])[-1]
        yield bool(NOT.search(before)) or match.group().lower().startswith("unemploy")  # "unemployed" is a no


def unsupported(key, value, user_words):
    """True when the user's words do not back this value. Over-flagging is the safe side: the user just checks it."""
    if isinstance(value, bool):
        # yes needs a plain mention, no needs a negated one; a yes/no field with no word list is always checked.
        return key not in FACTS or (not value) not in set(_hits(FACTS[key], user_words))
    if key == "previous_hdb_loans" and value == 0 and re.search(r"\bno (?:previous |prior |earlier )?hdb loans?\b", user_words, re.IGNORECASE):
        return False
    if key == "lease_left_months":
        return missing_number(key, value, lease_months(user_words))
    if isinstance(value, (int, float)) or NUMBER.fullmatch(str(value)) or key == "ages":
        return missing_number(key, value, numbers(user_words))
    if key == "citizenships":
        return not all(any(not negated for negated in _hits(CITIZEN.get(part.strip(), re.escape(part.strip())), user_words))
                       for part in str(value).split(","))
    pattern = SAID.get(key, {}).get(value)
    if pattern is None:
        plain = lambda text: re.sub(r"[^a-z0-9]", "", str(text).lower())
        return plain(value) not in plain(user_words)
    return not any(not negated for negated in _hits(pattern, user_words))


def numbers(text):
    return {Decimal(match.group().replace(",", "")) for match in NUMBER.finditer(text)}


def lease_months(text):
    """Numbers as months: "70 years" is 840, so a lease the model copied as 70 months is flagged."""
    found = set()
    for match in NUMBER.finditer(text):
        value = Decimal(match.group().replace(",", ""))
        years = re.match(r"\s*-?\s*(?:years?|yrs?)\b", text[match.end():], re.IGNORECASE)
        found.add(value * 12 if years else value)
    return found


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
