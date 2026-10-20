# Week 3 plan: eval set and baseline

Draft 2026-10-20, waiting for approval. Exit check: a results table for two conditions
(LLM-only, single agent). Gate: if the agent does not clearly beat LLM-only, stop and find out why.

## Steps
1. `eval/questions.yaml`: 50 questions now (price 15, eligibility 12, grants 10, price check 8,
   refuse 5). The 8 distance and 10 multi-step questions need places data, so they are added in
   week 4 (the roadmap already says so). Plain wording, some typos and vague phrasing.
2. Expected answers come from code or HDB text, never from the agent:
   - price and price check: `scripts/build_expected.py` runs pandas directly on the clean data.
   - eligibility and grants: HDB's worked examples plus amounts read by hand from the HDB tables
     (cited in the yaml). I check each one; the rule functions are not used to make their own answers.
   - refuse: must decline, no tool call needed.
3. Hold out 10 questions (`heldout: true`). They are never run while tuning prompts.
4. `ask-hdb eval` runner (replaces the week 2 routing check): `--condition llm-only|agent`,
   `--only <kind>`, `--verbose`. Per question: answer, tool calls, steps, tokens, seconds.
   Writes `eval/reports/<date>-<condition>.json` and a markdown table.
5. Scoring, all in code:
   - number questions: the expected number appears in the answer (within the stated tolerance).
   - verdict questions: the answer says yes/no as expected (keyword list per question), and the
     tool result holds the expected verdict.
   - refuse questions: no tool call and a decline phrase.
   - grounding rate: share of numbers in the answer found in that turn's tool results (a simple
     check; the full `grounding.py` is week 5).
   - steps, tokens, seconds: median and p90.
6. Run both conditions on the MacBook model (`qwen3.5-9b-16k`). About 25 minutes each, in the background.
7. `docs/eval-results.md`: the table, plus every failed question written down with its cause
   before any prompt is changed. Add the table to the README.

## Decisions for you
- OK to write 50 questions now and add the 18 distance and multi-step ones in week 4?
- OK that the tables use only the 9B Mac model for now? The 5090 is not touched until you say.
  When you say so, I rerun the same questions on the 27B and add a column.

## Working rules
- Codex drafts the questions and runner; this chat checks every expected answer by hand and reviews the diff.
- Expected answers are frozen once written. A failed question is a finding, not a reason to edit the answer.
- `uv run pytest` and `uv run ruff check .` stay green. Scoring functions get unit tests, no model needed.
