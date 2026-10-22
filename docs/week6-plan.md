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
| 6-6 Deploy | One small VM, cloud model (no GPU). Before choosing the model I run the dev eval on the candidate (a few dollars of API use) so the public demo is not worse than the 9B. | VM or host choice and account, API key in the server `.env`, a monthly spend cap |
| 6-7 README | Demo GIF, results table (9B and the cloud model), architecture picture, "what I learned". | nothing |

Order: 6-1, 6-2 (usable locally), 6-3, 6-5, 6-6 (public link), then 6-4 and 6-7. Tracing is last because it needs an account and is not needed for the exit check.

## Decisions I need
1. Cloud model for the public demo and a monthly cap (suggest the cheapest model that matches the 9B on the dev eval).
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
