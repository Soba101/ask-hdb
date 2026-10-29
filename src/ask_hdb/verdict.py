"""Code check: an answer may not state an eligibility verdict that no tool result supports (issue 11)."""

import re

# Phrases that state an outcome. Questions and "I need X to decide" are not matched.
VERDICT = re.compile(
    r"\b(?:you|they|he|she|we)\s+(?:are|is|can|cannot|can't|qualify|do not qualify|don't qualify|may|are not|aren't)\b[^.?!]{0,40}"
    r"\b(?:eligible|buy|apply|qualify|qualified|purchase)\b"
    r"|\b(?:not eligible|ineligible|is eligible|are eligible|eligible to|not allowed|cannot buy|can buy|cannot apply|can apply)\b",
    re.IGNORECASE)


def open_questions(results):
    """What the last result of each tool with an `eligible` field still needs; empty when every verdict is settled."""
    last = {}
    for name, result in results:
        if isinstance(result, dict) and "eligible" in result:
            last[name] = result
    missing = []
    for result in last.values():
        if result["eligible"] is None:
            missing += [str(item) for item in result.get("needs_check") or []] or ["more details"]
    return missing


def replacement(answer, results):
    """Plain text to show instead of `answer`, or None when the answer may stand."""
    missing = open_questions(results)
    if not missing or not VERDICT.search(answer or ""):
        return None
    return ("I cannot give a yes or no yet, because the rules check is missing information: "
            + "; ".join(dict.fromkeys(missing)) + ". Please tell me these details and I will check again.")
