# Week 4b plan: BTO (rules, launch info, appreciation, scenarios, map)

Draft 2026-10-21, waiting for approval. Scope decided by the user on 2026-10-20: rules + launch info + map. Nothing is built or
downloaded before approval.

## Scope update 2026-10-21 (user request, decisions made)
The user also wants: appreciation around a BTO site and government plans, a projected resale price, a comparison with surrounding-area prices, the difference between
launch price and prices after MOP, all with grants and bank/HDB loans taken into account. Decisions: **illustrative scenarios** (not a forecast) and **three phases**.

| Phase | What | Needs |
|---|---|---|
| **4b-1** | Everything in "Steps" below: BTO rules, launch data, sites, distances, tools, eval | This plan's approvals |
| **4b-2** | History: for past BTOs (launched about 2015 to 2020, now past MOP) compare indicative launch price with resale prices after MOP in the same blocks and in the surrounding area; growth by town, flat type and distance band to MRT/schools; government plans (URA Master Plan, planned MRT) shown as facts with dates | A **feasibility check first**: HDB launch price history for older exercises, and matching a project to its blocks (our data has town, street and lease commence year) |
| **4b-3** | Scenario calculator: launch price plus grants and loan (CPF Housing Grant, EHG, HDB/bank loan at stated rates, MSR) to a range of resale outcomes after MOP, with net proceeds (loan payoff, CPF refund with accrued interest, fees) | HDB rules read first and flagged where unclear; its own plan, eval and Opus review |

**Prediction policy change (needs recording in AGENTS.md and the proposal when 4b-3 is built).** Today the agent declines price predictions. After 4b-3 it may show an
*illustrative scenario range*: code applies past growth (low / median / high of comparable towns) to a price over the MOP years and labels it "illustrative, from past
growth, not a forecast". The model never invents the number; every figure comes from a tool. "What will my flat sell for?" (an exact figure) is still declined.
**What cannot be promised:** how much a government plan adds to a price. Past data can show correlation (for example, blocks that gained an MRT within 1 km versus blocks that
did not), but cannot separate the plan from everything else that changed. Such comparisons are shown as descriptive history with that caveat, never as a causal uplift.

## What I found first (searched 2026-10-21)
- No clean per-project BTO dataset on data.gov.sg. HDB publishes launches as press-release pages with administrative annexes (PDF tables
  of project, town, flat types, units, indicative prices, expected completion) and BTO application-rate pages. data.gov.sg has only aggregates
  (bookings, units sold).
- HDB's own pages disagree on BTO income ceilings: a 2026 annex lists $16,000 (families) and $24,000 (extended), while the February 2026 BTO annex still
  shows $14,000 and $21,000. I did not find the effective date. Rule: write both down as a finding, flag `needs_check`, do not guess (same rule as week 1).

## Steps
1. **BTO rules (no model).** Read hdb.gov.sg only. New dated file `rules/2026-10-bto.yaml` (each value with `source` and `as_of`): eligibility
   (citizenship, age, income ceilings, first-timer, flat types by buyer type), BTO grants and how they differ from resale (CPF Housing Grant, EHG, Fresh Start /
   Step-Up), loan limits. Functions `can_apply_bto` and `bto_grants`, reusing the resale grant code where the rule is identical. HDB's worked examples become tests.
   Out of scope: ballot odds, priority schemes, queue numbers.
2. **Launch data.** `scripts/fetch_bto.py`: the project list from HDB's launch pages/annexes, one launch at a time, into `data/clean/bto_projects.parquet`
   (stable id `bto_<slug>`, town, launch month, flat types with units, indicative price range, expected completion, site description). Prices are labelled
   "indicative at launch". I show you each source URL and size before downloading it.
3. **Sites on the map data.** Geocode each project by its name/street through OneMap (same cache and politeness as before; a BTO site has no block number, so
   coordinates are approximate and flagged). Add them to the places table as kind `bto_site`. Optional, with your OK: the URA Master Plan rail-station layer for planned MRT.
4. **Tools** (plain code, MCP picks them up automatically): `list_bto_projects(town, flat_type, launch_month, max_price)`, `bto_nearby(project_id, kind)` (nearest MRT/primary
   schools, straight-line, with the "approximate site" note), and the two rule tools. Required-but-nullable fields for every filter (lesson from week 4).
5. **Eval, written before any tuning.** About 14 questions: 6 BTO eligibility/grants (hand-read from the new YAML), 5 launch facts (counts, units, towns), 3 distance. 5 held out
   from the start. Expected answers computed independently. The frozen refuse question `q_refuse_003` ("How do I apply for a BTO flat?") becomes wrong; I retire it (marked, not deleted)
   and add a replacement decline question (for example Executive Condominium applications) so the refuse set stays at 5.
6. **Runs** on the MacBook model (9B), direct and MCP. The 5090 only after asking you.
7. **Docs, issues, wiki, Obsidian, board** updated at each step.

## Decisions (user, 2026-10-21)
- Launch data: HDB press-release annexes approved, download them. BTO prices shown only as "indicative at launch". Retire `q_refuse_003` and add a replacement: approved.
- Forecast stance: a **modest** projection. With history available, show conservative scenarios (lean to under-promise): the headline scenario uses the low-to-median
  past growth, never the high end, and every projection carries the "illustrative, from past growth, not a forecast" label.

## Decisions asked earlier (now answered)
- OK to use HDB's launch press-release annexes (PDF tables) as the launch-data source, one launch at a time, with your approval per download? Alternative: HDB's launch web pages if they render as plain text.
- OK that BTO prices are shown only as "indicative at launch", and that ballot odds / priority schemes are out of scope?
- OK to retire `q_refuse_003` and add a replacement (the one change to the frozen bank)?

## Risks
- PDF tables can be messy; I will check every parsed row against the source before using it, and list anything I cannot read.
- Income ceilings may be unresolved (two sets). They stay flagged `needs_check` until HDB's pages are clear.
- A BTO site's coordinates are approximate; every distance answer says so.

## Working rules
- No Codex (the user's usage is finished): built directly here, Opus reviews before merge. Files under ~200 lines, short comments. `uv run pytest` and `ruff` stay green.
- A failed question is a finding; write it down before any prompt change.
