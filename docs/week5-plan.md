# Week 5 plan: trust features

Exit check (roadmap): grounding 100% on the eval; profile confirmation; refusals kept; the full condition beats the single agent.
Rule: small and verifiable beats big. Each phase is tested offline with fake chat models first; model runs come after, by the user.

## Phases

| Phase | What | Status |
|---|---|---|
| 5-1 | `grounding.py` number check in `agent.ask()`: check, one rewrite, re-check, else an honest "can't answer reliably". Eval grounding column uses the same function. | built (this branch) |
| 5-2 | Tools return the numbers models like to add from memory (rule thresholds used, counts within a radius). | built (this branch), eval pending |
| 5-3 | Profile confirmation: "Is this right?" before any eligibility or grant tool runs. | after 5-2 |
| 5-4 | `full` eval condition (single agent + grounding + confirmation) vs single agent, same questions and model. | after 5-3 |
| deferred | Supervisor + workers graph; RAG over HDB policy pages. | see below |

## 5-1 Grounding (built)
- `src/ask_hdb/grounding.py`: `claims()` reads numbers from text, `evidence()` collects every number in tool results,
  `check()` returns stated and ungrounded numbers. Rules are written at the top of the file. In short:
  exact value after formatting (commas, `$`, `%`, sign); `k`/`million` must match exactly; decimals may be the tool value
  rounded half-up to the written decimals; whole numbers never round. Labels are skipped: block IDs, ISO dates, bare years
  1960-2100, ordinals under 100, flat types, list labels. Question numbers may be restated. Tool errors and tool arguments are not evidence.
- `agent._ask()`: after the graph answers, check. If any number is ungrounded, send ONE rewrite request naming those numbers.
  The rewrite runs through the same graph, so it may call a tool (for example `calculate`), and it shares the same token budget and
  tool-call cap. Re-check all tool results; if still ungrounded (or empty), the answer becomes `grounding.CANNOT_ANSWER`.
  The result gains a `grounding` record: numbers, ungrounded, first_ungrounded, rewritten, replaced. Limit stops behave as before.
- Eval: `scoring.grounding()` now calls the same `check()`. So the column measures what the agent enforces.
- Tests: `tests/test_grounding.py` (rules, both directions), `tests/test_agent_grounding.py` (scripted fake model: kept, fixed by
  rewrite, honest fallback after exactly one rewrite, rewrite with a tool call, decline unchanged, question echoes).

Offline look at the saved 2026-10-21 report (88 active questions, answers recorded before this change, so no rewrite happened):
new check 96/119 = 80.7%, old check 98/143 = 68.5%. The total drops because labels (years, flat types, list numbers) are no longer
claims; rounded distances and signed differences now match. Supported also drops by 2: tool errors are no longer evidence. What is left is real: rule thresholds from memory (min age 35/21, 24 months, 75% LTV, 12 months),
counts the model made itself ("2 schools", "3 schools"), a model-written "1e+06", and answers built on tool errors.

## 5-2 Tool-side numbers (next)
The rewrite can only remove a memory number, not ground it. Two small tool changes let the model cite instead:
- Rule tools add the rule values they used (for example `min_age_years: 35`, `ltv_max_pct: 75`) to their result, from `rules/*.yaml`.
- `nearest_places` adds `n_within_km` when asked for a radius, so counts come from code.
Test: unit tests on each tool output, plus grounding tests with those outputs. Risk: longer tool results on 8k-slot servers.

Why (5-1 dev eval, 9B, 2026-10-22): grounding 100% and number 93.6%, but verdict fell from 78.6% to 57.1%: 6 answers were replaced
because they quoted thresholds from memory (21, 35, 24 from "24 Aug 2026", 75% LTV), a school count, and numbers in a decline.

Built:
- `RuleUse.get` puts the rule value into each citation in `rules` (`value`; fractions also get `value_pct`, so 0.75 is 75).
  Tier tables are left out to keep results short. Singles checks cite both minimum ages (35 and 21).
- `can_apply_bto` cites the HFE revision date (2026-08-24); `bto_ehg` cites the 12-month work rule when work history fails.
- `bto_scenario` returns `ltv_pct`. Its growth percentages were already in `annual_growth_pct` and `growth_basis`.
- `nearest_places(within_km=...)` returns every place within that distance (inclusive) and `n_within`.
- System prompt: thresholds only from the rules `value`/`value_pct`; counts from `n_within`; a decline states no numbers.
- `grounding.py` is unchanged. Tests: `tests/test_rule_values_grounding.py` replays the memory-number answers against the new tool outputs.

## 5-3 Profile confirmation (after 5-2)
Code decides, not the prompt. The agent intercepts a call to `can_buy_resale`, `can_apply_bto`, `cpf_housing_grant`, `ehg_amount`,
`phg_amount`, `bto_ehg_amount` or `max_loan` (names checked against `tools.py` when built):
- If this profile was not confirmed, the tool does not run. Code renders the profile from the tool arguments ("Is this right?"),
  with no model wording, and the turn ends with `needs_confirmation`.
- The next user turn "yes" (code-matched, small fixed list) plus the same arguments hash lets the call run. Any change asks again.
- Eval: single-turn questions would all stop at the question. The `full` condition answers "yes" once as a second turn; the
  `agent` condition stays as today so the comparison is fair. Refuse/clarify questions must not change.
- Tests: fake model requests an eligibility tool; assert the tool did not run, the profile text, then a "yes" turn runs it.

## Deferred, with reasons
- **Supervisor + workers graph.** The single agent already reaches 97-98% number accuracy; the misses are tool inputs and memory
  numbers, which 5-1 to 5-3 target directly in code. A supervisor adds model calls per question (slower on the 9B, more places to
  loop), and a multi-agent graph is hard to test offline. Revisit only if 5-4 shows a failure that routing would fix.
- **RAG over HDB policy pages.** Needs downloads and an embedding model (not allowed now), and retrieved prose is a new source of
  numbers the grounding check would have to trust or reject. Explanations today cite rule IDs and source URLs from `rules/*.yaml`,
  which is enough for trust. Revisit in week 6 if users ask "why" questions the rules cannot answer.

## Risks
- Strict check, honest fallback: verdict answers that add a memory threshold may be replaced by "can't answer reliably" if the
  rewrite keeps the number. That would lower verdict accuracy until 5-2 lands. Measure before and after; do not loosen the check.
- Count questions (q_distance_005, 006) depend on the model counting list items. They may now fall back. 5-2 fixes this in code.
- The rewrite costs one more model call per ungrounded answer (time on the 9B); budgets are shared, so it can hit the token stop.
- Years 1960-2100 written without `$`, comma or unit are skipped as years; "income 2000" without a unit would be skipped too.
- Dates in words ("24 Aug 2026") count the day number as a claim; the rewrite usually removes it.
- The eval grounding column changes meaning with this branch; old reports must be rescored to compare (`scripts/rescore.py`).
