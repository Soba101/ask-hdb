# BTO history: launch price vs later resale (town level, descriptive)

Data (official, see `data/raw/bto_history/SOURCES.md`): HDB launch annexes 2021-02 to 2024-10 (`bto_flats_history.parquet`, parsed by `scripts/build_bto_history.py`)
and the data.gov.sg "Price Range of HDB Flats Offered" CSV, FY2008-FY2024 (`bto_price_range_town.parquet`, town and room type only, 14 towns).

Method (`src/ask_hdb/bto/history.py`): for each launch range (financial year FY, town, room type) take resale sales in the same town and flat type
with lease start FY+3 to FY+5, sold 5 to 7 years after the lease start (first two years after the 5-year MOP), at least 30 sales. Report the resale median
and its ratio to the top of the launch range. Result table: `data/clean/bto_launch_vs_resale_town.parquet` (165 rows, 9 towns, FY2008-FY2018).

Median resale / top of launch range, 4-room: FY2008-2012 launches about 1.4-1.55; FY2013-2018 about 1.8-2.1. Over all rows: 2-room ~2.6, 3-room ~2.1, 4-room ~1.7, 5-room ~1.6.

Limits (say these whenever the numbers are quoted):
- Descriptive only, not a forecast. Resale prices include the effect of the 2021-2023 price rise, which hits the later cohorts, so ratios are not stable.
- Launch ranges are before grants, resale prices are what the buyer paid; neither includes loan interest, CPF accrued interest, fees or renovation.
- Town and flat type level only: no project, floor, MRT distance or lease detail. 14 towns in the CSV (mostly non-mature), so mature-town BTO is not covered.
- Lease start FY+3 to FY+5 is an assumption for key collection; the match is approximate. Early resales of 2021/2022 lease-start flats are unexplained (see week4b-plan.md).
- 2015-2020 per-project launch prices are not available from HDB pages we could reach; per-project history stays limited to 2021-2026 launches.
