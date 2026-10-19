import json

import pytest
from pandas.testing import assert_frame_equal

from ask_hdb.sales import find_sales, price_stats


def test_find_sales_order_and_serializable_rows(sales):
    original = sales.copy(deep=True)
    rows = find_sales(sales)
    assert [row["price"] for row in rows] == [
        500002, 500001, 400000, 200000, 300000, 100000, 100000, 900000,
    ]
    assert rows[0]["sale_month"] == "2024-06"
    assert rows[0]["block_id"] == "blk_005_bedok-nth-st-1"
    assert isinstance(rows[0]["price"], int)
    json.dumps(rows)
    assert_frame_equal(sales, original)


@pytest.mark.parametrize(
    "filters,prices",
    [
        ({"town": "BEDOK"}, [500002, 900000]),
        ({"flat_type": "3 ROOM"}, [500001]),
        ({"block_id": "blk_001a_tampines-st-11"}, [200000, 100000, 100000]),
        ({"storey_min": 11}, [500002, 400000, 100000, 100000, 900000]),
        ({"storey_max": 5}, [500001, 200000]),
        ({"min_lease_months": 897}, [400000, 300000]),
        ({"since": "2024-04"}, [500002, 500001, 400000]),
        ({"until": "2024-02"}, [300000, 100000, 100000, 900000]),
        ({"max_price": 200000}, [200000, 100000, 100000]),
        ({"since": "2024-02-20", "until": "2024-03-15"}, [200000, 300000]),
    ],
)
def test_each_filter_is_inclusive(sales, filters, prices):
    assert [row["price"] for row in find_sales(sales, **filters)] == prices
    assert price_stats(sales, **filters)["n_sales"] == len(prices)


def test_filters_combine(sales):
    filters = {
        "town": "TAMPINES", "flat_type": "4 ROOM", "block_id": "blk_002_tampines-st-11",
        "storey_min": 8, "storey_max": 11, "min_lease_months": 736,
        "since": "2024-02", "until": "2024-04", "max_price": 300000,
    }
    assert [row["price"] for row in find_sales(sales, **filters)] == [300000]
    assert price_stats(sales, **filters) == {
        "n_sales": 1, "median": 300000, "mean": 300000, "min": 300000, "max": 300000,
        "p25": 300000, "p75": 300000, "period": "2024-02..2024-02",
    }


def test_stats_are_computed_over_all_matches(sales):
    original = sales.copy(deep=True)
    # Sorted prices are 100000, 100000, 200000, 300000, 400000.
    # Their sum is 1100000, so the mean is 220000 and the middle price is 200000.
    # Quartiles land exactly on the second and fourth prices: 100000 and 300000.
    assert price_stats(sales, town="TAMPINES", flat_type="4 ROOM") == {
        "n_sales": 5, "median": 200000, "mean": 220000, "min": 100000, "max": 400000,
        "p25": 100000, "p75": 300000, "period": "2024-01..2024-04",
    }
    assert_frame_equal(sales, original)


def test_fractional_statistics_are_plain_rounded_ints(sales):
    # 500001 and 500002 average to 500001.5; quartiles are .25 and .75.
    result = price_stats(sales, since="2024-05")
    assert result == {
        "n_sales": 2, "median": 500002, "mean": 500002, "min": 500001, "max": 500002,
        "p25": 500001, "p75": 500002, "period": "2024-05..2024-06",
    }
    assert all(type(value) is int for key, value in result.items() if key != "period")


def test_limit_and_equal_month_order(sales):
    assert [row["price"] for row in find_sales(sales, limit=2)] == [500002, 500001]
    assert find_sales(sales, limit=0) == []
    sales.loc[4, "sale_month"] = sales.loc[5, "sale_month"]
    assert [row["price"] for row in find_sales(sales, limit=2)] == [500001, 500002]


@pytest.mark.parametrize(
    "filters",
    [
        {"town": "unknown"}, {"flat_type": "unknown"}, {"block_id": "unknown"},
        {"storey_min": 20}, {"min_lease_months": 1200}, {"max_price": 1},
        {"since": "2025-01"}, {"since": "2024-04", "until": "2024-01"},
    ],
)
def test_empty_results(sales, filters):
    assert find_sales(sales, **filters) == []
    assert price_stats(sales, **filters) == {"n_sales": 0}


def test_empty_source(sales):
    assert find_sales(sales.iloc[:0]) == []
    assert price_stats(sales.iloc[:0]) == {"n_sales": 0}


@pytest.mark.parametrize("function", [find_sales, price_stats])
@pytest.mark.parametrize("bound", ["since", "until"])
@pytest.mark.parametrize("value", ["unknown", "2024-02-30", "NaT"])
@pytest.mark.parametrize("empty", [False, True])
def test_invalid_date_bounds_raise(sales, function, bound, value, empty):
    source = sales.iloc[:0] if empty else sales
    with pytest.raises(ValueError, match=f"Invalid {bound} date"):
        function(source, **{bound: value})
