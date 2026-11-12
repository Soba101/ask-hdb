# Architecture

## The big picture

```
 Web chat (FastAPI + front end)
      |
      v
 LangGraph agent  ----(traces)---->  Langfuse
   |  supervisor
   |   ├─ profile worker   asks questions, builds a BuyerProfile, asks "is this right?"
   |   ├─ tools worker     calls MCP tools to get numbers
   |   └─ answer worker    writes the reply from tool results only
   |
   |  grounding check: every number in the reply must appear in a tool result
   |
   v
 MCP server (ask_hdb.mcp)            pure Python, no LLM inside
   ├─ check_eligibility(profile)     -> rules engine + rules/*.yaml
   ├─ estimate_grants(profile)       -> rules engine
   ├─ max_loan(profile)              -> rules engine
   ├─ price_stats(filters)           -> pandas over data/clean/resale.parquet
   ├─ find_sales(filters)            -> pandas, returns rows with IDs
   ├─ compare_price(block_id, price) -> comparable recent sales (COV worry)
   ├─ nearest(block_id, kind)        -> geo index (MRT, schools) built from OneMap
   └─ policy_explain(topic)          -> official HDB page title + link (BM25 over own summaries)
```

## Why it is split this way
- **The MCP server has no LLM in it.** Every tool is plain code, so it can be unit tested
  and gives the same answer every time. This is the Whisperwick rule again:
  agents decide intentions, code decides reality.
- **The agent never sees raw tables.** Tools return small, labelled results
  (e.g. `{"median": 585000, "n_sales": 42, "period": "2025-10..2026-09"}`).
  Small results mean cheaper calls and fewer mistakes.
- **Workers keep each prompt short.** The profile worker does not need price tools;
  the answer worker does not need to ask questions.

## Key data shapes (pydantic)

```python
class BuyerProfile(BaseModel):
    scheme: Literal["family", "single"]          # v1 only supports these two
    citizenships: list[Literal["SC", "SPR", "foreigner"]]
    ages: list[int]
    monthly_household_income: int                # SGD, gross
    first_timer: bool                            # no previous HDB subsidy
    near_parents_address: str | None = None      # for the Proximity Housing Grant
    confirmed: bool = False                      # set True only after the user says yes

class ToolResult(BaseModel):
    tool: str
    inputs: dict
    output: dict
    rule_sources: list[str] = []                 # URLs behind any rule used
```

## Rules engine
- `rules/2026-10.yaml` holds the numbers: income ceilings, grant tiers, loan limits.
  Each value has `source` (URL) and `as_of` (date).
- `ask_hdb/rules/` has small functions, one per rule (e.g. `ehg_amount(income)`).
- Every function returns the answer **and** the rule IDs it used, so answers can cite them.
- Tests use HDB's own worked examples from its website as expected results.

## Data pipeline (re-runnable scripts, no hand edits)
1. `scripts/fetch_resale.py`: download resale prices (Jan 2017 onwards) from data.gov.sg.
   Dataset `d_8b84c4ee58e3cfc0ece0d773c8ca6abc`. Free under the Open Data Licence.
2. `scripts/clean_resale.py`: parse dates, lease left in months, storey midpoint.
   Give every block a stable ID: `blk_<block>_<street-slug>`.
3. `scripts/geocode_blocks.py`: block address -> lat/long via OneMap search. Cached to disk.
   Cross-check with the data.gov.sg HDB Existing Buildings GeoJSON (block + postal code outlines).
4. `scripts/fetch_places.py`: MRT stations and primary schools with lat/long.

## Distances
- v1 uses straight-line (haversine) distance. Every answer says "straight-line".
- Note: HDB's 1 km / 2 km primary school rule is measured by the official OneMap tool,
  not by us. We say "about", and link to OneMap for the official check.

## Grounding check (the trust feature)
- After the answer worker writes a reply, `grounding.py` pulls out every number.
- Each number must match a value in this turn's tool results (allowing formatting
  like `$585,000` vs `585000`, and rounding we declare).
- If any number is unsupported, the reply is rejected and rewritten once.
  If it fails again, the agent says it cannot answer reliably.
- Every check is logged, so the eval can report the grounding rate. The server log gets one `grounding`
  line per run: the kinds of rejected numbers (money, year, date, percent, number), whether the reply was
  replaced, and the tool names. No message text or values.
