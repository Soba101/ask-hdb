"""Offline builders preserve identifiers and coordinate conventions."""

import runpy

import pandas as pd

build_places = runpy.run_path("scripts/build_places.py")["build_places"]
check_geocodes = runpy.run_path("scripts/check_geocodes.py")["check_geocodes"]


def exit_feature(name, lng, lat):
    return {"properties": {"STATION_NA": name},
            "geometry": {"type": "Point", "coordinates": [lng, lat]}}


def test_grouping_ids_and_coordinate_order():
    exits = {"features": [exit_feature("FOO MRT STATION", 103, 1),
                          exit_feature("FOO MRT STATION", 105, 3),
                          exit_feature("Foo MRT STATION", 106, 4)]}
    schools = pd.DataFrame({"school_name": ["Primary A", "Mixed B", "Secondary C"],
                            "postal_code": ["012345", "234567", "345678"],
                            "mainlevel_code": ["PRIMARY", "MIXED LEVEL (P1-S4)", "SECONDARY"]})
    places = build_places(exits, schools).set_index("place_id")
    assert set(places.index) == {"mrt_foo", "mrt_foo-2", "school_primary-a", "school_mixed-b"}
    assert places.loc["mrt_foo", "lat"] == 2
    assert places.loc["mrt_foo", "lng"] == 104
    assert places.loc["mrt_foo", "exit_count"] == 2
    assert places.loc["school_primary-a", "postal_code"] == "012345"
    assert pd.isna(places.loc["school_primary-a", "lat"])
    shuffled = build_places({"features": exits["features"][::-1]}, schools.iloc[::-1])
    pd.testing.assert_frame_equal(places.reset_index(), shuffled)


def test_check_geocodes_partial_data():
    buildings = {"features": [{"properties": {"POSTAL_COD": "012345"},
                               "geometry": {"type": "Polygon", "coordinates": [
                                   [[103, 0], [105, 0], [105, 2], [103, 2], [103, 0]]]}}]}
    blocks = pd.DataFrame({"block_id": ["good", "off", "missing"],
                           "postal": ["012345", "012345", "999999"],
                           "lat": [1., 1.01, 1.], "lng": [104., 104., 104.]})
    report = check_geocodes(blocks, buildings)
    assert "matched: 2\nunmatched: 1\nover 300 m: 1" in report
    assert "off: 1112.0 m" in report
    assert "good:" not in report
    assert "matched: 0\nunmatched: 0" in check_geocodes(blocks.iloc[:0], buildings)
