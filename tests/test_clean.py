import runpy
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from ask_hdb.clean import clean


def test_columns_dates_and_numeric_types(raw_sales):
    result = clean(raw_sales)
    assert list(result.columns) == [
        "sale_month", "year", "town", "flat_type", "block", "street_name", "block_id",
        "storey_low", "storey_high", "storey_mid", "floor_area_sqm", "flat_model",
        "lease_commence_year", "lease_left_months", "resale_price",
    ]
    assert pd.api.types.is_datetime64_any_dtype(result["sale_month"])
    assert result["sale_month"].dt.day.tolist() == [1, 1, 1, 1, 1, 1, 1, 1]
    assert result["sale_month"].iloc[0] == pd.Timestamp("2024-01-01")
    assert result["year"].tolist() == [2024, 2024, 2024, 2024, 2024, 2024, 2023, 2024]
    for column in ("year", "lease_commence_year", "lease_left_months", "resale_price"):
        assert pd.api.types.is_integer_dtype(result[column])
    assert pd.api.types.is_float_dtype(result["floor_area_sqm"])
    assert result["floor_area_sqm"].iloc[2] == 95.5
    assert result["lease_commence_year"].iloc[0] == 1985
    assert result["resale_price"].iloc[0] == 100000


def test_stable_block_ids_and_floor_bands(raw_sales):
    result = clean(raw_sales)
    assert result["block_id"].tolist() == [
        "blk_001a_tampines-st-11", "blk_001a_tampines-st-11", "blk_002_tampines-st-11",
        "blk_003_tampines-ave-2", "blk_004_tampines-ave-2", "blk_005_bedok-nth-st-1",
        "blk_006_bedok-nth-st-1", "blk_001a_tampines-st-11",
    ]
    assert result["storey_low"].tolist() == [10, 4, 7, 10, 1, 13, 16, 10]
    assert result["storey_high"].tolist() == [12, 6, 9, 12, 3, 15, 18, 12]
    # Each midpoint is the average of the two known floors.
    assert result["storey_mid"].tolist() == [11, 5, 8, 11, 2, 14, 17, 11]
    assert result["block"].iloc[0] == "001A"
    assert result["street_name"].iloc[0] == " TAMPINES... ST / 11 "


def test_lease_formats_and_missing_lease_fallback(raw_sales):
    # 61*12+4=736; 61*12=732; Jan 2099 minus Feb/Apr 2024 = 899/897.
    # Then 60*12+1=721, 50*12=600, 59*12+11=719; the repeated first sale has 736.
    assert clean(raw_sales)["lease_left_months"].tolist() == [
        736, 732, 899, 897, 721, 600, 719, 736,
    ]
    raw_sales.loc[2, "remaining_lease"] = "   "
    assert clean(raw_sales)["lease_left_months"].iloc[2] == 899


def test_identical_rows_are_kept_without_mutating_input(raw_sales):
    original = raw_sales.copy(deep=True)
    result = clean(raw_sales)
    assert len(result) == 8
    assert result.duplicated().tolist() == [False, False, False, False, False, False, False, True]
    assert_frame_equal(result.iloc[[7]].reset_index(drop=True), result.iloc[[0]])
    assert_frame_equal(raw_sales, original)


def test_empty_input_with_schema(raw_sales):
    result = clean(raw_sales.iloc[:0])
    assert result.empty
    assert "block_id" in result.columns


def test_missing_columns_are_reported_together(raw_sales):
    with pytest.raises(ValueError, match="Missing required columns: month, resale_price"):
        clean(raw_sales.drop(columns=["month", "resale_price"]))


def test_script_writes_parquet_from_fixture(raw_sales, tmp_path):
    source = tmp_path / "data/raw/resale.csv"
    source.parent.mkdir(parents=True)
    raw_sales.to_csv(source, index=False)
    script_path = Path(__file__).resolve().parents[1] / "scripts/clean_resale.py"
    script = runpy.run_path(str(script_path))
    # Redirect the script so this check never reads the real download.
    script["main"].__globals__["ROOT"] = tmp_path
    script["main"]()
    result = pd.read_parquet(tmp_path / "data/clean/resale.parquet")
    assert_frame_equal(result, clean(raw_sales))


@pytest.mark.parametrize(
    "column,value,message",
    [("remaining_lease", "unknown", "remaining_lease"), ("storey_range", "high", "storey_range")],
)
def test_malformed_ranges_have_clear_errors(raw_sales, column, value, message):
    raw_sales.loc[0, column] = value
    with pytest.raises(ValueError, match=message):
        clean(raw_sales)
