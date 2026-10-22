"""Check that every number in an answer comes from this question's tool results.

The LLM talks. Code decides. A number the model writes must be traceable to a tool
result from the same turn, or to the user's own question. Never weaken these rules to
make a test or an eval pass; fix the agent or the tool instead.

Rules, in plain words:
- A number matches when its size is exactly a tool value. Commas, "$", "%" and a sign
  are formatting ("$20,000 below" matches a tool value of -20000).
- "k" and "million" scale a number, and the scaled value must match exactly
  ("$1.2 million" matches 1200000; "1.5k" does not match 1531).
- A number written with decimals may be the tool value rounded half-up to that many
  decimals ("0.09" km matches 0.0906). Whole numbers and scaled numbers never round.
- A date with a day ("24 Aug 2026") must be an ISO date in a tool result or the question.
- Labels are not claims and are skipped: block IDs (blk_...), addresses ("Blk 314",
  "Ave 3"), ISO dates and months (2025-10), ordinals under 100 (1st, 21st), flat types
  (4-room, 3 ROOM), list labels ("1.") and years 1960-2100 that follow a date word
  (in, since, as of, from, until, a month name) with no money word nearby.
- Evidence is numeric values, whole-number strings, and the years and months of window
  strings ("2025-10..2026-09"). Digits inside other strings (sentences, IDs, sources,
  as_of dates, URLs) are not evidence. Results with an "error" key and tool arguments are not.
- Numbers the user wrote in the question may be restated, but not right after a threshold
  word ("minimum", "at least", "ceiling", "limit"...): the user's 35 is not HDB's minimum age.
  Known limit: other phrasings can still present a question number as a rule.
"""

import math
import re
from decimal import ROUND_HALF_UP, Decimal

CANNOT_ANSWER = (
    "I can't answer this reliably. My draft answer used numbers that I could not trace "
    "to a tool result, so I have not shown it. Try a narrower question."
)

# Optional sign and $, thousands commas, decimals, then an explicit k or million scale.
NUMBER = re.compile(r'(?<![\w.])(-?)\$?(\d+(?:,\d{3})*)(\.\d+)?(\s*(?:million\b|k\b))?',
                    re.IGNORECASE)
MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
MONTH = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?'
DAY_DATES = [re.compile(r'\b(?P<d>\d{1,2})\s+' + MONTH + r',?\s+(?P<y>(?:19|20)\d{2})\b', re.IGNORECASE),
             re.compile(r'\b' + MONTH + r'\s+(?P<d>\d{1,2}),?\s+(?P<y>(?:19|20)\d{2})\b', re.IGNORECASE)]
YEAR = re.compile(r'\b(?:in|since|as of|from|until|till|during|' + MONTH + r')\s+(?:19[6-9]\d|20\d{2}|2100)\b'
                  r'(?!\d|,\d|%|\.\d)', re.IGNORECASE)
MONEY = re.compile(r'\$|\b(?:sgd|dollars?|instal+ments?|income|salary|price|cost|loan|grant|'
                   r'pay|paid|per month|a month|monthly)\b', re.IGNORECASE)
LABELS = [
    r'\bblk_[\w-]+',                                  # stable block IDs
    r'\b(?:blk|block)\s+\d+[a-z]?\b',                  # "Blk 314", "Block 648A"
    r'\b(?:ave|avenue|st|street|rd|road|dr|drive|cres|crescent|lane|sector|central)\s+\d+[a-z]?\b',
    r'\b(?:19|20)\d{2}-\d{2}(?:-\d{2})?\b',            # ISO dates and months
    r'\b\d{1,2}(?:st|nd|rd|th)\b',                     # ordinals
    r'\b[1-5][\s-]?room\b',                            # flat types
]
LIST_LABEL = re.compile(r'^\s*(?:[-*+•]\s+)?\d+[.)]\s+', re.MULTILINE)
THRESHOLD = re.compile(r'(?:minimum|maximum|at least|at most|ceiling|limit|threshold|cap|'
                       r'must be|no more than|up to)(?:\s+\w+){0,2}[\s:]+$', re.IGNORECASE)
# Only plain words may sit between: "ceiling ($4000 < $8000)" compares the user's income, it does not state a rule.
WINDOW = re.compile(r'(\d{4})-(\d{2})(?:\.\.(\d{4})-(\d{2}))?')
NOT_EVIDENCE = {'source', 'as_of', 'id', 'block_id', 'place_id', 'project_id'}


def _date_claims(text):
    """Return the text without day dates, and the ISO form of each one."""
    found = []
    for pattern in DAY_DATES:
        for m in pattern.finditer(text):
            iso = f"{m['y']}-{MONTHS.index(m[2 if pattern is DAY_DATES[0] else 1][:3].lower()) + 1:02d}-{int(m['d']):02d}"
            found.append((m.group(), iso))
        text = pattern.sub(' ', text)
    return text, found


def _skip_year(match):
    # A year after a date word is a label, unless money is nearby ("in 2025 the instalment is 2050").
    near = match.string[max(0, match.start() - 30):match.end() + 30]
    return match.group() if MONEY.search(near) else ' '


