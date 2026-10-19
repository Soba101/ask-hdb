# Week 1 plan: data and rules (no LLM)

Approved 2026-10-20. Exit check: `uv run pytest` green and `uv run ruff check .` clean,
with no model anywhere.

## Steps
1. Setup: `uv init`, pytest, ruff, `.env.example`, `ask_hdb/` and `tests/`.
2. Data: `scripts/fetch_resale.py` (data.gov.sg, 2017 on) and `scripts/clean_resale.py`
   (dates, lease left in months, storey midpoint, stable block IDs).
3. Price tools: `price_stats` and `find_sales`. Tests: 5 price facts computed by hand.
4. Rules: read hdb.gov.sg only, write `rules/2026-10.yaml` with `source` and `as_of` per value.
5. Rule functions: `can_buy_resale`, `cpf_housing_grant`, `ehg_amount`, `phg_amount`, `max_loan`.
   Tests use HDB's own worked examples.
6. `compare_price(block_id, price)`: comparable recent sales by storey and lease band.

## Working rules
- Every diff is reviewed before committing.
- Files stay under ~200 lines, with short plain comments.
- If hdb.gov.sg is unclear or two pages disagree, write it down as a finding. Do not guess.
- data.gov.sg API key goes in `.env` (`DATAGOV_API_KEY`), never in the repo.

## Exit answer (2026-10-20)
`uv run pytest -q` passes (229 tests) and `uv run ruff check .` is clean, with no model anywhere.
- Data: 242,742 resale sales (2017-01 to 2026-10). Price facts are checked against the raw CSV.
- Rules: `rules/2026-10.yaml` from hdb.gov.sg only. HDB's five worked examples pass as tests.
- Open (see `docs/week1-rules-notes.md`): lease pro-rating formulas are unpublished (flagged, not guessed);
  Plus/Prime 3-room project ceilings and joint-single EHG are not modelled; previous PHG use cannot be checked.
- Reviewed twice by a second model; its must-fix items are fixed.
