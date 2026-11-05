# Week 7 plan: trust and a stable link (draft, 2026-11-05)

Status: draft for review. Nothing here has started.

Goal: close the week 6 exit check ("a stranger uses the public link with no help") and fix the real gaps from the external review.
Each phase is one PR. Each PR needs approval before merge.

## 7-1: CI and project basics (small, do first)
- Add `.github/workflows/ci.yml`: `uv sync --frozen`, `ruff check`, `pytest` on Python from `.python-version`.
- Problem to solve first: no file under `data/` is in git. Tests that read `data/clean/*` fail on a fresh clone.
  Mark them `@pytest.mark.data` and skip them in CI when the file is missing. Do not commit the data.
- Node UI tests (`tests/*.mjs`): run in CI only if they need no browser. Check first.
- `pyproject.toml`: replace `description = "Add your description here"`.
- Add `LICENSE`. **Decision needed: license** (MIT suggested).
- Add a short `SECURITY.md` (how to report a problem). Skip CONTRIBUTING and issue templates.
- **Exit:** a PR shows a green CI check. The check runs in under 5 minutes with no keys and no model.

## 7-2: "As of" dates in answers
- The rule YAML already has `source` and `as_of` for each value (`rules/loader.py`). Rule tools already return them.
- Show the newest `as_of` date and the source link under each rules answer in the web page. Show the data date for resale prices.
- Add one test: a rules answer in the API stream carries `as_of`.
- **Exit:** every eligibility, grant and loan answer on the page shows "Rules as of <date>" with a link.

## 7-3: Two small test gaps from the review
- Rules: list each branch in `eligibility.py` and `grants.py`. Add a test where a branch has no "missing information" case. Do not rebuild the existing suite.
- Grounding: add 3 to 5 eval questions where a tool number exists but is the wrong one (wrong flat type, wrong period, monthly vs total).
  Write them as a new held-out set, because issue #13 says the old held-out set is spent.
- **Exit:** the new cases exist and the result is written in `docs/eval-results.md`, pass or fail.

## 7-4: Stable public link (decision needed)
Choose one:
- **A. Named Cloudflare tunnel from this Mac.** Fixed address. Needs a domain on Cloudflare (about USD 10 a year). Same 9B local model, about 30 s per answer. Works only while the Mac is on.
- **B. Small VM with a cloud model.** Always on. Costs a VM fee plus API calls. The roadmap says to run the dev eval on that model first.
  The current caps stay: 6 chats per minute per visitor (`API_RATE_PER_MINUTE`) and 2,000,000 tokens a day (`API_DAILY_TOKEN_CAP`).
- **Decided 2026-11-05: neither for now.** Keep the current setup: GitHub Pages demo (chat paused) and the quick tunnel shared by hand. Look at this again later.
- Week 6 exit check stays open until then.

## Leftover UI items (fit in any PR)
- Phone legend is cut off. Tab order. Map flick momentum.

## Not in this plan
- Supervisor graph and RAG over policy pages (week 5 deferred; the eval showed no gain from the graph).
- BTO sites on the 3D map.
- Demo GIF, accessibility pass, data licence checklist, more models or tools.

## Decisions for the owner
1. License (7-1).
2. ~~Hosting path A or B (7-4).~~ Decided: keep the current setup for now.
3. Order: 7-1 first is fixed. 7-2 and 7-3 can swap.
