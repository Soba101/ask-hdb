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
difference is one timeout). Gate met for distance and MCP parity. **Not yet compliant for multi-step:** 6 of the 7 multi-step dev passes rely on
the model doing its own subtraction or addition ("638888 - 590000 = 48888"), so the final number is in no tool result. Fix: the calculate tool (issue 32).

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

## Held-out (6 new questions, run once)
4 of 6 pass. The 10 older held-out questions (spent in week 3) were run again on the same code: 10 of 10 pass. Full 68-question
report (direct tools): 94.1% number, 91.7% verdict, 100% refusal, 70.5% grounding.

| Question | Held out | Result | Cause |
|---|---|---|---|
| q_distance_003, 006, 008 | new | pass | Distance and count questions: right tool, right arguments. |
| q_multi_step_006 | new | pass | Punggol vs Sengkang median gap with MRT filter. |
| q_multi_step_002 | new | FAIL: said 280,000, expected 180,000 | **The model added the numbers wrong.** The tools returned 80,000 + 70,000 + 30,000 correctly. This breaks the core rule: arithmetic must be done by code, not by the LLM. |
| q_multi_step_010 | new | FAIL: said 0.97 km, expected 0.74 km | The model left out `lease_left_months` in both `compare_price` calls, so it picked the wrong block as the one with the higher premium. Same optional-field pattern as q_multi_step_009. |

Two proposed fixes, not yet done (so this held-out result stays clean):
1. A `calculate` tool (safe arithmetic on numbers from earlier tool results) plus a prompt rule: never add, subtract or compare numbers yourself.
   This also makes the grounding check pass for derived numbers.
2. Make `storey_mid`, `lease_left_months` and `floor_area_sqm` on `compare_price` required but nullable.

## Data fixes after review (2026-10-21)
An Opus review of PR 8 found two data problems. Both are corrected; none of the model runs above were redone except the one question that changed.
1. **LRT stations were counted as MRT** (41 exits in Punggol, Sengkang, Bukit Panjang, Choa Chu Kang). They are now a separate kind `lrt`
   (147 MRT stations, 41 LRT). This changes the nearest MRT for 1,735 blocks. Of the 18 new questions only held-out `q_multi_step_006`
   (Punggol median minus Sengkang median) changes: expected 40,556 with LRT, **50,000 MRT-only**. This is a data fix, not tuning. The agent was
   rerun once on that question after the fix and answers 50,000 (pass). The recorded held-out pass earlier was against the wrong expected value.
2. **"ST." (saint) was read as STREET**, leaving 21 St. George's Rd and Lane blocks "uncertain". Fixed offline (no new OneMap calls):
   9,477 blocks found, 0 uncertain, 19 not found.
Also: distance filters now report `sales_without_coordinates` (sales in blocks with no coordinates are left out of a "within X km" filter),
`nearest_places` says "No coordinates for block_id" instead of "Unknown block_id", `as_of="latest"` is case-insensitive, and the scorer filters
small numbers and years on negative expected answers too.

# Week 4 fixes (2026-10-21): calculate tool, required-but-nullable filters, 27B on the 5090

Fixes for issues 32 (the model added numbers wrongly) and 33 (the model skipped `lease_left_months`): a `calculate` tool plus a prompt rule, and
`storey_mid`, `lease_left_months`, `floor_area_sqm` on `compare_price` made required but nullable. Also: every one of the 19 blocks OneMap could not find
now has coordinates (issue 34), and the MCP subprocess gets a safe environment (issue 35).

## 9B model on the MacBook (direct tools)
| Run | Questions | Pass | Number | Notes |
|---|---|---|---|---|
| Week 4 (before these fixes) | 52 dev | 50/52 | 97.4% | direct; failures were q_eligibility_001 (timeout) and q_multi_step_009 (omitted lease filter) |
| Try 1 (nullable fields, no text fix) | 51 of 52 done | 47/51 | 89.2% | **Regression:** price check fell from 6/6 to 3/6 |
| Try 2 (final) | 52 dev | 51/52 | 97.4% | only miss: q_distance_005 (scorer limit, see below) |
| Try 2 held-out, older 16 | 16 | 16/16 | | includes the q_multi_step_002 and 010 that failed before |
| Try 2 held-out, **6 new (011 to 016)** | 6 | **6/6** | | clean test: written before the fixes, run once |
| Try 2, all 74 questions | 74 | | 98.2% number, 100% verdict, 100% refusal, 70.8% grounding | |

