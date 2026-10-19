# Roadmap

Six weeks, side-project pace. Each week has one exit check.
Do not start the next week until the exit check passes (or the miss is written down).

| Week | Focus | Exit check |
|---|---|---|
| 1 | Data + rules, no LLM | `pytest` computes known prices and HDB's worked grant examples |
| 2 | First agent | 10 hand-written questions answered correctly via tools, local model |
| 3 | Eval set + baseline | ~68 questions; table for LLM-only vs single agent |
| 4 | Places + MCP | MRT/school distance questions work; MCP server works |
| 5 | Trust features | Grounding 100%; profile confirmation; accuracy up vs week 3 |
| 6 | Ship | Langfuse traces, Docker, public demo link, README results table |
| later | Ideas parked | Walking routes, BTO, EIP quota, price trends chart, Telegram bot |

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

## Week 3: eval set and baseline
- [ ] `eval/questions.yaml`: about 68 questions as in docs/eval.md. Expected answers from code.
- [ ] `ask-hdb eval` runner: scores, steps, tokens, time. JSON + markdown report.
- [ ] Run LLM-only and single-agent conditions.
- **Exit:** a results table. **Gate:** if the agent does not clearly beat LLM-only,
  stop and find out why before adding anything.

## Week 4: places and MCP
- [ ] `scripts/geocode_blocks.py` with a disk cache. `scripts/fetch_places.py` for MRT and schools.
- [ ] `nearest(block_id, kind)` and a "within X km" filter for `find_sales`.
- [ ] Move all tools into an MCP server (`ask_hdb/mcp`). Agent connects through it.
- [ ] Add distance and multi-step questions to the eval.
- **Exit:** distance questions pass; same eval score through MCP as before.

## Week 5: trust features
- [ ] Profile worker + "Is this right?" confirmation before any eligibility tool runs.
- [ ] `grounding.py` number check, with one rewrite then an honest "I can't answer reliably".
- [ ] Supervisor + workers graph (profile, tools, answer).
- [ ] RAG over HDB policy pages for explanations, with links.
- [ ] Refusal handling for out-of-scope questions.
- **Exit:** grounding 100% on the eval; full condition beats single agent.

## Week 6: ship
- [ ] Langfuse tracing on every run.
- [ ] Streamlit chat page: chat on the left, tool results and sources on the right.
- [ ] Docker Compose: app, MCP server, Postgres + pgvector (Langfuse cloud free tier, or self-hosted).
- [ ] Deploy to one small VM with a cloud model (no GPU needed there).
- [ ] README: demo GIF, results table, architecture picture, "what I learned".
- **Exit:** a stranger uses the public link with no help.

## Decisions log
- 2026-10-19: Reddit shows COV/valuation is the top buyer worry. Added price check to v1.
- 2026-10-19: Project chosen. Resale only, v1 profiles: citizen families and singles 35+.
