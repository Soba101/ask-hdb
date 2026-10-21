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
- Labels are not claims and are skipped: block IDs (blk_...), ISO dates and months
  (2025-10), bare years 1960-2100 (no $, comma, decimal or unit after them),
  ordinals under 100 (1st, 21st), flat types (4-room, 3 ROOM) and list labels ("1.").
- Numbers the user wrote in the question may be restated.
- Tool results with an "error" key are not evidence. Tool arguments are not evidence.
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
LABELS = [
    r'\bblk_[\w-]+',                                  # stable block IDs
    r'\b(?:19|20)\d{2}-\d{2}(?:-\d{2})?\b',            # ISO dates and months
    # A bare year: no $ before it, and no comma, decimal, % or unit after it.
    (r'(?<![\w$,.])(?:19[6-9]\d|20\d{2}|2100)(?!\d|,\d|%|\.\d|\s*(?:k\b|million|/|a month|per\b|'
     r'dollars?|sgd|months?|years?|km\b|m\b))'),
    r'\b\d{1,2}(?:st|nd|rd|th)\b',                     # ordinals
    r'\b[1-5][\s-]?room\b',                            # flat types
]
LIST_LABEL = re.compile(r'^\s*(?:[-*+•]\s+)?\d+[.)]\s+', re.MULTILINE)


def claims(text):
    """Return (raw, value, decimals, scaled) for each number the text states."""
    text = str(text)
    for pattern in LABELS:
        text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)
    # Markdown emphasis would hide list labels like "**1.**".
    text = LIST_LABEL.sub(' ', re.sub(r'[*_`]', '', text))
    found = []
    for match in NUMBER.finditer(text):
        whole, fraction, scale = match.group(2), match.group(3) or '', match.group(4) or ''
        value = Decimal(whole.replace(',', '') + fraction)
        if scale:
            value *= 1000000 if 'million' in scale.lower() else 1000
        found.append((match.group().strip(), value, len(fraction) - 1 if fraction else 0, bool(scale)))
    return found


def evidence(results):
    """Every number inside tool results (numeric values and digits inside strings)."""
    values = set()

    def walk(node):
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            if math.isfinite(node):
                values.add(abs(Decimal(str(node))))
        elif isinstance(node, str):
            # Strings hold windows ("2025-10..2026-09") and block IDs; URLs are not evidence.
            if not node.startswith('http'):
                values.update(Decimal(d) for d in re.findall(r'\d+(?:\.\d+)?', node))
        elif isinstance(node, dict):
            if 'error' not in node:  # tool errors are not evidence for an answer
                for item in node.values():
                    walk(item)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(list(results))
    return values


def _matches(claim, values):
    _, value, decimals, scaled = claim
    if value in values:
        return True
    if scaled or decimals == 0:
        return False
    step = Decimal(1).scaleb(-decimals)
    return any(v.quantize(step, ROUND_HALF_UP) == value for v in values)


def check(answer, question, results):
    """Return the stated numbers (question echoes left out) and the ungrounded ones."""
    given = {value for _, value, _, _ in claims(question)}
    stated = [c for c in claims(answer) if c[1] not in given]
    found = evidence(results)
    return {'numbers': [c[0] for c in stated],
            'ungrounded': [c[0] for c in stated if not _matches(c, found)]}


def rewrite_request(ungrounded):
    return ("Your answer states these numbers, but none of this question's tool results "
            "contain them: " + ", ".join(ungrounded) + ". Rewrite the answer. Use only "
            "numbers that appear in tool results (call a tool or calculate if you need one), "
            "or leave the number out and say you cannot give it reliably.")