**Try 1 regression, cause:** the model wrote the text `"None"` for `floor_area_sqm` (and for `max_examples`), which failed validation, so it gave up on the tool
and asked the user. Fix: in every tool, the text "None" or "null" now means null for a required-nullable field and "use the default" for any other optional field.
**What the fixes did:** q_multi_step_002 (added 80,000 + 70,000 + 30,000 as 280,000) now passes through `calculate`; the multi-step dev questions are 7/7 with no
model arithmetic needed. This resolves issue 32 for these questions. Grounding is still about 71%; I have not yet analysed which numbers are unsupported
(week 5, `grounding.py`).
**Known scorer limit (not weakened):** q_distance_005's answer is right ("only 2 primary schools") but lists three distances first and the first-number rule reads
0.056. A "last number" rule was tried and rejected: it broke 10 tests that guard against false passes.

## MCP parity (9B, 52 dev questions)
Through MCP: 51/52, the same single miss as direct (q_distance_005, scorer limit). MCP matches direct after the fixes, including the new `calculate` tool and nullable fields.

## 27B model on the 5090 (qwen3.8:27b, llama-server)
Approved by the user on 2026-10-21 after coordinating with the Whisperwick session. One call at a time, nothing changed on the PC.
The server has 4 slots of 8,192 tokens, and our first request is 6,664 tokens (10 tools of schema). Setup: tool schemas without repeated `title` keys,
replies capped at 1,200 tokens, `find_sales` limited to 5 rows and `compare_price` to 3 examples (`LLM_COMPACT_TOOLS=1`). Same questions, same scorer.

| Set | Pass | Notes |
|---|---|---|
| 52 dev | 50/52 | 94.7% number, 100% verdict, 100% refusal, 0 errors |
| older 16 held-out | 15/16 | |
| new 6 held-out | 4/6 | |
| all 74 | | 91.2% number, 100% verdict, 100% refusal, 76.3% grounding, 2 errors |

Failures (5 questions, all multi-step counts and grant sums):
- q_multi_step_005, 007 (dev) and 014 (held-out): the model counted rows from `find_sales` (capped at 5 per town by my compact setting) and answered 10, instead
  of reading `n_sales` from `price_stats`. **Mostly my setup:** the cap hides the real rows. Partly the model's tool choice.
- q_multi_step_002 and 012 (held-out grant sums with parents): the request was rejected (OpenAIInvalidRequestError) on the first call, with no tool call made.
  Cause not verified; the likely reason is the 8k per-slot context, since both questions are long. Counted as failures.
So the 27B number is not a fair comparison with the 9B: it ran under a tighter context and a different tool setup. A clean comparison needs a server with a larger
context (for example 16k per slot), which I did not change.

