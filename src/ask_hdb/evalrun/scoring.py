"""Small answer checks; no model judges or changes to the agent."""

import json
import math
import re

# Commas, decimal prices and common scale suffixes are answer numbers too.
NUMBER = re.compile(r'(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?'
                    r'\s*(?:million\b|thousand\b|[km]\b)?', re.IGNORECASE)
DECLINES = (
    "cannot", "can't", "unable", "not able", "out of scope", "outside", "don't predict",
    "do not predict", "can't predict", "cannot predict", "not supported", "need more",
    "please provide", "could you provide", "please share", "what is your", "what are your",
    "could you share", "need your", "missing", "do not provide", "don't provide",
)


def numbers(text):
    values = []
    for match in NUMBER.finditer(str(text)):
        raw = match.group().strip().lower().replace(',', '')
        scale = 1
        for suffix, multiplier in [('million', 1000000), ('thousand', 1000),
                                   ('k', 1000), ('m', 1000000)]:
            if raw.endswith(suffix):
                raw, scale = raw[:-len(suffix)].strip(), multiplier
                break
        values.append(float(raw) * scale)
    return values


def _near(a, b, tolerance=0):
    return math.isclose(a, b, rel_tol=0, abs_tol=tolerance)


def _keyword(text, keyword):
    return bool(re.search(r'(?<!\w)' + re.escape(keyword) + r'(?!\w)', text, re.IGNORECASE))


def answer_passes(question, result):
    if result.get('error') or result.get('stopped_reason'):
        return False
    expect, answer = question['expect'], result['answer']
    calls = result.get('tool_calls', [])
    if 'number' in expect:
        return any(_near(value, expect['number'], expect['tolerance']) for value in numbers(answer))
    if 'verdict' in expect:
        positive = expect['verdict'] == 'yes'
        # A denial must not satisfy an affirmative "eligible" keyword. Other clauses
        # may still say "not eligible for a grant" after a valid purchase verdict.
        denials = r"\b(?:not eligible|ineligible|cannot buy|can't buy|not able to buy)\b"
        negative = bool(re.search(denials + r'|(?:^|[.!?]\s*)no\b',
                                  answer, re.IGNORECASE))
        prose_text = re.sub(denials, '', answer, flags=re.IGNORECASE) if positive else answer
        prose = any(_keyword(prose_text, key) for key in expect['answer_keywords'])
        if positive and re.search(r'^\s*no\s*[,!.]', answer, re.IGNORECASE):
            prose = False
        if not positive and not negative:
            prose = False
        if calls:
            # Evidence must be an actual verdict, not a truthy string or tool argument.
            verdicts = [call.get('result', {}).get('eligible') for call in calls
                        if isinstance(call.get('result'), dict)]
            prose = prose and any(v is positive for v in verdicts)
        return bool(prose)
    return not calls and any(_keyword(answer, phrase) for phrase in DECLINES)


def grounding(question, result):
    # Question echoes are explicitly excluded. Only current tool results count as evidence.
    given = numbers(question['question'])
    claimed = [n for n in numbers(result['answer']) if not any(_near(n, g) for g in given)]
    evidence = numbers(json.dumps([c.get('result') for c in result.get('tool_calls', [])]))
    supported = sum(any(_near(n, e) for e in evidence) for n in claimed)
    return {'supported': supported, 'total': len(claimed),
            'rate': supported / len(claimed) if claimed else 1.0}


def score(question, result):
    return {'passed': answer_passes(question, result), 'grounding': grounding(question, result)}
