# Notes for coding agents (and future me)

## The one rule
The LLM talks. Code decides.
- An LLM never states a number, a price, a distance or an eligibility verdict on its own.
- It calls a tool. The tool computes the answer in plain Python. The LLM explains it.
- If something has a correct answer, it belongs in code, not in a prompt.
- Every number in a final answer must appear in a tool result from the same turn.
  `grounding.py` checks this. Never weaken that check to make a test pass.

## Prices
- No exact future prices, no investment timing. The only forward-looking numbers are the `bto_scenario` scenarios: modest, from sourced past growth,
  headline = low growth, always labelled "illustrative, from past growth, not a forecast". Under-promise.

## Rules data
- HDB rules change (income ceilings, grant amounts, loan limits).
- Rules live in `rules/*.yaml`, never hard-coded in Python.
- Every rule value has a `source` URL and an `as_of` date.
- When a rule changes, add a new dated file. Do not edit old values in place.

## Code style
- Simple, small, modular. Keep files under ~200 lines.
- Lots of comments, in short plain sentences. Explain *why*, not just *what*.
- Never delete old comments unless they are clearly wrong.
- Stable IDs for everything (`town_tampines`, `mrt_ew2`). Never match on display names alone.
- Tools are pure functions where possible: same input, same output. Easy to test.

## Data
- Raw downloads go in `data/raw/` (git-ignored). Never edit them by hand.
- Cleaned data goes in `data/clean/`, built by a script that can be re-run.
- Cache OneMap results to disk. Do not call the API for the same address twice.

## Before you say "done"
- `uv run pytest` passes.
- `uv run ruff check .` is clean.
- If agent behaviour changed: `uv run ask-hdb eval` and note the score change in the roadmap.

## Design docs
- `docs/proposal.md`: the plan, decisions and scope.
- `docs/architecture.md`: components and data flow.
- `docs/eval.md`: what "correct" means and how we score it.
- `docs/roadmap.md`: weeks, tasks and exit checks.
