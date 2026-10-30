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
          "lease_commence_year": 1980, "lease_left_months": 636, "resale_price": 400000 + i * 1000, "floor_area_sqm": 100} for i in range(5)],
        {"block_id": "blk_1_a-st", "sale_month": pd.Timestamp("2026-08-01"), "flat_type": "3 ROOM",
         "lease_commence_year": 1980, "lease_left_months": 637, "resale_price": 300000, "floor_area_sqm": 100},
        {"block_id": "blk_1_a-st", "sale_month": pd.Timestamp("2025-01-01"), "flat_type": "4 ROOM",
         "lease_commence_year": 1980, "lease_left_months": 660, "resale_price": 250000, "floor_area_sqm": 100},
        {"block_id": "other", "sale_month": pd.Timestamp("2026-10-01"), "flat_type": "4 ROOM",
         "lease_commence_year": 1990, "lease_left_months": 700, "resale_price": 500000, "floor_area_sqm": 100}])
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
    assert got["counts"] == {"blocks": 0, "mrt_lrt": 0, "primary_schools": 1, "bto_sites": 0, "bto_upcoming": 0}  # the school is ~140 m away
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
    js = (Path(api.__file__).parent / "static/card-map.js").read_text()
    assert "radiusRequest" in js and "mapLayer.ring(selected ?" in js
    assert "schoolRings" in js and "{ km: 2, dash: true }, { km: 1, dash: false }" in js


def test_schools_within_two_km_are_banded_and_the_moe_caveat_is_attached():
    mine = mapdata.resolve({"kind": "block", "id": "blk_1_a-st"})
    got = mapdata.schools_nearby(mine)
    assert [(s["id"], s["band"]) for s in got["schools"]] == [("sch_y", "within 1 km")]
    assert any("boundary" in text and "does not guarantee" in text for text in got["limits"])
    assert got["schools"][0]["km"] < 0.2 and got["schools"][0]["label"] == "St. Anthony's Primary School"


def test_borderline_schools_and_the_route(monkeypatch):
    places = pd.DataFrame([
        {"place_id": "near", "kind": "primary_school", "name": "NEAR PRIMARY", "lat": 1.30, "lng": 103.8},
        {"place_id": "mid", "kind": "primary_school", "name": "MID PRIMARY", "lat": 1.315, "lng": 103.8},    # ~1.7 km
        {"place_id": "edge", "kind": "primary_school", "name": "EDGE PRIMARY", "lat": 1.3205, "lng": 103.8},  # ~2.3 km
        {"place_id": "far", "kind": "primary_school", "name": "FAR PRIMARY", "lat": 1.40, "lng": 103.8},
        {"place_id": "mrt_q", "kind": "mrt", "name": "Q", "lat": 1.30, "lng": 103.8}])
    monkeypatch.setattr(mapdata, "load_places", lambda: places)
    got = mapdata.schools_nearby({"id": "blk_1_a-st", "lat": 1.30, "lng": 103.8})
    assert [(s["id"], s["band"]) for s in got["schools"]] == [("near", "within 1 km"), ("mid", "1 to 2 km"), ("edge", "borderline")]
    client = TestClient(api.create_app())
    assert client.get("/schools/block/blk_1_a-st").json()["km"] == 2.0 and client.get("/schools/block/nope").status_code == 404


def test_place_names_keep_acronyms_and_small_words():
    from ask_hdb.geo.names import pretty_name
    assert pretty_name("CHIJ OUR LADY OF GOOD COUNSEL") == "CHIJ Our Lady of Good Counsel"
    assert pretty_name("ST. ANTHONY'S PRIMARY SCHOOL") == "St. Anthony's Primary School"


def test_metrics_give_a_median_only_with_enough_recent_sales_and_a_lease_estimate():
    mapdata.metrics.cache_clear()
    got = mapdata.metrics("4 ROOM")
    row = got["blocks"]["blk_1_a-st"]
    # six 4-room sales in 24 months (3-room one left out); newest sale 2026-09 had 636 months left, so 635 at 2026-10: 52 years
    assert row[:3] == [401500, 6, 52] and got["as_of"] == "2026-10"
    assert got["blocks"]["other"][0] is None and got["blocks"]["other"][1] == 1  # one sale: no median
    assert row[4] == 4015 and row[5] == 373  # median $401,500 over 100 sqm: $4,015 per sqm, $373 per sq ft
    assert got["blocks"]["other"][4] is None and got["blocks"]["other"][5] is None
    assert any("not a valuation" in text for text in got["limits"])
    with pytest.raises(ValueError):
        mapdata.metrics("1 ROOM")


