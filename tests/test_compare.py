"""Small samples with prices that can be checked by hand."""

import json
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from ask_hdb.compare import compare_price


@pytest.fixture
def sample():
    # The first five prices have median 300, quartiles 200 and 400.
    rows = [
        ("blk_a_main", "MAIN", "TOWN", "2026-01", 100),
        ("blk_a_main", "MAIN", "TOWN", "2026-02", 200),
        ("blk_a_main", "MAIN", "TOWN", "2026-03", 300),
        ("blk_a_main", "MAIN", "TOWN", "2026-04", 400),
        ("blk_a_main", "MAIN", "TOWN", "2026-05", 500),
        ("blk_b_main", "MAIN", "TOWN", "2026-06", 600),
        ("blk_c_side", "SIDE", "TOWN", "2026-07", 700),
        ("blk_d_other", "OTHER", "ELSEWHERE", "2026-08", 900),
    ]
    df = pd.DataFrame(rows, columns=[
        "block_id", "street_name", "town", "sale_month", "resale_price",
    ])
    df["sale_month"] = pd.to_datetime(df["sale_month"])
    df["flat_type"] = "4 ROOM"
    df["storey_low"], df["storey_high"], df["storey_mid"] = 7, 9, 8.0
    df["lease_left_months"], df["floor_area_sqm"] = 720, 90.0
    return df


def test_block_hit_and_examples(sample):
    before = sample.copy(deep=True)
    result = compare_price(sample, "blk_a_main", 330, flat_type="4 ROOM", max_examples=2)
    assert result == {
        "level": "block", "n_comparables": 5, "window": "2025-09..2026-08",
        "median": 300, "p25": 200, "p75": 400, "min": 100, "max": 500,
        "price": 330, "diff_vs_median": 30, "pct_vs_median": 10.0,
        "position": "within_middle_half",
        "examples": [
            {"block_id": "blk_a_main", "sale_month": month, "price": price,
             "storey_low": 7, "storey_high": 9, "floor_area_sqm": 90.0,
             "lease_left_months": 720}
            for month, price in [("2026-05", 500), ("2026-04", 400)]
        ],
        "notes": ["Comparison of past sales, not a valuation"],
    }
    json.dumps(result, allow_nan=False)
    assert_frame_equal(sample, before)


@pytest.mark.parametrize("min_n,level,n,median,p25,p75", [
    (6, "street", 6, 350, 225, 475),
    (7, "town", 7, 400, 250, 550),
    (8, "town", 7, 400, 250, 550),
])
def test_widening(sample, min_n, level, n, median, p25, p75):
    # Six prices: median (300+400)/2; quartiles 200+.25*100, 400+.75*100.
    # Seven prices: median 400; quartiles halfway between 200/300 and 500/600.
    result = compare_price(sample, "blk_a_main", 350, flat_type="4 ROOM", min_n=min_n)
    assert (result["level"], result["n_comparables"]) == (level, n)
    assert (result["median"], result["p25"], result["p75"]) == (median, p25, p75)
    assert f"Widened to {level} level" in result["notes"]
    assert (f"Thin sample: fewer than {min_n} comparables" in result["notes"]) == (n < min_n)


@pytest.mark.parametrize("column,arg,edge,outside", [
    ("storey_mid", "storey_mid", 11, 12),
    ("lease_left_months", "lease_left_months", 780, 781),
    ("floor_area_sqm", "floor_area_sqm", 100, 101),
])
def test_optional_filters(sample, column, arg, edge, outside):
    target = sample.loc[0, column]
    tolerance = edge - target
    sample.loc[1, column] = target - tolerance
    sample.loc[2, column] = edge
    sample.loc[3, column] = outside
    sample.loc[4, column] = target - tolerance - 1
    result = compare_price(sample, "blk_a_main", 200, flat_type="4 ROOM",
                           min_n=3, **{arg: target})
    # Both tolerance endpoints stay in: prices 100, 200, 300 have median 200.
    assert result["n_comparables"] == 3
    assert result["median"] == 200
    assert [row["price"] for row in result["examples"]] == [300, 200, 100]


