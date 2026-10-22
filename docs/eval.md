# Evaluation: what "correct" means

The eval is the main portfolio evidence. Recruiters say evaluation is what separates
real AI engineers from demo builders, so it gets built in week 3, before the fancy parts.

## The eval set: `eval/questions.yaml`

The bank contains 68 questions: the original 50 plus 18 appended for week four.
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
| distance | 8 | independent spherical law of cosines on local block and place coordinates |
| multi_step | 16 | grant sums, filtered price differences and sale counts, comparable premiums and nearest MRT |
| bto | 14 | BTO eligibility verdicts, EHG amounts, launch facts and site distances |
| scenario | 7 | loan instalment, loan size, upfront cost, balance at MOP and illustrative sale scenarios, computed independently (month-by-month amortisation) |
| refuse | 8 (1 retired) | six active declines and one request for missing details: "will prices rise?", "should I buy now?", Executive Condominium questions, "worth $1 million?", "which loan makes more money?" |

- Questions are written by hand in plain language, with typos and vague wording on purpose.
- 30 questions are marked held out; the 67 development questions exclude them by default.
- The original 10 held-out questions remain marked, but are spent for tuning (see results).
  The 6 new held-out IDs were fixed before tuning: `q_distance_003`, `q_distance_006`,
  `q_distance_008`, `q_multi_step_002`, `q_multi_step_006`, `q_multi_step_010`.
  Six more (`q_multi_step_011` to `016`, added 2026-10-21) are held out from the start. They test the calculate tool and the
  required-but-nullable compare filters, which were fixed after the earlier held-out failures. Run them once.

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
3. **Full**: grounding check + profile confirmation (week 5 build; the supervisor graph was deferred, see `docs/week5-plan.md`).
   `--condition full` answers "yes" once to the code-written profile question; `--condition agent` never asks, so earlier agent
   reports stay comparable.

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

New distance and multi-step entries also have structured queries. Verify them offline with
`uv run --no-sync python scripts/build_distance_expected.py`; `--write` freezes numeric
leaves only. It shares local parquet inputs, but imports no application distance, sales,
comparison or rules functions. Distances use the spherical law of cosines with radius
6371.0088 km. Kilometre answers round to 2 decimals with inclusive tolerance 0.05;
counts and dollar answers are exact. Digits inside block IDs echoed from the question
are ignored for answer matching. Small expected values bypass the large-price filter.
Each multi-step case needs at least two tool calls: separate grant tools, two town
statistics, or separate comparable samples followed by a nearest-place lookup.
All sales windows have explicit end months; ungeocoded blocks are excluded from geo filters.
The grant sums cite YAML keys and show hand arithmetic beside the entries. No loan
estimate is included. The existing question entries and their order remain frozen.

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
An answer with no scored numbers has a vacuous rate of one; answer accuracy and errors must be read alongside grounding.
Since week 5 (2026-10-22) the column uses `ask_hdb.grounding.check`, the same check the agent enforces; its rules are at
the top of `src/ask_hdb/grounding.py` (labels such as years and flat types are skipped, written decimals may round the tool
value, tool errors are not evidence). Grounding figures before that date used the older check; rescore to compare.
After the PR #45 review the check became stricter: digits inside tool strings (sentences, IDs, sources, as_of dates)
are no longer evidence, a year is skipped only after a date word with no money word nearby, and a day date must match an
ISO date in a tool result. Known limit: numbers from the question may be restated; one placed right after a threshold
word ("minimum", "at least", "ceiling") is not treated as an echo, but other phrasings can still present a user's number as a rule.

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


## Week 4b additions (2026-10-21)
- 14 `bto` questions (`q_bto_001` to `014`): 6 eligibility verdicts (hand-derived from `rules/bto/2026-10.yaml`), 2 EHG amounts (HDB EHG tables), 4 launch facts
  (read by hand from HDB's Annex A tables and checked against the parsed table), 2 distances (independent spherical law of cosines on approximate sites).
  Held out from the start: `q_bto_004`, `006`, `011`, `012`, `014`. `scripts/build_bto_expected.py` verifies the launch and distance answers.
- `q_refuse_003` ("How do I apply for a BTO flat?") is **retired** (`retired: true`, kept in the file so old results keep their meaning, never run again) because BTO is now in
  scope. `q_refuse_006` ("How do I apply for an Executive Condominium?") replaces it. The refuse set stays at 5 active questions.
