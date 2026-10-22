"""Independent expected values for the bto_history eval questions (plain pandas, not ask_hdb.bto.history).

Usage: uv run --no-sync python scripts/build_history_expected.py FY TOWN "4 ROOM"
Rule: resale sales in the same town and flat type, lease start FY+3..FY+5, sold 5..7 years after lease start (by calendar year).
"""

import sys

import pandas as pd

fy, town, flat = int(sys.argv[1]), sys.argv[2].upper(), sys.argv[3].upper()
sales = pd.read_parquet("data/clean/resale.parquet")
sales = sales[(sales.town == town) & (sales.flat_type == flat)]
lease = sales.lease_commence_year
held = sales[lease.between(fy + 3, fy + 5) & (sales.year - lease).between(5, 7)]
launch = pd.read_parquet("data/clean/bto_price_range_town.parquet")
launch = launch[(launch.financial_year == fy) & (launch.town == town) & (launch.room_type.str.strip().str.upper() == flat.replace(" ", "-"))]
print("launch_low", launch.price_low.tolist(), "launch_high", launch.price_high.tolist())
print("n", len(held), "median", held.resale_price.median(), "p25", held.resale_price.quantile(.25), "p75", held.resale_price.quantile(.75))