def test_filters_combine_and_flat_type(sample):
    sample.loc[1, "flat_type"] = "3 ROOM"
    sample.loc[2, "storey_mid"] = 20
    sample.loc[3, "lease_left_months"] = 900
    sample.loc[4, "floor_area_sqm"] = 110
    result = compare_price(sample, "blk_a_main", 100, flat_type="4 ROOM", min_n=1,
                           storey_mid=8, lease_left_months=720, floor_area_sqm=90)
    assert result["n_comparables"] == 1
    assert result["median"] == 100


def test_window_edges_and_default(sample):
    # A three-month window ending in May includes March, but excludes February.
    result = compare_price(sample, "blk_a_main", 400, flat_type="4 ROOM",
                           as_of="2026-05-20", months=3, min_n=3)
    assert result["window"] == "2026-03..2026-05"
    assert [row["price"] for row in result["examples"]] == [500, 400, 300]
    assert result["median"] == 400
    default = compare_price(sample, "blk_a_main", 400, flat_type="4 ROOM")
    explicit = compare_price(sample, "blk_a_main", 400, flat_type="4 ROOM", as_of="2026-08")
    assert default == explicit


@pytest.mark.parametrize("price,position", [
    (199, "below_p25"), (200, "within_middle_half"),
    (300, "within_middle_half"), (400, "within_middle_half"), (401, "above_p75"),
])
def test_position(sample, price, position):
    # Equal to either quartile belongs to the middle half.
    assert compare_price(sample, "blk_a_main", price, flat_type="4 ROOM")["position"] == position


def test_unknown_and_empty(sample):
    for df in (sample, sample.iloc[:0]):
        result = compare_price(df, "unknown", 300, flat_type="4 ROOM")
        assert result["n_comparables"] == 0
        assert result["level"] is None
        assert "Comparison of past sales, not a valuation" in result["notes"]
    result = compare_price(sample, "blk_missing_main", 300, flat_type="4 ROOM")
    assert (result["level"], result["n_comparables"]) == ("town", 7)
    sample.loc[7, "block_id"] = "blk_d_main"
    assert compare_price(sample, "blk_missing_main", 300, flat_type="4 ROOM")["level"] is None


def test_no_matches(sample):
    result = compare_price(sample, "blk_a_main", 300, flat_type="5 ROOM")
    assert (result["level"], result["n_comparables"]) == ("town", 0)
    assert result["examples"] == []
    assert "Thin sample: fewer than 5 comparables" in result["notes"]
    json.dumps(result, allow_nan=False)


def test_fractional_statistics(sample):
    sample = sample.iloc[:2].copy()
    sample["resale_price"] = [100, 101]
    result = compare_price(sample, "blk_a_main", 99, flat_type="4 ROOM", min_n=2)
    # Median 100.5 rounds to even: 100. Quartiles 100.25/100.75 round to 100/101.
    # Asking 99 is 1 below the rounded median, or -1.0 percent.
    assert (result["median"], result["p25"], result["p75"]) == (100, 100, 101)
    assert (result["diff_vs_median"], result["pct_vs_median"]) == (-1, -1.0)
    assert all(type(result[key]) is int for key in ("median", "p25", "p75", "min", "max"))


def test_real_data_smoke():
    path = Path(__file__).resolve().parents[1] / "data/clean/resale.parquet"
    if not path.exists():
        pytest.skip("Clean sales data is unavailable")
    result = compare_price(pd.read_parquet(path), "blk_406_ang-mo-kio-ave-10", 620000,
                           flat_type="4 ROOM", as_of="2026-09")
    assert result["n_comparables"] >= 1
    assert result["level"] in {"block", "street", "town"}
    assert {"window", "median", "p25", "p75", "position", "examples", "notes"} <= result.keys()
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("as_of", ["unknown", "2026-02-30"])
def test_invalid_comparison_date_raises(sample, as_of):
    with pytest.raises(ValueError):
        compare_price(sample, "blk_a_main", 300, flat_type="4 ROOM", as_of=as_of)
