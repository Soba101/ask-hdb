"""A bounded ReAct conversation over deterministic housing tools."""

import json
import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, convert_to_messages
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from ask_hdb import confirm as profile_check
from ask_hdb import grounding
from ask_hdb.llm import get_chat_model
from ask_hdb.tools import TOOLS

MAX_TOOL_CALLS = 8
TOKEN_BUDGET = 64000
HISTORY_MESSAGES = 6  # keep chat short so old turns cannot eat the budget
SYSTEM_PROMPT = """The LLM talks. Code decides.
Never state a number, price, distance or eligibility verdict unless it comes from
a tool result in the current question. Do not reuse numbers from chat history.
Ask for missing inputs; never invent a buyer profile or a flat's properties.
When a tool returns needs_check, explain each unresolved check and qualify the answer.
Keep rules citations and their as_of dates. State the sales data period when available.
compare_price compares past sales. Always say its level (block, street or town), n_comparables,
window, and any 'Widened' note; never call a street or town sample 'this block'. It compares past sales; it is not a valuation or a prediction of COV.
Do not predict future prices or invent unsupported capabilities; the only exception is bto_scenario, whose results you
must call "illustrative, from past growth, not a forecast" and quote with its needs_check items. For any BTO question about loan size, upfront cost,
instalment, loan balance or sale scenarios call bto_scenario (not max_loan, which is for resale), and quote its numbers as given;
ask the user for the loan interest rate and years if they are needed and missing; never assume them. For past BTO launch prices against later resale prices
use bto_history: call it descriptive history, not a forecast, quote its limits, and never say a buyer will gain. BTO (new flat) questions use
list_bto_projects, bto_nearby, can_apply_bto and bto_ehg_amount: BTO prices are indicative at launch and exclude
grants, and a BTO site is approximate (say so). Ballot odds, priority schemes and Executive Condominiums are not covered.
Pass every detail the user gave (price, category, family_timers, rooms, lease) to the
tool; a missing field can change the verdict. Tool inputs are flat JSON. Applicant citizenships and ages are comma-separated strings.
Use exact recorded town/flat_type filters and stable block_id values.
If a tool returns eligible null, a needs_check naming a missing input, or an error naming
missing fields, do not state a verdict: call the tool again with the value if the user gave it,
otherwise ask the user for it. Decline (do not explain how) investment timing, price
predictions, advice on which option earns more money, and Executive Condominium questions; say you only help with resale and BTO prices, grants and eligibility.
Never add, subtract, multiply or divide numbers yourself: call calculate with the
numbers from tool results and quote its result. If a question covers several towns, blocks or places, call the tool once for each and
use every result. Tool errors are not evidence for an answer. Explain when you cannot answer reliably.
Quote a rule threshold (age, income ceiling, months, loan limit, date) only from the value or value_pct in
the tool result's rules list; if it is not there, leave the number out. Never count list items yourself:
for "how many within X km" call nearest_places with within_km and quote n_within. A decline states no numbers.
"""


class LimitReached(Exception):
    """Leave the graph before it can do more work."""


class NeedsConfirmation(Exception):
    """Leave the graph before a profile tool runs on a profile the user has not confirmed."""


def _strip_titles(node):
    if isinstance(node, dict):
        return {k: _strip_titles(v) for k, v in node.items() if k != "title"}
    if isinstance(node, list):
        return [_strip_titles(v) for v in node]
    return node


def _compact(tools):
    # For small-context servers (8k per slot): same tools and fields, without the repeated "title" keys.
    return [_strip_titles(convert_to_openai_tool(tool)) for tool in tools]


def _size(value):
    # Bytes give a conservative fallback when a local server omits token usage.
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


def ask(question, history=None, confirm=False) -> dict:
    """confirm=True asks "Is this right?" before eligibility and grant tools (chat and the full eval)."""
    load_dotenv()
    source = os.getenv("TOOL_SOURCE", "direct")
    if source == "direct":
        return _ask(question, history, TOOLS, confirm)
    if source != "mcp":
        raise ValueError("TOOL_SOURCE must be direct or mcp")
    from ask_hdb.mcp.client import load_mcp_tools

    with load_mcp_tools() as tools:
        return _ask(question, history, tools, confirm)


