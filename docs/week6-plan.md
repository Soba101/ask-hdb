# Week 6 plan: web app, tracing, ship (draft, needs approval)

Goal (roadmap exit check): a stranger uses the public link with no help.
Starting point: the agent and tools work in the terminal (`ask-hdb chat`); `agent.ask(question, history, confirm=True)` returns the answer, tool calls and tool results after the whole run. Nothing is stored by the agent; the confirmation step already works from chat history alone, so the server can stay stateless.

## Phases (each gets approval before it is built)

| Phase | What | Needs from you |
|---|---|---|
| 6-1 API | FastAPI app. `POST /chat` takes the question and the history the browser holds, streams events (tool call, tool result, confirmation question, answer) as server-sent events. `GET /health`. Small change in `agent.py`: an optional callback that reports each tool call and result as it happens (today they only come back at the end). Guards: rate limit per visitor, a daily token/cost cap, request size limit, no storage of questions, answers or profiles, a "not financial advice" line in every response. | nothing |
| 6-2 Front end | One static page, no build step (plain JS): chat on the left, tool results and sources (rule `source` and `as_of`) on the right, the confirmation question shown as buttons. Runs locally against the API with the Mac model first. | nothing |
| 6-3 Map | MapLibre panel. Step 1: 2D markers for the blocks, MRT stations, schools and BTO sites that appear in tool results. Step 2: 3D blocks, extruded by the highest storey seen in the sales data for that block (approximate, say so on the map). Building footprints need the data.gov.sg "HDB Existing Buildings" outlines. | OK to download that official dataset |
| 6-4 Tracing | Langfuse via the LangChain callback, switched on only when keys are set. Traces would contain visitor questions, so the public demo either redacts them or keeps tracing off for visitors (my suggestion: trace metadata only, no text). | a Langfuse account and keys, or skip tracing for now |
| 6-5 Docker | Compose file for the app (the MCP server stays an internal subprocess, `TOOL_SOURCE=direct` is the default). The 5 MB of clean data is git-ignored, so the image build copies it in; a short build note says how to regenerate it from the scripts. | nothing |
| 6-6 Deploy | One small VM. The VM cannot reach the Mac's Ollama, so a public link needs a hosted model: set the three `.env` values and run the dev eval on it first (a few dollars of API use) so the demo is not worse than the 9B. Until then the app runs locally. | VM or host choice and account, API key in the server `.env`, a monthly spend cap |
| 6-7 README | Demo GIF, results table (9B and the cloud model), architecture picture, "what I learned". | nothing |

Order: 6-1, 6-2 (usable locally), 6-3, 6-5, 6-6 (public link), then 6-4 and 6-7. Tracing is last because it needs an account and is not needed for the exit check.

## Decisions I need
1. Model: build and test everything with the local model (`LLM_PROVIDER=local`). The model is a setting (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`), so a cloud model later is an `.env` change, not new code. The cloud model, its key and a monthly cap are only needed at 6-6.
2. Hosting: a small VM you own, or build and test locally only until you pick one.
3. Tracing: Langfuse cloud free tier, self-hosted, or skip for now; and whether traces may hold question text.
4. 3D map: OK to download the HDB Existing Buildings outlines (official, data.gov.sg)?
5. Front end: plain JS as above (my suggestion, nothing to build or maintain) or a framework.

## Risks and limits
- The 9B takes about a minute per answer on the Mac; the public demo must use a cloud model, so answers can differ from the numbers in `docs/eval-results.md` until the eval is run on it.
- Public visitors can try prompt injection and cost abuse: tool output is data, not instructions, and the guards above (rate limit, cost cap, size limit) are part of 6-1, not later.
- 3D height is "highest storey seen in sales", not the real building height; the map says so. Issue #19 (no floors source) stays open.
- Nothing about a visitor is stored. Logs hold request counts and errors only.
- Open items carried over: failing questions (q_multi_step_005, q_scenario_002, q_refuse_008, q_grants_010), issue #49, deferred supervisor graph and RAG.

## Re-scope 2026-10-23: map-first (Opus consult)
The owner wants the map to be the main view with the chat beside it: click or ask about a block, estate or place, and the chat answers and shows it on the map (nearest primary school from a block, travel time to town), built for people buying HDB flats.
- **A (done, PR week6-4a):** map-first page with every block, MRT/LRT station, primary school and BTO site; click to select; an info card made by code (lease, recent median, nearest school and MRT, blocks within 1 km); the selection goes to the agent as one code-written line ("this block" means it); map highlights and fly-to come from a `map` event built from tool results. No new tools.
- **B (next, needs no decision):** `resolve_place` (blocks, streets, MRT, schools, BTO from local data, ambiguity as clickable choices), `nearby` covering blocks, estates and BTO projects; about 25 new eval questions; keep the tool count at 17-18 for the 9B.
- **C (needs the owner):** travel time to town. Plan: one-time batch of OneMap public-transport routes from each block to Raffles Place (weekday 08:30), stored with the date and shown as "about N min, OneMap". Needs: approval for about 9,500 calls with the OneMap login, confirmation that OneMap's terms allow storing route results, and whether "town" is Raffles Place only. Until then only a labelled walk-to-MRT estimate.
- **Cut for now:** 3D, free destinations, live routing per visitor, vector tiles.

## Status 2026-10-24
Done and merged: 6-1 API (PR #52), 6-2 front end (#53), 6-3 2D map (#54), phase A map-first page (#55), phase B place lookup, radius ring, schools within 2 km with 1 km / 2 km rings, 18 map eval questions (#56).
Not started: price and lease layers, trend chart, shortlist and compare, eligibility form, Docker, tracing (Langfuse), deploy with a cloud model, README, travel time to town (needs the owner's decision on OneMap routing), 3D (owner decides after using the 2D map).

Update 2026-10-23: price and lease layers (PR #57), Docker, optional tracing and README (PR #58) merged. Left: public deploy (host, cloud model, key, dev eval on that model), live Langfuse check (account and keys), 3D (owner's call), travel time (OneMap routing decision), trend chart, shortlist and compare, eligibility form.
