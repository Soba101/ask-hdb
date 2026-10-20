# Evaluation: what "correct" means

The eval is the main portfolio evidence. Recruiters say evaluation is what separates
real AI engineers from demo builders, so it gets built in week 3, before the fancy parts.

## The eval set: `eval/questions.yaml`

The week-three bank contains 50 questions. The planned total is 68 after week four.
Each has a frozen expected answer that code can check.

```yaml
- id: q_price_001
  kind: price
  question: "What was the median price of 4-room flats in Tampines in 2025?"
  expect:
    number: 585000          # computed by pandas directly, NOT by the agent
    tolerance: 0            # exact
  source: "data/clean/resale.parquet, filter town=TAMPINES flat_type=4 ROOM year=2025"
```

| Kind | Count | Expected answer comes from |
|---|---|---|
| price | 15 | pandas directly on the clean data |
| eligibility | 12 | HDB's own worked examples and rule tables |
| grants | 10 | HDB grant tables (amount by income tier) |
| price check | 8 | comparable sales picked by code (same block/street, storey band, lease band) |
| distance | 8 | haversine on our geo index |
| multi-step | 10 | combination of the above (e.g. budget + grant + MRT distance) |
| refuse | 5 | four declines and one request for missing details: "will prices rise?", "should I buy now?", BTO questions |

- Questions are written by hand in plain language, with typos and vague wording on purpose.
- 10 questions are held out and never looked at while tuning prompts.

## Measures

| Measure | How | Bar |
|---|---|---|
| Verdict accuracy | eligibility and grant answers match | ≥ 95% |
| Number accuracy | price and distance within tolerance | ≥ 90% |
| Grounding rate | numbers in replies found in tool results | 100% |
| Refusal accuracy | declines out-of-scope requests or asks for missing details | 5 / 5 |
| Steps | tool calls per question | report median, watch for loops |
| Cost and latency | tokens and seconds per question | report median and p90 |

## Conditions to compare (same questions, same model)
1. **LLM only**: no tools, just the question. Shows why tools matter.
2. **Single agent**: one ReAct agent with all tools (week 2 build).
3. **Full**: supervisor + workers + grounding check + profile confirmation (week 5 build).

The README shows one table: these three conditions against the measures above.

## How to run

```bash
uv run --no-sync ask-hdb eval                         # agent, development split
uv run --no-sync ask-hdb eval --condition llm-only    # baseline, same model factory
uv run --no-sync ask-hdb eval --only price --verbose  # one kind, show each record
uv run --no-sync ask-hdb eval --heldout --limit 50    # explicitly include held-out questions
uv run --no-sync ask-hdb routing                     # previous routing check
```

Results go to `eval/reports/<date>-<condition>.json`, plus a short markdown table.

## Rules for the eval
- Expected answers are never produced by the agent. Only by code or HDB's own text.
- When rules change, the eval's expected answers are regenerated from the new rules file.
- A failed question is a finding. Write it down before changing any prompt.

## Frozen inputs and report semantics

`eval/questions.yaml` uses `expect.number` plus an absolute, inclusive `tolerance`,
`expect.verdict` (`yes`/`no`) plus `answer_keywords`, `expect.decline: true`, or `expect.clarify: true`.
Numeric grant answers are scored as numbers; eligibility answers are scored as verdicts.
For numeric accuracy, the first number absent from the question must match within tolerance;
a later correct number (even a bold final answer) cannot rescue an earlier guess or range.
Ordered-list labels, including labels under bullets, are ignored. Purchase verdict matching
ignores Markdown emphasis and code markers. Purchase denials fail affirmative expectations
unless clearly about grants, loans, EHG or CPF. Only `can_buy_resale` results supply tool
eligibility evidence; grant-tool eligibility is not purchase evidence.
Declines require a request-specific refusal phrase and no tool calls. Clarifications require
a request for details, no stated number or verdict, and no tool result with an eligibility
verdict. The clarification case remains in the refuse kind and held-out split.
Each entry cites its independent source. Rule arithmetic is in adjacent YAML comments.
Price entries also have a structured `query` so the independent builder can reproduce them.

Run `uv run --no-sync python scripts/build_expected.py` to verify the numeric price
expectations. It reads the parquet directly without importing the sales or compare tools.
`--write` explicitly freezes new values; do not use it to fix an agent failure.
Every query has an end month. Comparable questions use the final twelve inclusive months,
the same flat type, inclusive storey midpoint and lease bands, then the first sufficient
block, street within town, or town sample. No area filter is applied in these questions.
If all levels are thin, keep the town sample. Median prices round to the nearest dollar,
ties to even. The asking price is stated but is not the expected comparable median.

The runner sends each question as a fresh turn. The baseline uses the same model factory,
no tools, and only the system instruction "Answer the question." Steps count completed
tool calls. Tokens use reported usage (the unchanged agent retains its budget fallback);
missing baseline usage is `null`, not zero. Seconds include the attempted request.
Provider and factory errors, or agent budget stops, always fail the question.

Grounding is the micro-average of supported numeric occurrences across answers. Numbers
present in the question are excluded. Evidence comes only from the current turn's tool
results, never tool arguments or earlier turns. Commas, decimal values, `k`
and `million` are understood. Bare `m` and `km` units do not scale numbers.
An answer with no scored numbers has a vacuous rate of one; answer accuracy and errors must be read alongside grounding. This simple checker does not
alter or replace the agent's planned grounding enforcement.

Median and p90 use all recorded observations; missing token values are excluded from the
token distribution. P90 uses linear interpolation between sorted observations.
A score with no applicable questions is `null` / `n/a`.

Each report contains cumulative `results`, an `active_ids` selection, and a history of run
selections. Its summary and Markdown table cover only the active selection, so a prior
held-out run cannot enter a later development score. JSON and Markdown are each replaced
atomically after every question; JSON is authoritative if interrupted between replacements.
On resume the runner prints every retained result, including errors. It rejects changed
question fingerprints or model settings. Archive the dated report to retry recorded failures
or run a fresh comparison. Keep model configuration and the data snapshot fixed between
conditions. Do not run concurrent writers to the same dated condition report.

Failures appear in the report's Markdown table with an exception type, stop reason or a
frozen-expectation mismatch. Review each answer and tool record to diagnose the cause before
changing prompts. The baseline and single-agent comparison were run; see
`docs/eval-results.md`. Those recorded scores predate the scoring fixes.

Rescore saved reports offline with
`uv run --no-sync python scripts/rescore.py eval/reports/<date>-<condition>.json`.
This writes sibling `.rescored.json` and `.rescored.md` files and prints the summary.
It uses each row's stored question text, expectation, answer and tool calls, without loading
the current question bank or calling a model. Original reports remain unchanged. A stored
expectation remains historical, including older decline expectations for clarification cases.
Markdown reports show seconds to one decimal place; JSON retains full precision.
