"""Ask the 10 hand-written questions through the full agent and save every answer for review."""

import json
import time
from pathlib import Path

from ask_hdb.agent import ask
from ask_hdb.check_cases import CASES

out = []
for i, case in enumerate(CASES, 1):
    start = time.time()
    r = ask(case["question"])
    r["seconds"] = round(time.time() - start)
    r["question"], r["expected_tool"] = case["question"], case["tool"]
    out.append(r)
    print(i, r["seconds"], "s", [c["name"] for c in r["tool_calls"]], r["stopped_reason"], flush=True)
path = Path(__file__).resolve().parents[1] / "eval/reports/week2-answers.json"
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(out, indent=1, default=str))
