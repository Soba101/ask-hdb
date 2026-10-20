"""Distance calculations use tiny coordinate tables, never remote data."""

import pandas as pd
import pytest

from ask_hdb.geo.distance import haversine_km, nearest, within_km


@pytest.fixture
def geo_tables():
    blocks = pd.DataFrame({"block_id": ["b", "far", "pending"],
                           "lat": [0., 10., None], "lng": [0., 0., None]})
    places = pd.DataFrame({"place_id": ["mrt_far", "mrt_near", "school_pending"],
                           "kind": ["mrt", "mrt", "primary_school"],
                           "name": ["Far", "Near", "Pending"],
                           "lat": [1., .1, None], "lng": [0., 0., None]})
    return blocks, places


def test_known_distance():
    assert haversine_km(0, 0, 1, 0) == pytest.approx(111.195, abs=.01)
    assert haversine_km(1, 103, 1, 103) == 0


def test_nearest_and_within(geo_tables):
    blocks, places = geo_tables
    result = nearest(blocks, places, "b", "mrt")
    assert [row["place_id"] for row in result] == ["mrt_near", "mrt_far"]
    assert result[0]["method"] == "straight-line"
    assert within_km(blocks, places, "mrt", 12) == {"b"}
    assert within_km(blocks, places, "mrt", 0) == set()
    assert within_km(blocks.iloc[:0], places, "mrt", 12) == set()


@pytest.mark.parametrize("block,kind,message", [
    ("missing", "mrt", "No coordinates for block_id"), ("pending", "mrt", "Missing coordinates"),
    ("b", "unknown", "Unknown kind"), ("b", "primary_school", "Missing coordinates"),
])
def test_nearest_errors(geo_tables, block, kind, message):
    with pytest.raises(ValueError, match=message):
        nearest(*geo_tables, block, kind)


@pytest.mark.parametrize("km", [-1, float("nan"), float("inf")])
def test_bad_radius(geo_tables, km):
    with pytest.raises(ValueError, match="km"):
        within_km(*geo_tables, "mrt", km)


def test_broadcast_and_chunking(geo_tables):
    blocks, places = geo_tables
    repeated = pd.concat([blocks.iloc[:1]] * 2100, ignore_index=True)
    assert within_km(repeated, places, "mrt", 12) == {"b"}
    with pytest.raises(ValueError, match="Missing coordinates"):
        within_km(blocks, places, "primary_school", 1)
