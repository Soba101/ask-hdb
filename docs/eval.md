# Evaluation: what "correct" means

The eval is the main portfolio evidence. Recruiters say evaluation is what separates
real AI engineers from demo builders, so it gets built in week 3, before the fancy parts.

## The eval set: `eval/questions.yaml`

About 68 questions. Each has an exact expected answer that code can check.

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
| refuse | 5 | must decline: "will prices rise?", "should I buy now?", BTO questions |

- Questions are written by hand in plain language, with typos and vague wording on purpose.
- 10 questions are held out and never looked at while tuning prompts.

## Measures

| Measure | How | Bar |
|---|---|---|
| Verdict accuracy | eligibility and grant answers match | ≥ 95% |
| Number accuracy | price and distance within tolerance | ≥ 90% |
| Grounding rate | numbers in replies found in tool results | 100% |
| Refusal accuracy | declines out-of-scope questions politely | 5 / 5 |
| Steps | tool calls per question | report median, watch for loops |
| Cost and latency | tokens and seconds per question | report median and p90 |

## Conditions to compare (same questions, same model)
1. **LLM only**: no tools, just the question. Shows why tools matter.
2. **Single agent**: one ReAct agent with all tools (week 2 build).
3. **Full**: supervisor + workers + grounding check + profile confirmation (week 5 build).

The README shows one table: these three conditions against the measures above.

## How to run (planned)

```bash
uv run ask-hdb eval                           # full condition, all questions
uv run ask-hdb eval --condition llm-only      # baseline
uv run ask-hdb eval --only price --verbose    # one kind, show each answer
```

Results go to `eval/reports/<date>-<condition>.json`, plus a short markdown table.

## Rules for the eval
- Expected answers are never produced by the agent. Only by code or HDB's own text.
- When rules change, the eval's expected answers are regenerated from the new rules file.
- A failed question is a finding. Write it down before changing any prompt.
