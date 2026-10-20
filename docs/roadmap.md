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

## Week 4: places and MCP
- [ ] `scripts/geocode_blocks.py` with a disk cache. `scripts/fetch_places.py` for MRT and schools.
- [ ] Cross-check OneMap block coordinates against data.gov.sg "HDB Existing Buildings" (GeoJSON, `d_16b157c52ed637edd6ba1232e026258d`):
      building outlines keyed by block number + postal code. Use it to spot bad geocodes. It has no street name, so it cannot replace OneMap.
- [ ] `nearest(block_id, kind)` and a "within X km" filter for `find_sales`.
- [ ] Move all tools into an MCP server (`ask_hdb/mcp`). Agent connects through it.
- [x] Add distance and multi-step questions to the eval.
- **Exit:** distance questions pass; same eval score through MCP as before.

Offline build note (2026-10-20): place building, block cross-checks, straight-line
distance tools and sales distance filters are implemented. School geocoding is
prepared but was not run. Agent eval score change is unverified: the no-network
constraint prevents the model-backed eval run. Frozen questions are unchanged.

MCP build note: all registered tools are exposed over stdio with their original
schemas and results. Set `TOOL_SOURCE=mcp` for chat or use `ask-hdb eval --tools mcp`;
direct remains the default. Offline protocol and fake-model tests cover parity and
limits. Agent eval score change is unverified: model calls were explicitly disabled
for this build, so no model-backed eval was run and existing reports were untouched.

Eval additions: appended 8 distance and 10 multi-step questions with independent
local expected answers. The bank now has 68 questions and 16 marked held out,
including 6 new held-out IDs fixed before tuning. The original 50 entries and their
fingerprints are unchanged. Offline tests and both expected-answer builders pass.
Agent behavior is unchanged. Score change and direct/MCP score parity remain
unverified: network access, model calls and eval runs were explicitly disabled.

## Week 4b: BTO (added 2026-10-20, after week 4)
Scope decided by the user: rules + launch info + map. Plan to be shown and approved before building.
- [ ] BTO rules from hdb.gov.sg only, in a new dated YAML (eligibility, grants, loan limits that differ from resale).
- [ ] BTO launch data: find a clean source first (HDB publishes launches as web pages). Show the user the source before using it.
- [ ] BTO sites geocoded and added to the places table (nearest MRT and primary schools, straight-line).
- [ ] New eval questions; the current "How do I apply for a BTO flat?" decline question (q_refuse_003) must change with the scope.
- [ ] BTO sites on the 3D map (with the week 6 UI).
- **Exit:** BTO eligibility and "what is open near X" questions pass in the eval.

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
