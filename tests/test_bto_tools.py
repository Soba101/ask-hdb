"""BTO launch tools on small tables (no real data)."""

import pandas as pd
import pytest

from ask_hdb import tools
from ask_hdb.bto import queries

PROJECTS = pd.DataFrame([
    {"project_id": "bto_a", "name": "A", "category": "Standard", "first_launch": "2026-02", "wait_months": 30, "units": 300,
     "lat": 1.35, "lng": 103.85, "road_name": "R", "town": "TAMPINES", "site": "approximate"},
    {"project_id": "bto_b", "name": "B", "category": "Prime", "first_launch": "2025-10", "wait_months": 50, "units": 100,
     "lat": None, "lng": None, "road_name": None, "town": None, "site": "not_found"}])
FLATS = pd.DataFrame([
    {"launch": "2026-02", "project_id": "bto_a", "flat_type": "4-room", "units": 200, "price_low": 300000, "price_high": 400000},
    {"launch": "2026-02", "project_id": "bto_a", "flat_type": "3-room", "units": 100, "price_low": 200000, "price_high": 250000},
    {"launch": "2025-10", "project_id": "bto_b", "flat_type": "4-room", "units": 100, "price_low": 500000, "price_high": 700000}])
PLACES = pd.DataFrame([
    {"place_id": "mrt_x", "kind": "mrt", "name": "X", "lat": 1.351, "lng": 103.85},
    {"place_id": "mrt_y", "kind": "mrt", "name": "Y", "lat": 1.40, "lng": 103.85}])


@pytest.fixture(autouse=True)
def tables(monkeypatch):
    monkeypatch.setattr(queries, "load_projects", lambda: PROJECTS)
    monkeypatch.setattr(queries, "load_flats", lambda: FLATS)
    monkeypatch.setattr(queries, "load_places", lambda: PLACES)


ALL = {"name": None, "town": None, "flat_type": None, "launch_month": None, "category": None, "max_price": None}


def test_filters_are_optional():
    assert tools.list_bto_projects.invoke(ALL)["n_projects"] == 2
    town = tools.list_bto_projects.invoke(ALL | {"town": "tampines"})
    assert [p["name"] for p in town["projects"]] == ["A"]
    cheap = tools.list_bto_projects.invoke(ALL | {"flat_type": "4-room", "max_price": 350000})
    assert [(p["name"], [f["flat_type"] for f in p["flats"]]) for p in cheap["projects"]] == [("A", ["4-room"])]
    assert tools.list_bto_projects.invoke(ALL | {"launch_month": "2025-10"})["projects"][0]["name"] == "B"
    assert tools.list_bto_projects.invoke(ALL | {"category": "Prime"})["projects"][0]["town"].startswith("unknown")
    assert "note" in cheap and "indicative" in cheap["note"].lower()
    assert tools.list_bto_projects.invoke({"name": "A"})["n_projects"] == 1  # filters can be left out
    assert tools.list_bto_projects.invoke({"name": "A", "category": "", "max_price": "None"})["n_projects"] == 1


def test_nearby_uses_the_approximate_site_and_reports_missing_coordinates():
    near = tools.bto_nearby.invoke({"project_id": "bto_a", "kind": "mrt", "n": 2})
    assert [p["place_id"] for p in near["places"]] == ["mrt_x", "mrt_y"]
    assert near["places"][0]["km"] == pytest.approx(0.111, abs=0.01)
    assert "No site coordinates" in tools.bto_nearby.invoke({"project_id": "bto_b", "kind": "mrt"})["error"]
    assert "Unknown project_id" in tools.bto_nearby.invoke({"project_id": "bto_z", "kind": "mrt"})["error"]


def test_empty_text_is_only_no_value_for_bto_filters():
    from pydantic import ValidationError

    from ask_hdb.tool_inputs import CompareArgs
    with pytest.raises(ValidationError):
        CompareArgs.model_validate({"block_id": "x", "flat_type": "4 ROOM", "price": 1, "storey_mid": "",
                                    "lease_left_months": None, "floor_area_sqm": None, "as_of": "latest"})


def test_resale_flat_type_accepts_bto_style_names():
    from ask_hdb.tool_inputs import CompareArgs, SalesArgs
    for text in ("3-room", "3 room", "3-ROOM", "3 rooms"):
        assert SalesArgs(flat_type=text).flat_type == "3 ROOM"
    assert SalesArgs(flat_type="Multi-Generation").flat_type == "MULTI-GENERATION"
    assert SalesArgs(flat_type="3ROOM").flat_type == "3 ROOM"
    compare = CompareArgs(block_id="x", price=1, flat_type="4-room", storey_mid=None, lease_left_months=None,
                          floor_area_sqm=None, as_of="latest")
    assert compare.flat_type == "4 ROOM"
