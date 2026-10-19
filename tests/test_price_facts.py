"""Price facts checked against the real data.

Expected numbers were computed on 2026-10-20 straight from data/raw/resale.csv with the csv
module and statistics (not through our cleaner), so they check the whole pipeline.
Every query has an end month, so new downloads do not change the answers.
Skipped when the cleaned file has not been built yet.
"""

from pathlib import Path

import pandas as pd
import pytest

from ask_hdb.sales import price_stats

CLEAN = Path(__file__).resolve().parents[1] / "data/clean/resale.parquet"
pytestmark = pytest.mark.skipif(
    not CLEAN.exists(),
    reason="Build with uv run python scripts/fetch_resale.py then "
           "uv run python scripts/clean_resale.py",
)


@pytest.fixture(scope="module")
def sales() -> pd.DataFrame:
    return pd.read_parquet(CLEAN)


def test_tampines_4room_2025_median(sales):
    s = price_stats(sales, town="TAMPINES", flat_type="4 ROOM", since="2025-01", until="2025-12")
    assert (s["n_sales"], s["median"]) == (892, 668000)


def test_ang_mo_kio_3room_2024_range(sales):
    s = price_stats(sales, town="ANG MO KIO", flat_type="3 ROOM", since="2024-01", until="2024-12")
    assert (s["n_sales"], s["min"], s["max"]) == (571, 333000, 780000)


def test_one_block_all_sales(sales):
    s = price_stats(sales, block_id="blk_406_ang-mo-kio-ave-10", until="2026-09")
    assert (s["n_sales"], s["min"], s["max"]) == (22, 200000, 353000)


def test_bishan_5room_first_half_2025(sales):
    s = price_stats(sales, town="BISHAN", flat_type="5 ROOM", since="2025-01", until="2025-06")
    assert (s["n_sales"], s["min"], s["mean"]) == (52, 810000, 1056872)


def test_queenstown_executive_2023(sales):
    s = price_stats(sales, town="QUEENSTOWN", flat_type="EXECUTIVE", since="2023-01", until="2023-12")
    assert (s["n_sales"], s["mean"], s["median"]) == (7, 1139714, 1180000)
