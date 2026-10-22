"""Profile confirmation: "Is this right?" before any eligibility or grant tool runs.

Code decides, not the prompt. The agent stops before a gated tool runs and shows the profile
the model is about to use, written by code from the tool arguments (no model wording). The
tool runs on a later turn only if the user said yes to that exact profile. Any change in the
arguments gives a new reference, so the user is asked again.
"""

import hashlib
import re
from itertools import pairwise

# Tools whose answer depends on the buyer's profile (eligibility, grants, loan limits).
GATED = {"can_buy_resale", "cpf_housing_grant", "ehg_amount", "phg_amount", "max_loan",
         "can_apply_bto", "bto_ehg_amount"}
# The model can set "confirmed" itself, so it is never part of the profile or proof of a yes.
IGNORED = {"confirmed"}
EMPTY = {None, "", "none", "null", "not_applicable"}
REF = re.compile(r'\(profile ref ([0-9a-f]{8})\)')
YES = re.compile(r"\s*(?:yes|y|yep|yeah|correct|confirm(?:ed)?|(?:yes,?\s*)?(?:that'?s|that is|it'?s|this is) "
                 r"(?:right|correct))[\s.!]*", re.IGNORECASE)
MONEY = ("income", "price")


def _clean(value):
    if isinstance(value, str):
        value = value.strip().lower()
        return None if value in EMPTY else value
    if isinstance(value, float) and value.is_integer():
        return int(value)  # 4400 and 4400.0 are the same answer
    return value


def profile(args):
    """The arguments that describe the buyer and flat, normalised so equal answers compare equal."""
    return {k: _clean(v) for k, v in sorted(args.items()) if k not in IGNORED and _clean(v) is not None}


def _hash(lines):
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:8]


def ref(args):
    return _hash(_lines(args))


def _show(key, value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and any(word in key for word in MONEY):
        return f"${value:,}"
    return str(value).replace("_", " ")


def _lines(args):
    shown = profile(args)
    return [f"- {key.replace('_', ' ').capitalize()}: {_show(key, value)}" for key, value in shown.items()]


HEADER = "Before I check this, please confirm the details I will use:"


def question_text(args):
    """The confirmation message, written by code from the tool arguments."""
    return (HEADER + "\n" + "\n".join(_lines(args))
            + f"\nIs this right? Reply yes to continue, or tell me what to change. (profile ref {ref(args)})")


def _shown_ref(text):
    """The ref of the lines the message actually shows, or None when it is not a code-written message.
    A model that copies the template with other values and an old ref fails this check."""
    lines = text.splitlines()
    found = REF.search(lines[-1]) if len(lines) >= 2 else None
    if not found or lines[0] != HEADER or _hash(lines[1:-1]) != found.group(1):
        return None
    return found.group(1)


def confirmed(history, question):
    """References the user said yes to (a code confirmation message followed by a plain yes),
    and the user's questions that led to them. The answer may restate numbers from those questions,
    because the turn's own question is only "yes"."""
    turns = [(getattr(m, "type", None), str(getattr(m, "content", ""))) for m in history]
    turns.append(("human", question))
    refs, asked = set(), []
    for index, ((kind, text), (next_kind, reply)) in enumerate(pairwise(turns)):
        shown = _shown_ref(text) if kind == "ai" else None
        if shown and next_kind == "human" and YES.fullmatch(reply):
            refs.add(shown)
            # Only the turn that says yes may restate the earlier question's numbers.
            if index == len(turns) - 2:
                asked += [t for k, t in turns[index - 1:index] if k == "human"]
    return refs, asked
