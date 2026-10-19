# First agent questions

These are the hand-written prompts in `src/ask_hdb/check_cases.py`.
Run `uv run ask-hdb eval` to check routing and arguments. Expected factual answers
are computed by the original Python tools in `eval/reports/week2-expected.json`.
For answer review, ask each question with `ask-hdb ask` and compare every number,
verdict, unresolved check and citation with that output. Routing alone is not an
answer-grounding score.

For the family questions below, use this complete profile:
family couple, both SC, both aged 35, both first-timers, monthly household income
$4400, continuously employed for the past year, no private property or previous
HDB loans. Standard resale flat, 4-room, 960 months of lease left, price $600000.

1. What are the recorded 4 ROOM resale price statistics in TAMPINES during 2025?
   Expected tool: `price_stats`, town TAMPINES, flat type 4 ROOM, inclusive year bounds.
2. Find the newest 3 recorded 4 ROOM sales in BEDOK costing at most $600000.
   Expected tool: `find_sales`, BEDOK, 4 ROOM, price cap and row limit.
3. Compare $620000 for a 4 ROOM flat at blk_406_ang-mo-kio-ave-10 with recorded sales
   as of 2026-09. No floor, area or lease filter.
   Expected tool: `compare_price`; answer must say this is not a valuation.
4. With the family profile above, check whether we can buy this resale flat.
   Expected tool: `can_buy_resale`; keep unresolved checks visible.
5. With the family profile above, compute only our CPF Housing Grant.
   Expected tool: `cpf_housing_grant`; preserve rule citations.
6. With the family profile above, compute only our Enhanced CPF Housing Grant.
   Expected tool: `ehg_amount`; preserve rule citations.
7. With the family profile above, we will live with our parents. Compute our
   Proximity Housing Grant.
   Expected tool: `phg_amount`, relation with; disclose the previous-use check.
8. With the family profile above, estimate our maximum HDB loan using the default
   qualifying rate.
   Expected tool: `max_loan`; disclose the valuation limitation.
9. Give recorded resale price statistics for blk_406_ang-mo-kio-ave-10, 4 ROOM,
   from 2026-01 to 2026-09 inclusive.
   Expected tool: `price_stats`, exact stable block ID and inclusive month bounds.
10. Predict the exact price of my flat next year. Can these tools do that?
    Expected: no tool call and an explanation that future prices cannot be predicted.
