# Week 4 plan: places and MCP

Draft 2026-10-20, waiting for approval. Exit check (from the roadmap): distance questions pass, and the
same eval score through MCP as before. Nothing is built or downloaded before approval.

## Steps
1. **Block coordinates.** `scripts/geocode_blocks.py`: 9,763 blocks (block_id) -> lat/long using the
   OneMap search API, from block number + street. Every answer is cached to `data/clean/geocode_cache.json`
   (one call per address, ever) and written to `data/clean/blocks.parquet`. Blocks OneMap cannot find are
   listed in a report, not guessed.
2. **Cross-check.** Compare our coordinates with the HDB Existing Buildings GeoJSON
   (`d_16b157c52ed637edd6ba1232e026258d`, block number + postal code). Flag any block more than ~300 m away
   from its outline. About 57 MB download.
3. **Places.** `scripts/fetch_places.py`: MRT stations and primary schools with lat/long and stable IDs
   (`mrt_ew2`, `school_<name>`). I look up the right data.gov.sg datasets first and show you the names and sizes before
   downloading anything.
4. **Distance tools** (plain Python, no model): `nearest(block_id, kind, n)` and a `within_km` filter on
   `find_sales` / `price_stats`. Straight-line (haversine) only, and every answer says "straight-line".
   HDB's 1 km / 2 km school rule is the official OneMap tool's job; we say "about" and link to it.
5. **MCP server** `src/ask_hdb/mcp/`: the official Python MCP SDK, stdio transport, all tools (week 2 + week 4)
   moved behind it with the same argument rules (required fields, `not_applicable`, `unknown`). No LLM inside it.
   The agent connects through it with a small adapter. Old direct tools stay until the MCP score matches.
6. **Eval additions, written before any tuning:** 8 distance + 10 multi-step questions (budget + grant + nearest MRT),
   expected answers by haversine in plain pandas/numpy, independent of our `nearest`. Of these, 6 are held out
   from day one (the old held-out set is spent).
7. **Runs on the MacBook model:** all dev questions through direct tools and through MCP; table with both.

## OneMap facts (checked 2026-10-20)
- Search needs a registered OneMap account and a token (3-day JWT, renewed automatically); only basemaps are open.
  I cannot create the account. You would register, then put `ONEMAP_EMAIL` / `ONEMAP_PASSWORD` in `.env`.
- The rate limit is not written in any page I could read (the docs site is script-rendered; their workshop slide
  for it has no numbers). Terms of service set no figure, only "do not disrupt the service", and they may suspend access.
  So: start slow (about 2 calls a second), back off on any 429, and stop and tell you if it pushes back.
- We only need one call per unique block (9,763), not one per sale, and never repeat a call (disk cache).
  To cut it down, we could first geocode only blocks with a sale in the last 3 years.

## Decisions for you
- OK to register a OneMap account and use it for about 9,800 slow, cached calls (or fewer, recent blocks only)?
- OK that distances are straight-line only in v1, as in the proposal?
- Download approval is asked per file when I get there (names, sizes, sources), as before.

## Risks
- OneMap may not find some blocks (new or renamed streets). Plan: a "not found" list and a fallback to the
  building-outline file for blocks with a postal code; no invented coordinates.
- Distance and multi-step questions are harder for the 9B model. Expect failures; each is written down with its cause first.
- The 5090 stays untouched until you say.

## Working rules
- Codex builds, this chat reviews every diff, Opus reviews before merge. Files under ~200 lines, short comments.
- Expected answers are frozen once written. `uv run pytest` and `uv run ruff check .` stay green.