def test_metrics_route_accepts_only_the_offered_flat_types():
    mapdata.metrics.cache_clear()
    client = TestClient(api.create_app())
    assert client.get("/map/metrics?flat_type=4 ROOM").json()["window_months"] == 24
    assert client.get("/map/metrics?flat_type=1 ROOM").status_code == 404


def test_metrics_boundaries_for_the_window_and_the_minimum_sales(monkeypatch):
    sales = pd.DataFrame([
        {"block_id": "edge", "sale_month": pd.Timestamp("2024-11-01"), "flat_type": "4 ROOM", "lease_commence_year": 1990,
         "lease_left_months": 700, "resale_price": 500000, "floor_area_sqm": 100},   # exactly 24 months before 2026-10: inside
        {"block_id": "edge", "sale_month": pd.Timestamp("2024-10-01"), "flat_type": "4 ROOM", "lease_commence_year": 1990,
         "lease_left_months": 701, "resale_price": 900000, "floor_area_sqm": 100},   # one month earlier: outside
        {"block_id": "edge", "sale_month": pd.Timestamp("2026-10-01"), "flat_type": "4 ROOM", "lease_commence_year": 1990,
         "lease_left_months": 670, "resale_price": 520000, "floor_area_sqm": 100},
        {"block_id": "three", "sale_month": pd.Timestamp("2026-10-01"), "flat_type": "4 ROOM", "lease_commence_year": 2000,
         "lease_left_months": 900, "resale_price": 600000, "floor_area_sqm": 100},
        {"block_id": "three", "sale_month": pd.Timestamp("2026-09-01"), "flat_type": "4 ROOM", "lease_commence_year": 2000,
         "lease_left_months": 899, "resale_price": 610000, "floor_area_sqm": 100},
        {"block_id": "three", "sale_month": pd.Timestamp("2026-08-01"), "flat_type": "4 ROOM", "lease_commence_year": 2000,
         "lease_left_months": 898, "resale_price": 620000, "floor_area_sqm": 100}])
    monkeypatch.setattr(mapdata, "load_sales", lambda: sales)
    mapdata.metrics.cache_clear()
    got = mapdata.metrics("4 ROOM")["blocks"]
    assert got["edge"][:2] == [None, 2]          # two sales in the window: no median
    assert got["three"][:3] == [610000, 3, 75]       # exactly three sales: a median; 900 months left = 75 years
    mapdata.metrics.cache_clear()


def _sales_with_lease_starts(starts):
    return pd.DataFrame([
        {"block_id": f"b{y}", "sale_month": pd.Timestamp("2026-10-01"), "flat_type": "4 ROOM", "lease_commence_year": y,
         "lease_left_months": 900, "resale_price": 500000, "floor_area_sqm": 100} for y in starts])


def test_mop_codes_at_the_edge_years(monkeypatch):
    # Data year 2026, MOP 5 years: start 2020 ended in 2025 (past), 2021 ends in 2026 (this data year), 2022 ends in 2027 (within).
    monkeypatch.setattr(mapdata, "load_sales", lambda: _sales_with_lease_starts([2020, 2021, 2022]))
    mapdata.metrics.cache_clear()
    got = mapdata.metrics("4 ROOM")
    assert [got["blocks"][f"b{y}"][3] for y in (2020, 2021, 2022)] == [2, 1, 0]
    assert got["mop_years"] == 5 and got["mop_rule"]["id"] == "mop.standard_years" and "5 years" in got["mop_limits"]
    assert "Plus and Prime flats have a 10-year MOP" in got["mop_limits"]  # not every flat is 5 years
    mapdata.metrics.cache_clear()


