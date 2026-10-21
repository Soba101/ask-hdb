# Roadmap

Six weeks, side-project pace. Each week has one exit check.
Do not start the next week until the exit check passes (or the miss is written down).

| Week | Focus | Exit check |
|---|---|---|
| 1 | Data + rules, no LLM | `pytest` computes known prices and HDB's worked grant examples |
| 2 | First agent | 10 hand-written questions answered correctly via tools, local model |
| 3 | Eval set + baseline | 50 questions now; table for LLM-only vs single agent |
| 4 | Places + MCP | MRT/school distance questions work; MCP server works |
| 5 | Trust features | Grounding 100%; profile confirmation; accuracy up vs week 3 |
| 6 | Ship | Langfuse traces, Docker, public demo link, README results table |
| later | Ideas parked | Walking routes, EIP quota, price trends chart, Telegram bot |

## Week 1: data and rules (no LLM)
- [ ] Repo setup: `uv init`, `pytest`, `ruff`, `.gitignore`, `.env.example`.
- [ ] `scripts/fetch_resale.py`: download the data.gov.sg resale dataset (2017 onwards).
- [ ] `scripts/clean_resale.py`: dates, lease left, storey midpoint, stable block IDs.
- [ ] `price_stats(filters)` and `find_sales(filters)` as plain functions.
- [ ] Read HDB's eligibility and grant pages. Write `rules/2026-10.yaml` with source URLs.
      Note: sources disagree on some ceilings. Use hdb.gov.sg only.
- [ ] `compare_price(block_id, price)`: comparable recent sales, same storey and lease bands.
- [ ] Rule functions: `can_buy_resale`, `cpf_housing_grant`, `ehg_amount`, `phg_amount`, `max_loan`.
- [ ] Tests: 5 price facts checked by hand, and every worked example on HDB's grant pages.
- **Exit:** `uv run pytest` green. No model involved anywhere yet.

## Week 2: first agent
- [ ] `llm.py`: chat model from `.env` (llama-server by default).
- [ ] Check the local model can call tools reliably. Try 2 models. Write down which works.
- [ ] One LangGraph ReAct agent with the week 1 functions as tools.
- [ ] Step and token limit per question (the $4,700-loop lesson).
- [ ] `ask-hdb chat` in the terminal.
- [ ] 10 hand-written questions, checked by eye.
- **Exit:** 10/10 correct, or each miss written down with its cause.

Implementation note: model selection, tools, bounded agent, terminal commands and
the scripted routing check are built. Agent score change: unavailable; no prior
agent evaluation existed. Live checks are blocked because the build sandbox cannot
download the new dependencies. See `docs/week2-notes.md`; the exit check remains open.

## Week 3: eval set and baseline
- [x] `eval/questions.yaml`: 50 questions, including 10 fixed held-out questions.
      Price expectations use independent pandas; rule expectations cite the frozen YAML by hand.
- [x] `ask-hdb eval` runner: scores, steps, tokens, time. JSON + markdown report.
      The previous routing check remains available as `ask-hdb routing`.
- [x] Run LLM-only and single-agent conditions (9B Mac model, 2026-10-20): LLM-only 0/10/0 (number/verdict/refusal);
      agent 100/90/100 after four fix rounds, 9/10 held-out. Grounding 76.5% is the open gap. See `docs/eval-results.md`.
- **Exit:** a results table. **Gate:** if the agent does not clearly beat LLM-only,
  stop and find out why before adding anything.

Build note (2026-10-20): agent behavior and rule functions are unchanged. The baseline
and single-agent comparison were run; see `docs/eval-results.md`. Recorded scores predate
the scoring fixes; score changes await offline rescoring of stored reports. No model or
eval runs were made for these fixes. Distance and multi-step questions remain in week 4.

## Week 4: places and MCP (done 2026-10-21, PR #8)
- [x] `scripts/geocode_blocks.py` with a disk cache; `scripts/fetch_places.py`, `build_places.py`, `geocode_schools.py` for MRT, LRT and primary schools.
      9,477 of 9,496 recent blocks located (19 not found, mostly Towner Rd); 182 primary schools located.
