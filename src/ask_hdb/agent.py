"""A bounded ReAct conversation over deterministic housing tools."""

import json
import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, convert_to_messages
from langchain_core.runnables import RunnableLambda
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

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
Do not predict future prices, answer BTO questions or invent unsupported capabilities.
Pass every detail the user gave (price, category, family_timers, rooms, lease) to the
tool; a missing field can change the verdict. Tool inputs are flat JSON. Applicant citizenships and ages are comma-separated strings.
Use exact recorded town/flat_type filters and stable block_id values.
If a tool returns eligible null, a needs_check naming a missing input, or an error naming
missing fields, do not state a verdict: call the tool again with the value if the user gave it,
otherwise ask the user for it. Decline (do not explain how) investment timing, price
predictions and BTO questions; say you only help with resale prices, grants and eligibility.
If a question covers several towns, blocks or places, call the tool once for each and
use every result. Tool errors are not evidence for an answer. Explain when you cannot answer reliably.
"""


class LimitReached(Exception):
    """Leave the graph before it can do more work."""


def _size(value):
    # Bytes give a conservative fallback when a local server omits token usage.
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


def ask(question, history=None) -> dict:
    load_dotenv()
    source = os.getenv("TOOL_SOURCE", "direct")
    if source == "direct":
        return _ask(question, history, TOOLS)
    if source != "mcp":
        raise ValueError("TOOL_SOURCE must be direct or mcp")
    from ask_hdb.mcp.client import load_mcp_tools

    with load_mcp_tools() as tools:
        return _ask(question, history, tools)


def _ask(question, history, tools):
    calls, pending = [], {}
    tokens, requested, reported = 0, 0, False
    stopped_reason = None
    answer = ""
    plain = get_chat_model()
    model = plain.bind_tools(tools)
    schemas = [tool.args_schema if isinstance(tool.args_schema, dict)
               else tool.args_schema.model_json_schema() for tool in tools]

    def run_model(messages, config):
        nonlocal tokens, requested, reported
        final = requested >= MAX_TOOL_CALLS
        # Bytes over-count tokens, so use them only until a real usage figure is reported.
        input_bound = 0 if reported else (_size([m.model_dump() for m in messages]) + _size(schemas)) // 3
        remaining = TOKEN_BUDGET - tokens - input_bound - 1024
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
    messages = messages[-HISTORY_MESSAGES:] + [HumanMessage(content=question)]
    try:
        # A ReAct round has a model node and a tool node. Calls are capped above.
        for update in graph.stream({"messages": messages},
                                   {"recursion_limit": MAX_TOOL_CALLS * 2 + 2},
                                   stream_mode="updates"):
            for value in update.values():
                for message in value.get("messages", []):
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
    except LimitReached as exc:
        stopped_reason = str(exc)
    except GraphRecursionError:
        stopped_reason = "recursion_limit"
    if stopped_reason:
        answer = f"stopped: limit ({stopped_reason}). Please narrow the question."
    return {"answer": answer, "tool_calls": calls, "tokens": tokens,
            "stopped_reason": stopped_reason}
