"""Offline joins and bearings must not guess a block or a unit's facing."""

import json
import runpy
from math import cos, radians, sin

import pandas as pd
import pytest

from ask_hdb.geo.outlines import compass, long_axis, simplify_polygon, simplify_ring

build = runpy.run_path("scripts/build_buildings.py")["build"]


def rectangle(bearing=0):
    # A long north-south rectangle, rotated clockwise around its centre.
    theta = radians(bearing)
    ring = [[103.8 + (x * cos(theta) + y * sin(theta)) / cos(radians(1.3)),
             1.3 + y * cos(theta) - x * sin(theta)]
            for x, y in [(-.00005, -.0002), (.00005, -.0002), (.00005, .0002), (-.00005, .0002)]]
    return ring + ring[:1]


@pytest.mark.parametrize("bearing", [0, 30, 45, 90, 135])
def test_minimum_rectangle_long_axis_is_a_compass_bearing(bearing):
    assert long_axis(rectangle(bearing)) == pytest.approx(bearing, abs=.1)


def test_simplification_keeps_corners_closure_and_rounding():
    ring = rectangle()
    midpoint = [(a + b) / 2 for a, b in zip(ring[0], ring[1])]
    got = simplify_ring([ring[0], midpoint, *ring[1:]])
    assert len(got) == 5 and got[0] == got[-1]
    assert all(v == round(v, 6) for p in got for v in p)
    assert [compass(b) for b in [0, 45, 90, 225, 359]] == ["N", "NE", "E", "SW", "N"]


def test_holes_that_collapse_on_the_rounded_grid_are_removed():
    sliver = [[103.8, 1.3], [103.800001, 1.3], [103.800001, 1.30000001], [103.8, 1.3]]
    assert len(simplify_polygon([rectangle(), sliver])) == 1
    with pytest.raises(ValueError, match="exterior collapsed"):
        simplify_polygon([sliver])


def test_postal_join_normalized_height_join_and_fallbacks():
    blocks = pd.DataFrame([
        {"block_id": key, "block": str(i), "street_name": "A AVE", "postal": postal}
        for i, (key, postal) in enumerate([("exact", "012345"), ("sales", "123456"),
                                           ("default", "234567"), ("unknown", "NIL")], 1)])
    props = pd.DataFrame([{"blk_no": "1", "street": "A AVENUE", "max_floor_lvl": 20}])
    sales = pd.DataFrame([{"block_id": "exact", "storey_high": 21}, {"block_id": "sales", "storey_high": 9}])
    outlines = {"features": [{"properties": {"POSTAL_COD": p},
                               "geometry": {"type": "Polygon", "coordinates": [rectangle()]}}
                              for p in ["012345", "123456", "234567", "NIL", "999999"]]}
    result, report = build(outlines, blocks, props, sales)
    rows = {f["properties"]["block_id"]: f["properties"] for f in result["features"]}
    assert report["matched_outlines"] == 3 and report["outline_match_pct"] == 60
    assert [(rows[k]["floors"], rows[k]["height_source"]) for k in ["exact", "sales", "default"]] == [
        (20, "property_info"), (9, "sales"), (4, "default")]
    assert rows["exact"]["height_m"] == 56 and rows["exact"]["facing"] == [90, 270]
    assert rows["exact"]["facing_label"] == "E and W"
    json.dumps(result, allow_nan=False)
    # Duplicate postal matches are unsafe; disjoint shapes for a single block remain one feature.
    result, report = build(outlines, pd.concat([blocks, blocks.iloc[:1].assign(block_id="duplicate")]), props, sales)
    assert report["matched_outlines"] == 2
    result, report = build({"features": outlines["features"][:1] * 2}, blocks, props, sales)
    assert report["matched_outlines"] == 2 and len(result["features"]) == 1
    assert result["features"][0]["geometry"]["type"] == "MultiPolygon"