def _ask(question, history, tools, confirm=False):
    calls, pending = [], {}
    tokens, requested, reported = 0, 0, False
    stopped_reason = None
    answer = ""
    plain = get_chat_model()
    model = plain.bind_tools(_compact(tools) if os.getenv("LLM_COMPACT_TOOLS") == "1" else tools)
    schemas = [tool.args_schema if isinstance(tool.args_schema, dict)
               else tool.args_schema.model_json_schema() for tool in tools]

    def run_model(messages, config):
        nonlocal tokens, requested, reported
        final = requested >= MAX_TOOL_CALLS
        # Bytes over-count tokens, so use them only until a real usage figure is reported.
        input_bound = 0 if reported else (_size([m.model_dump() for m in messages]) + _size(schemas)) // 3
        remaining = TOKEN_BUDGET - tokens - input_bound - 1024
        # Small-context servers (8k per slot): cap the reply so prompt + reply always fits.
        remaining = min(remaining, int(os.getenv("LLM_MAX_TOKENS", remaining)))
        if remaining <= 0:
            raise LimitReached("tokens")
        # After the last allowed tool call the model may still write its answer, but with no tools.
        reply = (plain if final else model).bind(max_tokens=remaining).invoke(messages, config)
        usage = reply.usage_metadata
        reported = reported or bool(usage)
        tokens += (usage["total_tokens"] if usage else input_bound + _size(reply.model_dump()))
        if tokens >= TOKEN_BUDGET or reply.response_metadata.get("finish_reason") in {
            "length", "max_tokens",
        } or reply.response_metadata.get("stop_reason") == "max_tokens":
            raise LimitReached("tokens")
        if final and reply.tool_calls:
            raise LimitReached("tool_calls")
        # One model response may request many tools. Never execute past the cap.
        if len(reply.tool_calls) > MAX_TOOL_CALLS - requested:
            reply = reply.model_copy(update={"tool_calls": reply.tool_calls[
                :MAX_TOOL_CALLS - requested
            ]})
        for call in reply.tool_calls if confirm else []:
            if call["name"] in profile_check.GATED and profile_check.ref(call["args"]) not in said_yes:
                raise NeedsConfirmation(call["args"])
        requested += len(reply.tool_calls)
        return reply

    def select_model(state, runtime):
        # A dynamic model lets the budget guard run before every API request.
        return RunnableLambda(run_model)

    graph = create_react_agent(select_model, tools, prompt=SYSTEM_PROMPT, version="v1")
    # Only dialogue belongs in history; past tool evidence must be recomputed.
    messages = [message for message in convert_to_messages(history or [])
                if isinstance(message, (HumanMessage, AIMessage))
                and not (isinstance(message, AIMessage) and message.tool_calls)]
    said_yes, asked = profile_check.confirmed(messages, question)
    echo = "\n".join(asked + [question])  # numbers the user gave may be restated
    messages = messages[-HISTORY_MESSAGES:] + [HumanMessage(content=question)]

    def run(messages):
        # Stream one graph run; keep every message so a rewrite can continue the same turn.
        answer = ""
        # A ReAct round has a model node and a tool node. Calls are capped above.
        for update in graph.stream({"messages": messages},
                                   {"recursion_limit": MAX_TOOL_CALLS * 2 + 2},
                                   stream_mode="updates"):
            for value in update.values():
                for message in value.get("messages", []):
                    messages = messages + [message]
                    if isinstance(message, AIMessage):
                        pending.update({call["id"]: call for call in message.tool_calls})
                        if not message.tool_calls:
                            answer = message.text
                    elif isinstance(message, ToolMessage):
                        call = pending.pop(message.tool_call_id)
                        try:
                            result = json.loads(message.content)
                        except (ValueError, TypeError):
                            result = {"error": "Tool returned unreadable output"}
                        calls.append({"name": call["name"], "args": call["args"], "result": result})
        return answer, messages

    checked, first, kept, needs_confirmation = None, [], False, False
    try:
        answer, messages = run(messages)
        checked = grounding.check(answer, echo, [c["result"] for c in calls])
        first = checked["ungrounded"]
        if first:
            # One rewrite, inside the same budgets and tool cap, then an honest fallback.
            asking = not calls and grounding.is_clarification(answer)
            answer, _ = run(messages + [HumanMessage(content=grounding.rewrite_request(first, asking))])
            checked = grounding.check(answer, echo, [c["result"] for c in calls])
            # A no-tool request for missing details states no fact, so a small number left in it
            # is reported but does not replace the question with the fallback.
            kept = bool(checked["ungrounded"]) and asking and not calls and grounding.is_clarification(answer)
            if (checked["ungrounded"] and not kept) or not answer.strip():
                answer = grounding.CANNOT_ANSWER
    except NeedsConfirmation as exc:
        # Code writes the question from the tool arguments; the tool has not run.
        answer, needs_confirmation, checked = profile_check.question_text(exc.args[0]), True, None
    except LimitReached as exc:
        stopped_reason = str(exc)
    except GraphRecursionError:
        stopped_reason = "recursion_limit"
    if stopped_reason:
        answer = f"stopped: limit ({stopped_reason}). Please narrow the question."
    if checked is not None:
        # Same keys even when the rewrite was stopped by a limit.
        checked = {**checked, "first_ungrounded": first, "rewritten": bool(first),
                   "replaced": answer == grounding.CANNOT_ANSWER, "kept_clarification": kept}
    return {"answer": answer, "tool_calls": calls, "tokens": tokens, "stopped_reason": stopped_reason,
            "grounding": checked, "needs_confirmation": needs_confirmation}