def test_mop_years_come_from_the_rules_getter(monkeypatch):
    monkeypatch.setattr(mapdata, "load_sales", lambda: _sales_with_lease_starts([2016]))
    mapdata.metrics.cache_clear()
    assert mapdata.metrics("4 ROOM")["blocks"]["b2016"][3] == 2
    monkeypatch.setattr(mapdata, "_mop_years", lambda: 10)
    mapdata.metrics.cache_clear()
    got = mapdata.metrics("4 ROOM")
    assert got["blocks"]["b2016"][3] == 1 and got["mop_years"] == 10 and "10 years" in got["mop_limits"]
    mapdata.metrics.cache_clear()


def test_block_card_has_an_approximate_mop_fact():
    card = mapdata.card(mapdata.resolve({"kind": "block", "id": "blk_1_a-st"}))
    assert "MOP (estimated, approximate): past MOP" in card["facts"]
    assert any("approximate" in text and "Check HDB" in text for text in card["limits"])


def test_bto_estimated_completion(monkeypatch):
    projects = pd.DataFrame([
        {"project_id": "p1", "name": "P1", "lat": 1.3, "lng": 103.8, "category": "Standard", "units": 10, "wait_months": 47,
         "first_launch": "2025-02", "town": "BEDOK"},
        {"project_id": "p2", "name": "P2", "lat": 1.3, "lng": 103.8, "category": "Standard", "units": 10, "wait_months": 47,
         "first_launch": None, "town": "BEDOK"},
        {"project_id": "p3", "name": "P3", "lat": 1.3, "lng": 103.8, "category": "Standard", "units": 10, "wait_months": 12,
         "first_launch": "2020-01", "town": "BEDOK"},
        {"project_id": "p4", "name": "P4", "lat": 1.3, "lng": 103.8, "category": "Standard", "units": 10, "wait_months": 5,
         "first_launch": "garbage", "town": "BEDOK"}])
    monkeypatch.setattr(mapdata, "load_projects", lambda: projects)
    facts = {p: mapdata.card({"kind": "bto", "id": p, "label": p})["facts"] for p in ("p1", "p2", "p3", "p4")}
    assert any(f.startswith("Estimated completion: about 2029-01") and "approximate" in f for f in facts["p1"])
    assert not any("Estimated" in f for f in facts["p2"] + facts["p4"])
    assert "Estimated completion has passed; check HDB for the actual date." in facts["p3"]


def test_upcoming_bto_sites_are_labelled_not_on_sale_and_counted_apart(monkeypatch):
    projects = pd.DataFrame([
        {"project_id": "bto_z", "name": "Z Vista", "lat": 1.33, "lng": 103.83, "category": "Plus", "units": 100, "wait_months": 40,
         "town": "BEDOK", "status": "launched", "flat_types": None, "first_launch": "2026-02"},
        {"project_id": "bto_up_x", "name": "Tengah upcoming BTO (HDB code X)", "lat": 1.331, "lng": 103.831, "category": None, "units": 710,
         "wait_months": float("nan"), "town": "TENGAH", "status": "upcoming", "flat_types": "2-room Flexi, 4-room", "first_launch": "2026-11"}])
    monkeypatch.setattr(mapdata, "load_projects", lambda: projects)
    mapdata.features.cache_clear()
    props = {f["properties"]["id"]: f["properties"] for f in mapdata.features()["features"] if f["properties"]["kind"] == "bto"}
    assert props["bto_up_x"]["status"] == "upcoming" and "not on sale yet" in props["bto_up_x"]["label"]
    assert props["bto_z"]["status"] == "launched" and "not on sale" not in props["bto_z"]["label"]
    text = " ".join(mapdata.card(mapdata.resolve({"kind": "bto", "id": "bto_up_x"}))["facts"])
    assert "Not on sale yet" in text and "November 2026" in text and "Units: 710" in text and "2-room Flexi" in text
    assert "Waiting time" not in text and "Estimated completion" not in text and "No prices" in text
    counts = mapdata.around(mapdata.resolve({"kind": "bto", "id": "bto_z"}), 2.0)["counts"]
    assert counts["bto_upcoming"] == 1 and counts["bto_sites"] == 0  # the place itself is left out, the upcoming one is counted apart
