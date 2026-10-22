"""The map's data, cards and selection context come from tables by code; browser ids are never trusted."""

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ask_hdb import api
from ask_hdb.api import mapdata


@pytest.fixture(autouse=True)
def tables(monkeypatch):
    blocks = pd.DataFrame([
        {"block_id": "blk_1_a-st", "block": "1", "street_name": "A ST", "town": "BEDOK", "lat": 1.30, "lng": 103.80},
        {"block_id": "blk_2_b-st", "block": "2", "street_name": "B ST", "town": "BEDOK", "lat": float("nan"), "lng": float("nan")}])
    places = pd.DataFrame([
        {"place_id": "mrt_x", "kind": "mrt", "name": "X", "lat": 1.31, "lng": 103.81},
        {"place_id": "sch_y", "kind": "primary_school", "name": "ST. ANTHONY'S PRIMARY SCHOOL", "lat": 1.301, "lng": 103.801}])
    projects = pd.DataFrame([{"project_id": "bto_z", "name": "Z Vista", "lat": 1.33, "lng": 103.83, "category": "Plus",
                              "units": 100, "wait_months": 40, "town": "BEDOK"},
                             {"project_id": "bto_nosite", "name": "No Site", "lat": float("nan"), "lng": float("nan"),
                              "category": "Standard", "units": 1, "wait_months": 1, "town": float("nan")}])
    sales = pd.DataFrame([
        *[{"block_id": "blk_1_a-st", "sale_month": pd.Timestamp("2026-09-01"), "flat_type": "4 ROOM",
          "lease_commence_year": 1980, "resale_price": 400000 + i * 1000} for i in range(5)],
        {"block_id": "blk_1_a-st", "sale_month": pd.Timestamp("2026-08-01"), "flat_type": "3 ROOM",
         "lease_commence_year": 1980, "resale_price": 300000},
        {"block_id": "blk_1_a-st", "sale_month": pd.Timestamp("2025-01-01"), "flat_type": "4 ROOM",
         "lease_commence_year": 1980, "resale_price": 250000},
        {"block_id": "other", "sale_month": pd.Timestamp("2026-10-01"), "flat_type": "4 ROOM",
         "lease_commence_year": 1990, "resale_price": 500000}])
    for module, name, value in ((mapdata, "load_blocks", blocks), (mapdata, "load_places", places),
                                (mapdata, "load_projects", projects), (mapdata, "load_sales", sales)):
        monkeypatch.setattr(module, name, lambda value=value: value)
    mapdata.features.cache_clear()


def test_features_list_only_located_things_with_clean_labels():
    got = mapdata.features()["features"]
    json.dumps(mapdata.features(), allow_nan=False)  # a NaN anywhere would make the endpoint fail
    assert [f["properties"]["id"] for f in got] == ["blk_1_a-st", "mrt_x", "sch_y", "bto_z"]
    assert got[0]["properties"]["label"] == "Blk 1 A St"
    assert got[2]["properties"]["label"] == "St. Anthony's Primary School (primary school)"


@pytest.mark.parametrize("selected", [None, {}, {"kind": "block", "id": "nope"}, {"kind": "block", "id": "blk_2_b-st"},
                                      {"kind": "mrt", "id": "blk_1_a-st"}, {"kind": "mrt", "id": "sch_y"},
                                      {"kind": "bogus", "id": "x"}, {"kind": "block", "id": 5}])
def test_unknown_or_mismatched_selections_are_dropped(selected):
    assert mapdata.resolve(selected) is None


def test_context_line_is_a_label_without_coordinates():
    line = mapdata.context_line(mapdata.resolve({"kind": "block", "id": "blk_1_a-st"}))
    assert "Blk 1 A St" in line and "block_id=blk_1_a-st" in line and "1.3" not in line
    assert mapdata.context_line(None) is None


