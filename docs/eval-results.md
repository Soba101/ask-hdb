# Week 3 results (2026-10-20)

Model: `qwen3.5-9b-16k` on the MacBook (Ollama, thinking off), same for both conditions.
40 questions per condition (the 10 held-out questions were not run). Expected answers are frozen.
Reports: `eval/reports/2026-10-20-llm-only.json`, `eval/reports/2026-10-20-agent.json` (git-ignored; rerun with `uv run ask-hdb eval --condition ...`).

| Condition | Number accuracy | Verdict accuracy | Refusal accuracy | Grounding | Errors | Steps median | Tokens median / p90 | Seconds median / p90 |
|---|---|---|---|---|---|---|---|---|
| LLM only | 0.0% | 10.0% | 0.0% | 0.0% | 8 (timeouts) | 0 | 727 / 1,227 | 118 / 180 |
| Single agent | 92.3% | 40.0% | 50.0% | 85.7% | 0 | 1 | 8,384 / 9,123 | 52 / 68 |

Bars from `docs/eval.md`: verdict 95%, number 90%, grounding 100%, refusal 5/5.
Only numbers pass the bar. **Gate:** the agent clearly beats LLM-only on numbers (92% vs 0%) and
refusals (50% vs 0%); verdicts are 40% vs 10% but far below the 95% bar. Causes found below.

Rescored 2026-10-20: an Opus review found false passes in the first scoring code (decline phrases matched ordinary
prose, a "yes" passed on answers saying "No", any number in an answer could pass). The scoring was fixed and the
saved answers rescored offline (`scripts/rescore.py`, no model run). First-pass scores were LLM-only 15/30/50/0 and
agent 92/40/75/69; the table above is the corrected one.

## LLM-only
- Every price question that did not time out was wrong: with no tools the model invents prices.
- 8 questions hit the 180 s timeout (a 9B model writing long reasoning without tools). Of 40 questions only 1 passes.
- Refusal 0%: it answered "will prices rise", "should I buy now", the BTO question and "predict my price" instead of declining.

## Single agent: every failure and its cause (10 of 40)
| Question | What happened | Cause |
|---|---|---|
| q_eligibility_005, 006, 007, 008, 012 | Tool returned an error; the model said it could not decide | The model sent both `first_timer` AND `family_timers` for a single buyer. The profile check rejects that mix. Model fills mutually exclusive fields. |
| q_eligibility_009 | Said "eligible" although the tool said `eligible: null` | Model omitted `marital_status`; the tool asked for it; the model ignored the unresolved check and stated a verdict. |
| q_grants_002 | Said EHG is $0 | Model omitted `family_timers`; tool returned `needs_check`; the model reported $0 instead of retrying with the field. |
| q_grants_006 | Said EHG $40,000, expected $0 | Model omitted `works_12_months=false`. The profile defaults it to true, so the tool silently answered for the wrong person. **Most serious: a wrong answer with no flag.** |
| q_refuse_002 | "Should I buy now or wait": said it could not decide without more details and offered to analyse | Prompt does not say to decline investment-timing advice; the model asked for details instead of declining. |
| q_refuse_003 | Gave generic BTO steps | Prompt says not to answer BTO questions; the model partly did anyway . |

Grounding 85.7% after the fix. (The first scorer counted "1." "2." list markers as numbers, which made it look like 69%.)
The remaining unsupported numbers are not yet individually reviewed.

## What this means
- Price and price-check numbers are solid with tools (every price and price-check question passed, 92% number accuracy overall).
- The weak spot is the profile tools: a 9B model drops optional fields, mixes exclusive ones, or ignores `needs_check`.
- The 27B on the 5090 is untested, by your instruction. It may do better; this table is the 9B only.

## Proposed fixes (not done; each needs your OK, then a rerun of the same 40 questions)
1. Code: tool wrapper drops the field that does not apply (`family_timers` for singles, `first_timer` for families).
2. Code: no unsafe defaults. Make `works_12_months`, `owns_private_property` and `previous_hdb_loans`
   required on the profile tools, so a missing value comes back as "ask the user", not a silent guess.
3. Code: if a tool returns `eligible: null`, the agent must ask for the missing field (a retry), not state a verdict.
4. Prompt: one line on BTO and decline cases.
