# Week 2 plan: first agent

Draft 2026-10-20, waiting for approval. Exit check: 10 hand-written questions, 10/10
correct, or each miss written down with its cause. Nothing is built before approval.

## Steps
1. `llm.py`: one chat client chosen by `.env`: `LLM_PROVIDER` = `local` (default,
   llama-server on the 5090), `openai` or `anthropic`, plus `LLM_MODEL`, `LLM_BASE_URL`,
   `LLM_API_KEY`. The agent code never knows which one it is talking to.
   Note: a ChatGPT or Claude chat subscription does not include API access, and using its
   login in a third-party app is against their terms. So "connect your account" means the
   user pastes their own API key (billed separately). Keys stay in `.env`, never in the repo.
2. Tool-calling check: run 2 local models on 10 scripted tool-call prompts. Write down
   which one calls tools reliably (right tool, valid arguments) in `docs/week2-notes.md`.
3. `tools.py`: wrap the week 1 functions as tools (`price_stats`, `find_sales`,
   `compare_price`, `can_buy_resale`, `cpf_housing_grant`, `ehg_amount`, `phg_amount`,
   `max_loan`). Each returns plain JSON. Rule results keep their `rules` citations.
4. `agent.py`: one LangGraph ReAct agent over those tools. Hard limits per question:
   max 8 tool steps and a token budget. When hit, stop and say so (no silent loops).
5. `ask-hdb chat`: terminal loop. Prints each tool call and result, then the answer.
6. `eval/week2_questions.md`: 10 hand-written questions (price, grant, loan, eligibility,
   compare, one unanswerable). Expected answers computed in code, checked by eye.

## Decisions I need from you
- Which two local models to compare (suggest one ~30B and one ~8B, as in Whisperwick)?
- Is the 5090 PC reachable from this Mac (Tailscale)? If not, I use an API-key provider
  for week 2 only and flag it.
- The MacBook's models can also be used as `local` (same OpenAI-compatible interface).
- Decided 2026-10-20: 5090 is the default; OpenAI and Anthropic are optional via API key.

## Out of scope for week 2
- iOS / on-device models (Apple Foundation Models or a downloaded model): noted in the
  README as an idea. Revisit after the tool-calling check shows how small models do.

## Working rules
- Codex builds, this chat reviews every diff. Files under ~200 lines, short comments.
- The LLM never states a number. `grounding.py` (number-in-tool-result check) is week 3;
  in week 2 I check numbers by eye and write down any miss.
- `uv run pytest` and `uv run ruff check .` stay green. Tools get unit tests, no model needed.
