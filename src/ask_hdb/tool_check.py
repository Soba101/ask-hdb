"""Check model routing separately from the later full answer evaluation."""

import json
import os
from datetime import date
from pathlib import Path

from anthropic import APIError as ProviderAPIError
from langchain_core.messages import HumanMessage, SystemMessage
from openai import OpenAIError

from ask_hdb.agent import SYSTEM_PROMPT
from ask_hdb.check_cases import CASES
from ask_hdb.llm import get_chat_model
from ask_hdb.tools import TOOLS

ROOT = Path(__file__).resolve().parents[2]
MODEL_ERRORS = (ValueError, TypeError, RuntimeError, OSError, OpenAIError, ProviderAPIError)


def check_response(case, response):
    tools = {tool.name: tool for tool in TOOLS}
    calls = response.tool_calls
    right = not response.invalid_tool_calls and (
        not calls if case["tool"] is None else
        len(calls) == 1 and calls[0]["name"] == case["tool"]
    )
    valid = right
    cause = ""
    if right and calls:
        try:
            call = calls[0]
            values = tools[call["name"]].args_schema.model_validate(call["args"]).model_dump()
            # Whitespace in applicant lists has no meaning.
            diffs = [f"{key}: got {values[key]!r}, want {expected!r}"
                     for key, expected in case["args"].items()
                     if (values[key].replace(" ", "") if key in {"ages", "citizenships"}
                         else values[key]) != expected]
            valid = not diffs
            result = tools[call["name"]].invoke(call["args"])
            if "error" in result:
                diffs.append("tool returned an error")
                valid = False
            cause = "; ".join(diffs)
        except (ValueError, TypeError, KeyError):
            valid, cause = False, "arguments failed validation"
    if not right:
        cause = "Wrong or missing tool"
    elif not valid and not cause:
        cause = "Invalid or incorrect arguments, or unavailable data"
    return {"right_tool": right, "valid_args": valid, "cause": cause}


def main():
    rows = []
    model = None
    failure = None
    try:
        model = get_chat_model().bind_tools(TOOLS)
    except MODEL_ERRORS as exc:
        # Exception text can contain URLs or credentials; store only its type.
        failure = type(exc).__name__
    for index, case in enumerate(CASES, 1):
        if failure:
            row = {"right_tool": False, "valid_args": False,
                   "cause": f"Not run: {failure}"}
        else:
            try:
                response = model.bind(max_tokens=2048).invoke([
                    SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=case["question"]),
                ])
                row = check_response(case, response)
            except MODEL_ERRORS as exc:
                failure = type(exc).__name__
                row = {"right_tool": False, "valid_args": False,
                       "cause": f"Not run: {failure}"}
        rows.append({"case": index, **row})
    score = sum(row["right_tool"] and row["valid_args"] for row in rows)
    table = ["| Case | Right tool | Valid args | Cause |", "|---|---|---|---|"]
    for row in rows:
        table.append(f"| {row['case']} | {'PASS' if row['right_tool'] else 'FAIL'} | "
                     f"{'PASS' if row['valid_args'] else 'FAIL'} | {row['cause']} |")
    report = (f"\n## Tool-call check {date.today().isoformat()}\n\n"
              f"Model: `{os.getenv('LLM_MODEL', 'qwen3.5-9b-16k')}`\n\n"
              + "\n".join(table) + f"\n\nRouting score: {score}/{len(rows)}. "
              "This checks routing and arguments; answer grounding still needs manual review.\n")
    notes = ROOT / "docs/week2-notes.md"
    with notes.open("a") as stream:
        stream.write(report)
    print(report)
    # Keep expected answers reproducible and independent of the model.
    expected = [{"case": index, "tool": case["tool"], "result":
                 next(tool for tool in TOOLS if tool.name == case["tool"]).invoke(case["args"])
                 if case["tool"] else {"unsupported": "Future price prediction"}}
                for index, case in enumerate(CASES, 1)]
    target = ROOT / "eval/reports/week2-expected.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(expected, indent=2))
    return rows
