# Week 3 results (2026-10-20)

Model: `qwen3.5-9b-16k` on the MacBook (Ollama, thinking off), same for both conditions.
40 questions per condition (the 10 held-out questions were not run). Expected answers are frozen.
Reports: `eval/reports/2026-10-20-llm-only.json`, `eval/reports/2026-10-20-agent.json` (git-ignored; rerun with `uv run ask-hdb eval --condition ...`).

| Condition | Number accuracy | Verdict accuracy | Refusal accuracy | Grounding | Errors | Steps median | Tokens median / p90 | Seconds median / p90 |
|---|---|---|---|---|---|---|---|---|
| LLM only | 0.0% | 10.0% | 0.0% | 0.0% | 8 (timeouts) | 0 | 727 / 1,227 | 118 / 180 |
| Single agent (first run, before fixes) | 92.3% | 40.0% | 50.0% | 85.7% | 0 | 1 | 8,384 / 9,123 | 52 / 68 |

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

## Fix rounds (same 40 dev questions, same 9B model, all rescored with the final scorer)
| Run | Change | Pass | Number | Verdict | Refusal | Grounding |
|---|---|---|---|---|---|---|
| 0 baseline | none | 30/40 | 92.3% | 40.0% | 50.0% | 85.7% |
| 1 | drop the inapplicable timer field; three profile fields get no default; prompt lines | 34/40 | 96.2% | 50.0% | 100.0% | 78.6% |
| 2 | tool errors when a single has no `marital_status` | **30/40** | 88.5% | **30.0%** | 100.0% | 88.5% |
| 3 | `marital_status` and `family_timers` become required schema fields | 39/40 | 96.2% | 100.0% | 100.0% | 78.5% |
| 4 | `first_timer` becomes a required schema field | 39/40 | 100.0% | 90.0% | 100.0% | 76.5% |

Run 2 was a regression and is kept on purpose. Returning an error for a missing field did not work: the
9B model never sent `marital_status` when it was optional, then asked the user for what they had already said.
What worked (run 3) was making the field required in the tool schema: **this model fills required fields and
skips optional ones.** Three live spot-checks showed it then copied the value from the question correctly.
Scorer corrections made along the way (all found by reading failed answers whose content was right): small
numbers and years are ignored when the expected answer is 10,000 or more, more decline wordings, and clarify
answers may mention small numbers. Reports for every run are kept in `eval/reports/` (git-ignored).

## Held-out questions (10, run once, after the fixes)
9 of 10 pass (8 of 10 as first scored; `q_refuse_005` was a scorer false fail on a correct clarifying
answer, fixed afterwards, so treat 9/10 as slightly optimistic). The miss is `q_eligibility_004`: the model
left out `category` (Standard/Plus/Prime), the tool returned `eligible: null`, and the model said it could not decide.
Same family of failure as before. **The held-out set is now spent for tuning purposes** (a fix for that failure
would be tuned on it); new questions in week 4 are the next clean test.

## Final dev run vs LLM-only (40 questions)
| Condition | Number | Verdict | Refusal | Grounding |
|---|---|---|---|---|
| LLM only | 0.0% | 10.0% | 0.0% | 0.0% |
| Single agent (run 4) | 100.0% | 90.0% | 100.0% | 76.5% |

Against the bars in `docs/eval.md`: number (90%) and refusal (5/5) pass; verdict (95%) is just under on the dev set
(it missed `q_eligibility_012`) and grounding (100%) is far off.
The agent clearly beats LLM-only, so the gate is cleared.

## What is still open
1. Grounding 76.5%: the simple check counts numbers in the answer that no tool returned (rule thresholds the model
   adds from memory, restated question numbers, list numbering variants). Not yet reviewed one by one; `grounding.py`
   with a rewrite step is week 5.
2. The model still misreads `eligible: null` / omits optional fields (`category`, `price`). Candidate fix: make `category`
   required with an `unknown` option. Not done, because the held-out set is spent.
3. These numbers are for the 9B model only. The 27B on the 5090 is untested until you say.
