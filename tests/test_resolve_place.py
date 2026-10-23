"""resolve_place: places named in words become ids by code, with ambiguity, towns and misses handled."""

import pandas as pd
import pytest

from ask_hdb.geo import filters, resolve


@pytest.fixture(autouse=True)
def tables(monkeypatch):
    blocks = pd.DataFrame([
        {"block_id": "blk_227_bishan-st-23", "block": "227", "street_name": "BISHAN ST 23", "town": "BISHAN", "lat": 1.35, "lng": 103.85},
        {"block_id": "blk_227_bt-batok-ctrl", "block": "227", "street_name": "BT BATOK CTRL", "town": "BUKIT BATOK", "lat": 1.35, "lng": 103.76},
        {"block_id": "blk_227_bishan-st-22", "block": "227", "street_name": "BISHAN ST 22", "town": "BISHAN", "lat": 1.351, "lng": 103.851},
        {"block_id": "blk_5a_bishan-st-23", "block": "5A", "street_name": "BISHAN ST 23", "town": "BISHAN", "lat": 1.36, "lng": 103.86},
        {"block_id": "blk_9_nolatlng", "block": "9", "street_name": "X RD", "town": "BISHAN", "lat": float("nan"), "lng": float("nan")}])
    places = pd.DataFrame([
        {"place_id": "mrt_bishan", "kind": "mrt", "name": "BISHAN", "lat": 1.351, "lng": 103.849},
        {"place_id": "school_catholic-high-school", "kind": "primary_school", "name": "CATHOLIC HIGH SCHOOL", "lat": 1.352, "lng": 103.848},
        {"place_id": "school_bishan-primary", "kind": "primary_school", "name": "BISHAN PRIMARY SCHOOL", "lat": 1.353, "lng": 103.847},
        {"place_id": "school_far", "kind": "primary_school", "name": "FAR PRIMARY SCHOOL", "lat": 1.45, "lng": 103.8}])
    projects = pd.DataFrame([{"project_id": "bto_nova", "name": "Bishan Nova", "lat": 1.355, "lng": 103.85}])
    for module in (resolve, filters):
        monkeypatch.setattr(module, "load_places", lambda: places)
    monkeypatch.setattr(resolve, "load_blocks", lambda: blocks)
    monkeypatch.setattr(resolve, "load_projects", lambda: projects)
    monkeypatch.setattr(filters, "load_projects", lambda: projects)
    resolve._block_index.cache_clear()


@pytest.mark.parametrize("text", ["Blk 227 Bishan St 23", "block 227 BISHAN STREET 23", "227 bishan st 23"])
def test_a_block_named_in_full_is_one_candidate(text):
    got = resolve.resolve_place(text)
    assert got["status"] == "ok" and got["candidates"][0]["id"] == "blk_227_bishan-st-23"
    assert got["candidates"][0]["label"] == "Blk 227 Bishan St 23" and got["candidates"][0]["town"] == "Bishan"


def test_a_part_of_the_street_or_only_the_number_is_ambiguous_and_never_picked_for_the_user():
    partial = resolve.resolve_place("blk 227 bishan")
    assert partial["status"] == "ambiguous" and {c["id"] for c in partial["candidates"]} == {
        "blk_227_bishan-st-23", "blk_227_bishan-st-22"} and "Do not pick" in partial["note"]
    assert resolve.resolve_place("227")["n_matches"] == 3
    assert resolve.resolve_place("5a bishan st 23")["status"] == "ok"


def test_names_of_stations_schools_and_projects():
    assert resolve.resolve_place("Bishan MRT")["candidates"][0]["id"] == "mrt_bishan"
    assert resolve.resolve_place("catholic high school")["candidates"][0]["kind"] == "primary_school"
    assert resolve.resolve_place("Bishan Nova")["candidates"][0]["id"] == "bto_nova"
    school = resolve.resolve_place("Bishan primary school")
    assert school["status"] == "ok" and school["candidates"][0]["id"] == "school_bishan-primary"


def test_a_bare_town_is_not_a_point_and_unknown_or_unlocated_places_are_not_found():
    assert resolve.resolve_place("Bishan")["status"] == "town" and resolve.resolve_place("Bishan")["candidates"] == []
    assert resolve.resolve_place("Blk 9999 Nowhere Rd")["status"] == "not_found"
    assert resolve.resolve_place("blk 9 x rd")["status"] == "not_found"  # a block without coordinates cannot be placed
    assert resolve.resolve_place("   ")["status"] == "not_found"


def test_nearest_places_from_a_station_or_a_bto_site_never_returns_the_origin_itself():
    got = filters.nearest_places("mrt_bishan", "primary_school", 2)
    assert [p["place_id"] for p in got["places"]] == ["school_catholic-high-school", "school_bishan-primary"]
    near = filters.nearest_places("bto_nova", "primary_school", 5, within_km=2)
    assert near["n_within"] == 2 and "approximate site" in near["note"]
    with pytest.raises(ValueError, match="Unknown id"):
        filters.nearest_places("mrt_nowhere", "mrt")


def test_a_label_from_a_tool_result_is_a_name_but_other_numbers_still_need_evidence():
    from ask_hdb import grounding

    results = [{"candidates": [{"label": "Blk 227 Bishan St 23", "id": "x"}, {"label": "227 Ang Mo Kio Ave 3", "id": "y"}],
                "n_within": 9, "note": "See 99 places"}]
    named = grounding.check("Did you mean Blk 227 Bishan St 23 or 227 Ang Mo Kio Ave 3?", "How far from Blk 227?", results)
    assert named["ungrounded"] == []
    invented = grounding.check("Blk 227 Bishan St 23 has 23 primary schools nearby.", "q", results)
    assert invented["ungrounded"] == ["23"]  # the name is left out, the invented count is not
