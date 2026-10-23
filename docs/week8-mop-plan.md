# Week 8-6: MOP status on the map, and upcoming BTO completion

## Goal
Mark blocks that have not yet reached the Minimum Occupation Period (MOP) and show upcoming BTO sites as upcoming, with an estimated completion. Everything is approximate and labelled so.

## What the data can say (checked 2026-10-24)
- Built blocks: `resale.parquet` has `lease_commence_year` per sale. HDB's MOP is 5 years from key collection (the rule is in the dated rules YAML with its source and as_of; read the value from the rules loader, do not hard-code 5). We have no key-collection date, so the lease start year stands in for it. A block with lease start Y reaches MOP during year Y+5, month unknown.
- Newest lease start in the data is 2023, and a block appears only once a flat in it has resold. Blocks finished recently and never resold are not in `blocks.parquet` sales and cannot be marked; the limits text says so.
- BTO: `bto_projects.parquet` has `first_launch` (YYYY-MM) and `wait_months` (HDB's stated waiting time from launch). Estimated completion = first_launch + wait_months, shown as a month and labelled an estimate. It is the date flats are expected to be ready, not a promise.
- Resales before MOP exist (see memory note early-resale-puzzle): a "within MOP" block can still show resales. The label says "estimated".

## Design
- **Server (code decides).** `src/ask_hdb/api/mapdata.py`: `metrics()` rows become `[price, count, lease_left, mop]` where `mop` is a small integer computed in Python from the block's newest `lease_commence_year` and the data's latest month year: 0 = "within MOP" (Y+5 > current year), 1 = "MOP ends this year" (Y+5 == current year, month unknown), 2 = "past MOP" (Y+5 < current year). The response also carries `mop_years` and the rule's `source`/`as_of`, plus a limits line. Existing consumers read `row[0..2]` only, so adding a fourth element is compatible; tests assert the old three fields are unchanged. The block card (`_block_facts`) gets a fact: "MOP: estimated within MOP / ends this year / past, from the lease start year" with an inline "approximate" qualifier. The BTO card gets "Estimated completion: about YYYY-MM (launch month plus stated waiting time)" beside the existing waiting time fact; no new numbers are computed outside code, and nothing is invented when `first_launch` or `wait_months` is missing (omit the fact).
- **Map.** A fourth layer button "MOP" (`data-mode="mop"`) in the existing colour-by control and the phone chip row (`.seg [data-mode]` selectors already generic): within MOP amber, ends this year light amber, past MOP the normal blue, no data grey. The 3D buildings use the same colour expression through `buildings.js` `setMetrics`. Legend steps under the layer (like `#lease-controls`): a new `#mop-controls` row with the three states and one line of limits; the long limits text lives in `#layer-note`, which already moves into the sheet on phones. BTO sites keep the orange point, with an "upcoming" ring (white outline thicker) and the legend text "BTO site (upcoming, approximate)".
- **No agent change.** The agent, tools, prompt and grounding rules do not change. (A later tool for "which blocks are within MOP" is out of scope.)
- Limits text on the layer and the card: "MOP is 5 years from key collection. We only know each block's lease start year, so this status is approximate (a block can reach MOP months earlier or later). Blocks with no resale yet are not shown. Check HDB for a specific flat." Read the 5 from the rules loader.

## Contract that must not change
DOM ids and behaviours in docs/week8-plan.md, the mobile sheet and chips (new chip must fit the row and scroll), `.seg [data-mode]` lookups, existing metrics fields and tests, no `innerHTML`, desktop layout unchanged apart from the new button.

## Done when
- pytest and ruff pass. New tests: MOP codes for lease-start edge years (Y+5 below, equal to and above the data year), rule value read from the loader (changing it in a test changes the codes), old row fields unchanged, block card MOP fact present with its qualifier, BTO estimated completion correct for a known row (first_launch 2025-02 + 47 months = 2029-01) and omitted when a field is missing, UI test for the MOP mode button, legend row and layer note.
- Checked in a browser at desktop and 375px: the MOP layer colours blocks, the legend and limits read, BTO card shows the estimate.
