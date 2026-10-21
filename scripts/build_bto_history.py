"""Build older BTO launch tables (2021 to 2024) and the town-level launch price ranges.

Reads data/raw/bto_history/ (HDB annexes and the data.gov.sg price-range CSV, see SOURCES.md there).
Writes data/clean/bto_flats_history.parquet (same columns as bto_flats.parquet) and
data/clean/bto_price_range_town.parquet (launch price range by financial year, town and room type).
"""

from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from ask_hdb.bto.parse import parse_annex_a, parse_legacy_annex

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN = ROOT / "data/raw/bto_history", ROOT / "data/clean"
# Pricing annexes only (A2 and A3 of 2021 are Flexi-by-lease and CCA tables; 2024-10 annex A is not pricing).
LEGACY = ["2021-02-annex-a1", "2021-05-annex-a1", "2021-08-annex-a1", "2021-11-annex-a1", "2022-05-annex-a", "2022-08-annex-a"]
CURRENT = ["2023-02-annex-a", "2023-05-annex-a", "2023-10-annex-a", "2023-12-annex-a", "2024-02-annex-a",
           "2024-06-annex-a", "2024-10-annex-b"]


def text_of(name):
    return "\n".join((page.extract_text() or "") for page in PdfReader(RAW / f"{name}.pdf").pages)


def main():
    rows = []
    for name in LEGACY:
        rows += parse_legacy_annex(text_of(name), name[:7])
    for name in CURRENT:
        rows += parse_annex_a(text_of(name), name[:7])
    flats = pd.DataFrame(rows)
    flats["project_id"] = "bto_" + flats.project.str.lower().str.replace(r"[^a-z0-9]+", "-", regex=True).str.strip("-")
    flats.to_parquet(CLEAN / "bto_flats_history.parquet", index=False)
    print(flats.groupby("launch").agg(rows=("units", "size"), units=("units", "sum"), projects=("project", "nunique")))

    town = pd.read_csv(RAW / "price_range_of_hdb_flats_offered.csv")
    town = town.rename(columns={"min_selling_price": "price_low", "max_selling_price": "price_high"})
    town["town"] = town.town.str.upper()
    town.to_parquet(CLEAN / "bto_price_range_town.parquet", index=False)
    print(len(town), "town price-range rows,", town.financial_year.min(), "to", town.financial_year.max())


if __name__ == "__main__":
    main()
