"""Map points are found by code from ids in tool arguments and results."""

import pandas as pd
import pytest

from ask_hdb.api import points


@pytest.fixture(autouse=True)
def tables(monkeypatch):
    blocks = pd.DataFrame([
        {"block_id": "blk_1_a-st", "block": "1", "street_name": "A ST", "lat": 1.30, "lng": 103.80},
        {"block_id": "blk_2_b-st", "block": "2", "street_name": "B ST", "lat": float("nan"), "lng": float("nan")}])
    places = pd.DataFrame([
        {"place_id": "mrt_x", "kind": "mrt", "name": "X", "lat": 1.31, "lng": 103.81},
        {"place_id": "sch_y", "kind": "primary_school", "name": "Y PRIMARY", "lat": 1.32, "lng": 103.82}])
    projects = pd.DataFrame([{"project_id": "bto_z", "name": "Z Vista", "lat": 1.33, "lng": 103.83}])
    monkeypatch.setattr(points, "load_blocks", lambda: blocks)
    monkeypatch.setattr(points, "load_places", lambda: places)
    monkeypatch.setattr(points, "load_projects", lambda: projects)


def test_origin_block_and_nearest_places():
    got = points.map_points({"block_id": "blk_1_a-st"}, {"places": [{"place_id": "mrt_x"}, {"place_id": "sch_y"}]})
    assert [(p["kind"], p["role"]) for p in got] == [("block", "origin"), ("mrt", "result"), ("primary_school", "result")]
    assert got[1]["label"] == "X (MRT)" and got[0]["lat"] == 1.3


def test_sales_rows_and_bto_projects_and_the_approximate_note():
    got = points.map_points({}, {"sales": [{"block_id": "blk_1_a-st"}, {"block_id": "blk_1_a-st"}],
                                 "projects": [{"project_id": "bto_z"}]})
    assert [p["id"] for p in got] == ["blk_1_a-st", "bto_z"]  # a block is listed once
    assert got[1]["note"] == "approximate site"


def test_blocks_without_coordinates_and_unknown_ids_are_left_out():
    assert points.map_points({"block_id": "blk_2_b-st"}, {"sales": [{"block_id": "nope"}]}) == []


def test_the_number_of_points_is_capped(monkeypatch):
    many = pd.DataFrame([{"block_id": f"b{i}", "block": str(i), "street_name": "S", "lat": 1.3, "lng": 103.8}
                         for i in range(100)])
    monkeypatch.setattr(points, "load_blocks", lambda: many)
    got = points.map_points({}, {"sales": [{"block_id": f"b{i}"} for i in range(100)]})
    assert len(got) == points.MAX_POINTS
