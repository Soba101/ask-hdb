"""Profile confirmation: "Is this right?" before any eligibility or grant tool runs.

Code decides, not the prompt. The agent stops before a gated tool runs and shows the profile
the model is about to use, written by code from the tool arguments (no model wording). The
tool runs on a later turn only if the user said yes to that exact profile. Any change in the
arguments gives a new reference, so the user is asked again.
"""

import hashlib
import json
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


def ref(args):
    return hashlib.sha256(json.dumps(profile(args), sort_keys=True).encode()).hexdigest()[:8]


def _show(key, value):
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and any(word in key for word in MONEY):
        return f"${value:,}"
    return str(value).replace("_", " ")


def question_text(args):
    """The confirmation message, written by code from the tool arguments."""
    # Shown as the model wrote them (normalised values are only for the reference).
    lines = [f"- {key.replace('_', ' ').capitalize()}: {_show(key, args[key])}" for key in profile(args)]
    return ("Before I check this, please confirm the details I will use:\n" + "\n".join(lines)
            + f"\nIs this right? Reply yes to continue, or tell me what to change. (profile ref {ref(args)})")


def confirmed(history, question):
    """References the user said yes to (a code confirmation message followed by a plain yes),
    and the user's questions that led to them. The answer may restate numbers from those questions,
    because the turn's own question is only "yes"."""
    turns = [(getattr(m, "type", None), str(getattr(m, "content", ""))) for m in history]
    turns.append(("human", question))
    refs, asked = set(), []
    for index, ((kind, text), (next_kind, reply)) in enumerate(pairwise(turns)):
        if kind == "ai" and next_kind == "human" and YES.fullmatch(reply) and REF.search(text):
            refs.update(REF.findall(text))
            asked += [t for k, t in turns[index - 1:index] if k == "human"]
    return refs, asked
