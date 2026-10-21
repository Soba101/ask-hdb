"""Small answer checks; no model judges or changes to the agent."""

import json
import re
from decimal import Decimal

# Only explicit price scales count; metre and kilometre units never scale values.
NUMBER = re.compile(r'(?<![\w.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?'
                    r'\s*(?:million\b|k\b)?', re.IGNORECASE)
DECLINES = (
    'cannot predict', "can't predict", 'cannot advise', "can't advise", 'unable to predict',
    'outside my scope', 'only help with resale', 'do not answer BTO', 'not able to predict',
    'can only help with', 'can only assist with', 'cannot provide investment',
    'cannot provide information on how to apply',
)
CLARIFIES = ('please provide', 'what is your', 'what are your', 'need your', 'tell me',
             'could you share', 'could you provide', 'please share')
DENIAL = r"\b(?:not eligible|ineligible|cannot buy|can't buy|not able to buy)\b"
BENEFIT = r'\b(?:grants?|loans?|EHG|CPF)\b'


def numbers(text):
    # Ignore ordered-list labels, including labels nested under a bullet.
    text = re.sub(r'^\s*(?:[-*+•]\s+)?\d+[.)]\s+', '', str(text), flags=re.MULTILINE)
    values = []
    for match in NUMBER.finditer(text):
        raw = match.group().strip().lower().replace(',', '')
        scale = 1
        for suffix, multiplier in [('million', 1000000), ('k', 1000)]:
            if raw.endswith(suffix):
                raw, scale = raw[:-len(suffix)].strip(), multiplier
                break
        values.append(float(raw) * scale)
    return values


def _near(a, b, tolerance=0):
    # Decimal subtraction keeps an inclusive decimal boundary inclusive.
    return abs(Decimal(str(a)) - Decimal(str(b))) <= Decimal(str(tolerance))


def _without_question_ids(text, question):
    # A stable block ID is a label, not a numeric answer.
    ids = set(re.findall(r'\bblk_[\w-]+\b', question))
    return re.sub(r'\bblk_[\w-]+\b', lambda m: '' if m[0] in ids else m[0], text)


def _keyword(text, keyword):
    return bool(re.search(r'(?<!\w)' + re.escape(keyword) + r'(?!\w)', text, re.IGNORECASE))


def _purchase_denial(answer):
    if re.search(r'^\s*no\s*[,!.]', answer, re.IGNORECASE):
        return True
    # Scope each denial locally: a grant denial in another clause cannot excuse a
    # purchase denial. Explicit buying language always describes purchase eligibility.
    for clause in re.split(r'[.!?;\n]|\bbut\b|\band\b', answer, flags=re.IGNORECASE):
        for denial in re.finditer(DENIAL, clause, re.IGNORECASE):
            tail = clause[denial.start():]
            scope = re.match(r'\s+(?:for|to receive|to get)\b[^,.!?;]*',
                             clause[denial.end():], re.IGNORECASE)
            if (re.search(r'\bbuy\b', tail, re.IGNORECASE)
                    or not scope or not re.search(BENEFIT, scope.group(), re.IGNORECASE)):
                return True
    return False


def answer_passes(question, result):
    if result.get('error') or result.get('stopped_reason'):
        return False
    expect = question['expect']
    answer = re.sub(r'[*_`]', '', result['answer'])
    calls = result.get('tool_calls', [])
    if 'number' in expect:
        text = question['question']
        given = numbers(_without_question_ids(text, text))
        values = [n for n in numbers(_without_question_ids(result['answer'], text))
                  if not any(_near(n, g) for g in given)]
        # Small numbers (counts, list items) cannot be a price or amount, so skip them
        # when the expected answer is 10,000 or more.
        if abs(expect['number']) >= 10000:
            # Years (a window like 2025-10) are not amounts either.
            values = [n for n in values if abs(n) >= 1000 and not 1900 <= n <= 2100]
        # The first non-question number must match, even if a later bold answer matches.
        if values and _near(values[0], expect['number'], expect['tolerance']):
            return True
        # A worked line like "638888 - 590000 = 48888" gives its result after the last "=".
        tail = numbers(_without_question_ids(result['answer'].rsplit('=', 1)[1], text)
                       ) if '=' in result['answer'] else []
        return bool(tail) and _near(tail[0], expect['number'], expect['tolerance'])
    if 'verdict' in expect:
        positive = expect['verdict'] == 'yes'
        negative = _purchase_denial(answer)
        prose = any(_keyword(answer, key) for key in expect['answer_keywords'])
        prose = prose and (not negative if positive else negative)
        if calls:
            # Grant tools also return eligible; only purchase verdicts are evidence here.
            verdicts = [call['result'].get('eligible') for call in calls
                        if call.get('name') in {'can_buy_resale', 'can_apply_bto'}
                        and isinstance(call.get('result'), dict)]
            prose = prose and any(v is positive for v in verdicts)
        return bool(prose)
    if expect.get('clarify'):
        # A clarifying question may mention small numbers (12 months, 4-room); amounts are 1,000+.
        verdict = re.search(DENIAL + r'|\beligible\b|\bcan buy\b|^\s*(?:yes|no)\b',
                            answer, re.IGNORECASE)
        tool_verdict = any(isinstance(c.get('result'), dict)
                           and isinstance(c['result'].get('eligible'), bool) for c in calls)
        return (any(_keyword(answer, phrase) for phrase in CLARIFIES)
                and not verdict and not any(n >= 1000 for n in numbers(result['answer']))
                and not tool_verdict)
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