def test_block_card_uses_the_datas_latest_month_and_states_its_limits():
    card = mapdata.card(mapdata.resolve({"kind": "block", "id": "blk_1_a-st"}))
    facts = " | ".join(card["facts"])
    assert "Lease started: 1980" in facts and "Sales in the 12 months to 2026-10: 6" in facts
    assert "4 Room: 5 sales, median $402,000" in facts  # a median only where there are enough sales, per flat type
    assert "3 Room: 1 sale (too few for a median)" in facts
    assert "St. Anthony's Primary School" in facts and "Nearest MRT: X" in facts
    assert any("Straight-line" in text for text in card["limits"]) and any("MOE" in text for text in card["limits"])


def test_routes_and_the_selection_reaches_the_agent(monkeypatch):
    seen = {}

    def ask(question, history=None, confirm=False, on_event=None, context=None):
        seen["context"] = context
        return {"answer": "ok", "tokens": 1, "stopped_reason": None, "needs_confirmation": False}

    monkeypatch.setattr(api.agent, "ask", ask)
    client = TestClient(api.create_app())
    assert client.get("/card/block/blk_1_a-st").json()["label"] == "Blk 1 A St"
    assert client.get("/card/block/nope").status_code == 404 and client.get("/card/bogus/x").status_code == 404
    assert len(client.get("/map/features").json()["features"]) == 4
    big = {"type": "FeatureCollection", "features": [{"id": i, "pad": "x" * 50} for i in range(500)]}
    monkeypatch.setattr(mapdata, "features", lambda: big)
    gz = client.get("/map/features", headers={"accept-encoding": "gzip"})
    assert gz.headers["content-encoding"] == "gzip" and len(gz.json()["features"]) == 500
    client.post("/chat", json={"question": "q", "context": {"selected": {"kind": "block", "id": "blk_1_a-st"}}})
    assert "block_id=blk_1_a-st" in seen["context"]
    client.post("/chat", json={"question": "q", "context": {"selected": {"kind": "block", "id": "made-up"}}})
    assert seen["context"] is None
    assert client.post("/chat", json={"question": "q", "context": {"selected": {"kind": "x", "id": "y"}}}).status_code == 422


def test_place_cards_count_blocks_by_straight_line_and_keep_the_school_caveat():
    school = mapdata.card(mapdata.resolve({"kind": "primary_school", "id": "sch_y"}))
    assert "Blocks with resales since 2017 within 1 km (straight-line): 1" in school["facts"] and any("MOE" in t for t in school["limits"])
    station = mapdata.card(mapdata.resolve({"kind": "mrt", "id": "mrt_x"}))
    assert any("within 500 m" in f for f in station["facts"]) and not any("MOE" in t for t in station["limits"])


def test_radius_counts_are_inclusive_straight_line_and_leave_out_the_place_itself():
    mine = mapdata.resolve({"kind": "block", "id": "blk_1_a-st"})
    got = mapdata.around(mine, 0.5)
    assert got["counts"] == {"blocks": 0, "mrt_lrt": 0, "primary_schools": 1, "bto_sites": 0}  # the school is ~140 m away
    far = mapdata.around(mine, 2.0)
    assert far["counts"]["mrt_lrt"] == 1 and far["counts"]["bto_sites"] == 0
    assert any("MOE" in text for text in far["limits"]) and not any("MOE" in t for t in got["limits"])
    with pytest.raises(ValueError):
        mapdata.around(mine, 3.0)


def test_radius_route_accepts_only_the_offered_radii(monkeypatch):
    client = TestClient(api.create_app())
    assert client.get("/around/block/blk_1_a-st?km=1").json()["km"] == 1.0
    assert client.get("/around/block/blk_1_a-st?km=3").status_code == 404
    assert client.get("/around/block/nope?km=1").status_code == 404
    from pathlib import Path
    js = (Path(api.__file__).parent / "static/app.js").read_text()
    assert "radiusRequest" in js and 'mapLayer.ring(null, false)' in js