- Years: a year after a date word ("October 2024") is a label, unless a money word is close to it.
  Then it is a claim, and it is grounded only when a tool result string (a source URL included) cites the
  same year. Amounts such as `$2024` are never grounded this way.
- On the turn where the user says yes to a profile confirmation, the code-written confirmation lines count
  as the user's words, so the answer can repeat the user's own income. Earlier turns do not count.
- `policy_explain` results are excluded by tool name and by their payload marker. Titles, summaries
  and links cannot ground numbers or dates. They cannot supply place labels either.
  Rules tools still supply eligibility verdicts. Links only: `policy.py` holds the 10 allowlisted
  hdb.gov.sg pages with a title and a summary written for this project (search hints, no digits).
  No HDB text is fetched or stored: hdb.gov.sg refuses automated fetching, and HDB's terms ask
  for written approval before reuse. The browser gets page titles and links.

## Profile confirmation
- Before an eligibility, grant or loan tool runs, `confirm.py` writes an "Is this right?" message from the
  arguments the tool will run with (schema defaults included). The model does not write it.
- `confirm_display.py` shows each value in plain words with the raw value in brackets ("both first-timers
  (both_first)"). A value the user's words do not back gets "(you did not give this: please check)":
  numbers need a whole matching number (a lease in years counts as months times 12), choices and yes/no
  values need matching words, and a negation counts ("never owned a condo" backs no).
- A short ref (a hash of the raw values) ties the user's yes to that exact profile. A changed value needs a new yes.
- Arguments that fail the tool's schema get no confirmation. The tool returns its validation error and the model fixes the call.

## Tool logs
- `TOOL_LOG=1` (default) writes one JSON line per tool call: the tool, its arguments and a result count.
  Profile, grant, loan and calculate tools log only argument names, never income, ages or citizenship.
- A failed model provider logs `provider_failed` (provider and error class). The API logs `chat_failed` (class only).

## Safety limits
- Max tool calls and max tokens per question, set in settings. Hit the limit -> stop and say so.
- Every answer states the data's "as of" month, so old data is never silent.

## Model access
- One `llm.py` that builds a LangChain chat model from settings.
- `.env`: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Local llama-server by default.
- Tool calling must work with the local model. Week 2 tests this first.

## Folder layout (as built, 2026-10)

```
src/ask_hdb/
  agent.py        ReAct agent, system prompt, grounding rewrite, profile confirmation gate
  tools.py        tool wrappers (JSON in, JSON out); tool_inputs.py has their pydantic arguments
  sales.py, compare.py, calc.py, clean.py   price tools, comparable sales, calculator, cleaning
  confirm.py      code-written "Is this right?" before eligibility and grant tools
  confirm_display.py   plain-word profile lines and the "you did not give this" flags
  grounding.py    number check against this question's tool results
  policy.py, policy_sources.py   policy page links (own summaries) and the fixed official URL list
  rules/          dated rule functions (resale, BTO); numbers come from rules/*.yaml
  bto/            BTO launch data, history, scenarios, planned rail lines
  geo/            geocoding, distances, nearest places
  mcp/            MCP server and client around the same tools
  evalrun/        eval runner, scoring, conditions (llm-only, agent, full), reports
  llm.py          chat model from settings
  tracing.py      optional Langfuse tracing, one trace per question with scores (TRACING=1)
  sun.py          sun position for the 3D map shadows and facing
  api/            FastAPI app: /chat stream, map data, cards, nearby places and walking routes; static/ holds the page
  __init__.py     main() has the `ask-hdb` subcommands (chat, ask, mcp, routing, eval); cli.py is the chat loop
  tool_check.py, check_cases.py   the `routing` command: tool-call check and its hand-written prompts
rules/            dated YAML rule files with sources (resale, bto/, plans/)
scripts/          data fetch, build and expected-value scripts
eval/             questions.yaml and reports
tests/
docs/
```
Hosting: a static demo on GitHub Pages (chat paused), and the full app in Docker on a small home server,
shared through a Cloudflare quick tunnel (the address changes on restart). See `docs/hosting-plan.md`.
Planned, not built: an always-on public host with a model, and a supervisor and worker graph. The diagram's workers
remain a design sketch; the current agent is a single bounded conversation. Policy search uses
that existing agent, with no supervisor added.
