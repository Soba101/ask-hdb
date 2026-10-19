# Architecture

## The big picture

```
 Streamlit chat
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
   └─ search_policy(question)        -> pgvector over HDB policy pages (RAG)
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
4. `scripts/fetch_places.py`: MRT stations and primary schools with lat/long.
5. `scripts/fetch_policy.py`: HDB policy pages -> text chunks with URL and fetch date -> pgvector.

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
- Every check is logged, so the eval can report the grounding rate.

## Safety limits
- Max tool calls and max tokens per question, set in settings. Hit the limit -> stop and say so.
- Every answer states the data's "as of" month, so old data is never silent.

## Model access
- One `llm.py` that builds a LangChain chat model from settings.
- `.env`: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Local llama-server by default.
- Tool calling must work with the local model. Week 2 tests this first.

## Folder layout (planned)

```
ask_hdb/
  agent/        LangGraph graph, workers, prompts
  mcp/          MCP server and tool definitions
  rules/        rule functions (numbers come from rules/*.yaml)
  data/         loaders for clean data and the geo index
  grounding.py  number check
  llm.py        model client
  cli.py        `ask-hdb chat`, `ask-hdb eval`
rules/          dated YAML rule files with sources
scripts/        data fetch and clean scripts
eval/           questions.yaml, runner, reports
app/            Streamlit page
tests/
docs/
```
