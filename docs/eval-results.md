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

Against the bars in `docs/eval.md`: number (90%) and refusal (5/5) pass; verdict (95%) is under on the dev set (90% vs 95%; held-out verdict 1 of 2 on its two eligibility questions)
(it missed `q_eligibility_012`) and grounding (100%) is far off.
The agent clearly beats LLM-only, so the gate is cleared.

## What is still open
1. Grounding 76.5%: the simple check counts numbers in the answer that no tool returned (rule thresholds the model
   adds from memory, restated question numbers, list numbering variants). Not yet reviewed one by one; `grounding.py`
   with a rewrite step is week 5.
2. The model still misreads `eligible: null` / omits optional fields (`category`, `price`). Candidate fix: make `category`
   required with an `unknown` option. Not done, because the held-out set is spent.
3. These numbers are for the 9B model only. The 27B on the 5090 is untested until you say.

# Week 4 results (2026-10-21): distance, multi-step, direct tools vs MCP

Same 9B model on the MacBook, 52 dev questions (the 40 from week 3 plus 12 new: 5 distance, 7 multi-step). The 6 new held-out
questions are not in these numbers. All runs scored with the final scorer (`scripts/rescore.py`).

| Run | Tools | Pass | Number | Verdict | Refusal | Grounding | Seconds median / p90 |
|---|---|---|---|---|---|---|---|
| 1 (before fixes) | direct | 47/52 | 86.8% | 100% | 100% | 75.8% | 63 / 125 |
| 1 (before fixes) | MCP | 49/52 | 92.1% | 100% | 100% | 77.8% | 39 / 64 |
| 2 (after fixes) | direct | 50/52 | 97.4% | 90.0% | 100% | 74.3% | 53 / 91 |
| 2 (after fixes) | MCP | 51/52 | 97.4% | 100% | 100% | 74.1% | 46 / 101 |

Pass counts by kind, run 2 (direct / MCP): price 12/12 both, eligibility 9/10 and 10/10, grants 8/8 both, price check 6/6 both,
refuse 4/4 both, distance 5/5 both, multi-step 6/7 both.

**Week 4 exit check:** distance questions pass (5/5), and MCP scores the same as direct (97.4% number both; 51 vs 50 passes, the
difference is one timeout). Gate met.

## What changed between run 1 and run 2
1. `compare_price` `as_of` became a required field (value `latest` means newest month). In run 1 the model left it out on three
   price-check questions, so the comparison window ended one month late and the median was wrong. Price check went from 3/6 (direct) to 6/6.
2. The scorer now also accepts the result after the last "=" in a worked line ("638888 - 590000 = 48888"). Four correct answers had been
   marked wrong because the first number was an intermediate value.
3. One prompt line: call the tool once for each town, block or place in the question. Fixes the two-town count question (`q_multi_step_005`).

## Every failure in run 2
| Question | Run | What happened | Cause |
|---|---|---|---|
| q_eligibility_001 | direct | Timeout, no answer | OpenAITimeoutError at 180 s; the MacBook model was slow on that call. Infrastructure, not a wrong answer. |
| q_multi_step_009 | direct and MCP | Premium difference -72,000, expected 27,000 | The model left out `lease_left_months` in both `compare_price` calls, so no lease filter was applied and the medians were wrong (625,000 and 523,000 instead of 529,000 and 526,000). Same pattern again: **the 9B model skips optional fields.** |

## Findings
- The 9B model skips optional tool fields: `category`, `price`, `as_of`, now `lease_left_months`. Making a field required with an escape value fixed
  each one so far. Candidate next step: make the optional filters on `compare_price` (`storey_mid`, `lease_left_months`, `floor_area_sqm`) required
  but nullable, so the model must write a value or null. Not done yet.
- Scorer needs the same care as the agent: it gave false passes in week 3 and false fails on worked equations in week 4.
- MCP matches direct tools. A faster median through MCP in run 1 was noise (different load on the Mac).
- Grounding is still about 74%; the number-in-tool-result check counts intermediate and rounded numbers. Real fix is `grounding.py` (week 5).
- Geocoding: 9,456 of 9,496 recent blocks found (99.6%); 21 uncertain and 19 not found (mostly Towner Rd and St. George's Rd). Cross-check against HDB
  building outlines: median 8.5 m, worst 79 m. All 182 primary schools located.

## Held-out (6 new questions)
To be run once, after this section is committed. Results below.