## Data and tools
- All 9,496 recent blocks now have coordinates (the Towner Rd blocks needed HDB's building outlines to choose between two OneMap listings; New Market Rd needed `MKT = MARKET`).
- `sales_without_coordinates` is reported on distance-filtered results.

## Week 4b-1: BTO (9B on the MacBook, direct tools, 2026-10-21)
Added 14 BTO questions (5 held out) and replaced q_refuse_003 with q_refuse_006 (Executive Condominium decline). Whole bank: 88 questions, 0 errors,
90.8% number, 100% verdict, 100% refusal, 68.5% grounding.

| Set | Result |
|---|---|
| BTO dev (9) | 6/9 |
| BTO held-out (5, run once) | 3/5 (004, 006, 014 pass; 011, 012 fail) |
| BTO eligibility verdicts and declines | all pass (EHG amounts are number questions: q_bto_008 failed) |

Failures (5 BTO questions plus the known q_distance_005 scorer limit), all launch-lookup or tool-input errors, none a wrong rule:
- q_bto_009, 010, 011, 012 (launch counts and prices): `list_bto_projects` has several required-but-nullable filters. The model fills them with
  invented values (a wrong town, `category: Standard`, `flat_type: 3-room`, `max_price: 1000000`), so the lookup returns 0 or a partial list and the model reports it.
  This is the required-nullable lesson from week 4 turning against us: fields the model must fill invite made-up values.
- q_bto_008 (EHG): the model added `room` and `lease_left_months`, which `bto_ehg_amount` does not take. The tool called them "missing or invalid", which likely led the model to repeat the call; the error message now says "not accepted, leave out". Numbers are from the git-ignored `eval/reports/2026-10-21-agent.json`.
Not fixed here, and no scorer change. Next step: make the launch filters optional with defaults, or reject unfamiliar values with the list of valid ones. Tracked in issue #29.

Unresolved BTO rules (kept as needs_check, not guessed): grant refund on sale, Plus/Prime subsidy recovery rates, EHG work rule for new flats,
loan tenure/MSR, current HDB interest rate, second-timer flat types. Six projects have no OneMap site (distances unknown).

### Week 4b-1 follow-up: optional launch filters (2026-10-22, 9B on the MacBook)
Change: `list_bto_projects` filters are now optional (the model had invented values for the required-nullable ones), `flat_type` is a fixed list, and empty text counts as no value.
Re-ran the 9 BTO dev questions in a separate report (`eval/reports/2026-10-22-agent-bto-fix.json`): 8 pass, 1 request timeout (q_bto_002, a verdict question; the first run
of it passed too). Asked once more outside the harness it gave the correct "no" (income above the 16,000 revised ceiling) in 61 s, but that run is not counted.
q_bto_009 and 010 now pass because of this change; q_bto_008 passes because of the clearer tool error added in 4b-1 (the model now drops the extra fields). Grounding in this re-run was 72.7% (q_bto_001 1/3 and q_bto_013 0/1 are weak). The held-out BTO questions (011, 012 failed before) were not re-run: they are spent for tuning, so their 3/5 stays as reported above.

## Week 4b-3: scenario questions (9B on the MacBook, direct tools, 2026-10-22)
7 `scenario` number questions (3 held out) and 2 declines (q_refuse_007, 008). Expected values come from `scripts/build_scenario_expected.py` (month-by-month amortisation, independent of the app code).

Dev tuning (separate reports `eval/reports/*-agent-scenario*.json`, git-ignored): first run 0/4 scenario and q_refuse_008 failing. Causes, all on my side or the model's tool choice:
the model used `calculate` or `max_loan` instead of `bto_scenario`; q_scenario_002 and 003 gave no rate or years while the tool required them (now optional); q_scenario_007's expected
value equalled a number in its question, which the scorer ignores (case changed to Jurong West 4-room); q_scenario_002 also read as the income-based personal loan limit (reworded to "ignoring income limits").
After the fixes dev is 4/4. q_refuse_008 ("which loan makes more money") still fails: the model gives a balanced list of factors instead of declining.
Dev questions were reworded after seeing results, so the dev pass rate is tuned, not independent.

Held-out (run once, after the fixes): 1/3 pass (q_scenario_006 passes; 004 and 005 fail). Cause: I had made `category` optional, and the model then left it out even when the question
named Standard or Plus, so no balance or sale scenario was returned and it answered with the instalment or the upfront cost instead. Fixed afterwards by making `category`
required but nullable (the week 4 lesson: required-nullable for fields the model must consider, optional for filters). The held-out set is spent, so its 1/3 stays as reported; dev re-run after the fix is 4/4.
Grounding column is low in these runs (37-100%) because the tool rounds sale prices to $1,000 and the model sometimes quotes unrounded figures; week 5 `grounding.py` will judge this properly.