def claims(text):
    """Return (raw, value, decimals, scaled, threshold) for each number the text states."""
    text, _ = _date_claims(str(text))
    for pattern in LABELS:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    text = YEAR.sub(_skip_year, text)
    # Markdown emphasis would hide list labels like "**1.**".
    text = LIST_LABEL.sub(' ', re.sub(r'[*_`]', '', text))
    found = []
    for match in NUMBER.finditer(text):
        whole, fraction, scale = match.group(2), match.group(3) or '', match.group(4) or ''
        value = Decimal(whole.replace(',', '') + fraction)
        if scale:
            value *= 1000000 if 'million' in scale.lower() else 1000
        threshold = bool(THRESHOLD.search(text[max(0, match.start() - 30):match.start()]))
        found.append((match.group().strip(), value, len(fraction) - 1 if fraction else 0, bool(scale), threshold))
    return found


def evidence(results):
    """Numbers and ISO dates in tool results, following the evidence rules above."""
    values, dates = set(), set()

    def walk(node, key=None):
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            if math.isfinite(node):
                values.add(abs(Decimal(str(node))))
        elif isinstance(node, str) and not node.startswith('http'):
            dates.update(re.findall(r'\b\d{4}-\d{2}-\d{2}\b', node))
            if key in NOT_EVIDENCE:
                return
            if key == 'label':
                # A place label written by code from our own tables ("Blk 227 Bishan St 23") is a name, so its
                # digits are evidence for listing that place; no other prose counts.
                values.update(Decimal(n) for n in re.findall(r'\d+', node))
                return
            if re.fullmatch(r'\s*-?\d+(?:\.\d+)?\s*', node):
                values.add(abs(Decimal(node.strip())))
            elif WINDOW.fullmatch(node.strip()):
                values.update(Decimal(part) for part in WINDOW.fullmatch(node.strip()).groups() if part)
        elif isinstance(node, dict):
            if 'error' not in node:  # tool errors are not evidence for an answer
                for name, item in node.items():
                    walk(item, name)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item, key)

    walk(list(results))
    return values, dates


def _matches(claim, values):
    _, value, decimals, scaled, _ = claim
    if value in values:
        return True
    if scaled or decimals == 0:
        return False
    step = Decimal(1).scaleb(-decimals)
    return any(v.quantize(step, ROUND_HALF_UP) == value for v in values)


def check(answer, question, results):
    """Return the stated numbers (question echoes left out) and the ungrounded ones."""
    given = {c[1] for c in claims(question)}
    asked_dates = {iso for _, iso in _date_claims(str(question))[1]}
    # A question number is only an echo when it is not presented as a threshold.
    stated = [c for c in claims(answer) if c[4] or c[1] not in given]
    found, dates = evidence(results)
    days = [(raw, iso) for raw, iso in _date_claims(str(answer))[1] if iso not in asked_dates]
    return {'numbers': [c[0] for c in stated] + [raw for raw, _ in days],
            'ungrounded': [c[0] for c in stated if not _matches(c, found)]
            + [raw for raw, iso in days if iso not in dates]}


ASKS = re.compile(r'\?|\b(?:please (?:provide|share|tell|confirm)|could you|can you (?:tell|share|provide)|'
                  r'what is your|what are your|i need|let me know)\b', re.IGNORECASE)
DECLINE = re.compile(r"\b(?:cannot|can't|can not|unable to|not able to|won't|will not) (?:predict|provide|advise|"
                     r"give|forecast|recommend|help)\b|\b(?:can|could) only (?:help|assist|provide)\b|\boutside my scope\b",
                     re.IGNORECASE)
VERDICT = re.compile(r'\b(?:eligible|ineligible|qualify|qualifies|can buy|cannot buy|can\'t buy|can apply|'
                     r'cannot apply|will get|you get|you receive)\b|^\s*(?:yes|no)\b', re.IGNORECASE)


# A rule stated as fact ("at least 35 years old", "the MOP is 5 years") is never just a question.
RULE_WORDS = re.compile(r'\b(?:at least|at most|minimum|maximum|ceiling|limit|must|required?|requires?|MOP)\b|'
                        r'\byears? old\b', re.IGNORECASE)


def is_clarification(text):
    """A request for missing details: it asks, gives no verdict, and states no amount.

    Only small numbers may appear (like "12 months" in a question about work history); any
    "$", "%" or number of 1,000 or more makes it a factual answer, which is checked as usual.
    """
    text = str(text)
    # A decline often ends with "please provide..." for something else; it keeps the normal rewrite.
    if DECLINE.search(text) or not ASKS.search(text) or VERDICT.search(text) or RULE_WORDS.search(text) or re.search(r'[$%]', text):
        return False
    return all(c[1] < 1000 for c in claims(text))


def rewrite_request(ungrounded, clarification=False):
    if clarification:
        # A no-tool request for details needs no numbers at all.
        return ("You called no tool, so state no numbers: " + ", ".join(ungrounded) + " came from no tool result. "
                "Rewrite your reply to ask only for the missing details, and state no numbers.")
    return ("Your answer states these numbers, but none of this question's tool results "
            "contain them: " + ", ".join(ungrounded) + ". Rewrite the answer. Use only "
            "numbers that appear in tool results (call a tool or calculate if you need one), "
            "or leave the number out and say you cannot give it reliably.")