- [x] Cross-check against data.gov.sg "HDB Existing Buildings": median 8.5 m, worst 79 m (`scripts/check_geocodes.py`).
- [x] `nearest_places(block_id, kind)` and `near_kind` / `near_km` filter on `price_stats` / `find_sales` (straight-line; the result also reports
      sales in blocks without coordinates).
- [x] All tools behind an MCP server (`ask_hdb/mcp`); the agent connects with `TOOL_SOURCE=mcp`.
- [x] 8 distance and 10 multi-step eval questions with independent expected answers (68 total, 16 held out).
- **Exit: met.** Distance questions 5/5. Same score through MCP as direct (97.4% number, 51 vs 50 of 52 passes). Agent score change:
  run 1 (before fixes) 86.8% / 92.1% number (direct / MCP); run 2 (after fixes) 97.4% both. Held-out: 6 new = 4/6, 10 old = 10/10.
  Details, every failure and its cause: `docs/eval-results.md`.
- Caveat (fixed 2026-10-21, PR #36): multi-step passes used to rely on the model's own arithmetic (issue #32). A `calculate` tool now does it; the
  6 new held-out multi-step questions pass 6/6 on the 9B.

## Week 4b: BTO (added 2026-10-20, scope extended 2026-10-21; plan: docs/week4b-plan.md)
Three phases; each gets approval before building.
- [ ] **4b-1** BTO rules from hdb.gov.sg only (new dated YAML), launch data (HDB annexes, approval per download), BTO sites geocoded (approximate), `list_bto_projects`,
      `bto_nearby`, BTO rule tools, about 14 eval questions (5 held out); retire `q_refuse_003` and add a replacement decline question.
- [ ] **4b-2** History: launch price vs resale after MOP for past BTOs, surrounding-area growth, government plans shown as dated facts (URA Master Plan, planned MRT). Feasibility check first.
- [ ] **4b-3** Illustrative scenario calculator with grants, HDB/bank loan and net proceeds (labelled "illustrative, from past growth, not a forecast"); update the prediction rule in AGENTS.md.
- [ ] BTO sites on the 3D map (with the week 6 UI).
- **Exit:** BTO eligibility and "what is open near X" questions pass; launch-vs-MOP and scenario answers come only from tool results, with the caveats shown.

## Week 5: trust features
- [ ] Profile worker + "Is this right?" confirmation before any eligibility tool runs.
- [ ] `grounding.py` number check, with one rewrite then an honest "I can't answer reliably".
- [ ] Supervisor + workers graph (profile, tools, answer).
- [ ] RAG over HDB policy pages for explanations, with links.
- [ ] Refusal handling for out-of-scope questions.
- **Exit:** grounding 100% on the eval; full condition beats single agent.

## Week 6: ship
- [ ] Langfuse tracing on every run.
- [ ] Web app (decided 2026-10-20, replaces the Streamlit plan): FastAPI server around the agent
      (`POST /chat` streaming each tool call, result and answer; `GET /health`), and a plain web front end:
      chat on the left, tool results and sources on the right, 3D map panel (MapLibre) with block, MRT and school markers.
      Same agent and MCP tools as the terminal; model and API key come from the server `.env`, never the browser.
      Needs: rate limit per visitor, a cost cap, no personal data stored, a clear "not financial advice" line.
- [ ] Docker Compose: web app (FastAPI + static front end), MCP server, Postgres + pgvector (Langfuse cloud free tier, or self-hosted).
- [ ] Deploy to one small VM with a cloud model (no GPU needed there).
- [ ] 3D block map in the web app (building outlines extruded by floors if a floors source is found, MRT and school markers, approximate facing). BTO sites join after week 4b.
- [ ] README: demo GIF, results table, architecture picture, "what I learned".
- **Exit:** a stranger uses the public link with no help.

## Decisions log
- 2026-10-19: Reddit shows COV/valuation is the top buyer worry. Added price check to v1.
- 2026-10-19: Project chosen. Resale only, v1 profiles: citizen families and singles 35+.
