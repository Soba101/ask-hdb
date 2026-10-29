"""Nearest places, walking routes and the amenity build: all offline (fake data, fake OneMap, fake Overpass)."""

import sys
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ask_hdb.api import amenities, create_app
from ask_hdb.geo.client import OneMap
from ask_hdb.geo.route import RouteError, decode_polyline, parse_route

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_amenities

CREDS = {"email": "e", "password": "p"}
START = {"kind": "block", "id": "b1", "label": "Blk 1", "lat": 1.30, "lng": 103.80}
AMENITIES = pd.DataFrame([
    {"id": "osm:node/1", "kind": "supermarket", "name": "Near Mart", "ref": None, "lat": 1.301, "lng": 103.80, "place_id": None, "source": "OSM", "as_of": "2026-10-29"},
    {"id": "osm:node/2", "kind": "supermarket", "name": "Far Mart", "ref": None, "lat": 1.32, "lng": 103.80, "place_id": None, "source": "OSM", "as_of": "2026-10-29"},
    {"id": "osm:node/3", "kind": "bus_stop", "name": "Blk 5", "ref": "12345", "lat": 1.3005, "lng": 103.80, "place_id": None, "source": "OSM", "as_of": "2026-10-29"},
    {"id": "exit:mrt_a:1", "kind": "mrt_exit", "name": "A", "ref": None, "lat": 1.31, "lng": 103.80, "place_id": "mrt_a", "source": "LTA", "as_of": "2026-10-29"},
    {"id": "exit:mrt_a:2", "kind": "mrt_exit", "name": "A", "ref": None, "lat": 1.302, "lng": 103.80, "place_id": "mrt_a", "source": "LTA", "as_of": "2026-10-29"},
])
PLACES = pd.DataFrame([{"place_id": "mrt_a", "kind": "mrt", "name": "A", "lat": 1.306, "lng": 103.80}])
LINE = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"  # (38.5,-120.2) (40.7,-120.95) (43.252,-126.453)
ROUTE = {"route_geometry": LINE, "route_summary": {"total_time": 142, "total_distance": 197},
         "route_instructions": [["Head East", "A Road", 100, "1.3,103.8", 60, "100 m", "East", 90, "walk", "Head East on A Road"],
                                ["Arrive", "", 0, "1.3,103.8", 0, "", "", 0, "walk", "Arrive at your destination"]]}


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(amenities, "load_amenities", lambda: AMENITIES)
    monkeypatch.setattr(amenities, "load_places", lambda: PLACES)
    monkeypatch.setattr(amenities.mapdata, "resolve", lambda s: START if s.get("id") == "b1" else None)
    amenities.cache.clear(); amenities.caps.cache_clear()
    yield
    amenities.cache.clear(); amenities.caps.cache_clear()


def one_map(handler, credentials=CREDS):
    return OneMap(httpx.Client(transport=httpx.MockTransport(handler)), credentials, sleep=lambda s: None)


def serve(monkeypatch, handler, credentials=CREDS):
    monkeypatch.setattr(amenities, "onemap", lambda: one_map(handler, credentials))
    return TestClient(create_app())


def ok_handler(calls=None):
    def handler(request):
        if calls is not None:
            calls.append(request.url.path)
        if request.url.path.endswith("getToken"):
            return httpx.Response(200, json={"access_token": "SECRET-TOKEN", "expiry_timestamp": "9999999999"})
        return httpx.Response(200, json=ROUTE)
    return handler


def test_polyline_and_parse():
    points = decode_polyline(LINE)
    assert points[0] == [-120.2, 38.5] and len(points) == 3
    out = parse_route(ROUTE)
    assert out["distance_m"] == 197 and out["duration_s"] == 142
    assert [s["text"] for s in out["steps"]] == ["Head East on A Road", "Arrive at your destination"]
    with pytest.raises(RouteError):
        parse_route({"route_summary": {}})


def test_nearby_ranks_by_distance_and_bounds_n():
    client = TestClient(create_app())
    body = client.get("/nearby/block/b1", params={"type": "supermarket", "n": 99}).json()
    assert [i["id"] for i in body["items"]] == ["osm:node/1", "osm:node/2"]
    assert body["items"][0]["km"] < body["items"][1]["km"] and "OpenStreetMap" in body["limits"][0]
    assert client.get("/nearby/block/b1", params={"type": "bus", "n": 0}).json()["items"][0]["ref"] == "12345"
    assert client.get("/nearby/block/b1", params={"type": "mrt"}).json()["items"][0]["id"] == "mrt_a"
    assert client.get("/nearby/block/nope", params={"type": "bus"}).status_code == 404
    assert client.get("/nearby/block/b1", params={"type": "pizza"}).status_code == 422


def test_route_success_uses_the_nearest_exit_and_never_leaks_the_token(monkeypatch):
    calls, seen = [], []
    def handler(request):
        seen.append(request.url.params.get("end"))
        return ok_handler(calls)(request)
    client = serve(monkeypatch, handler)
    response = client.get("/route/block/b1", params={"to": "mrt_a"})
    body = response.json()
    assert response.status_code == 200 and body["to"].endswith("(nearest exit)") and len(body["line"]) == 3
    assert "1.302,103.8" in seen  # the exit nearer to the start, not the far one
    assert "SECRET-TOKEN" not in response.text
    client.get("/route/block/b1", params={"to": "mrt_a"})
    assert calls.count("/api/public/routingsvc/route") == 1, "the second request is served from the cache"


def test_client_cannot_route_to_coordinates_or_unknown_ids(monkeypatch):
    client = serve(monkeypatch, ok_handler())
    assert client.get("/route/block/b1", params={"to": "1.3,103.8"}).status_code == 404
    assert client.get("/route/block/zzz", params={"to": "osm:node/1"}).status_code == 404


def test_errors_map_to_plain_messages_and_are_not_cached(monkeypatch):
    for status, code, http in [(404, "no_route", 404), (429, "quota", 429), (500, "unavailable", 502)]:
        amenities.cache.clear()
        def handler(request, status=status):
            if request.url.path.endswith("getToken"):
                return httpx.Response(200, json={"access_token": "t", "expiry_timestamp": "9999999999"})
            return httpx.Response(status, text="internal OneMap text")
        response = serve(monkeypatch, handler).get("/route/block/b1", params={"to": "osm:node/1"})
        assert response.status_code == http and response.json()["error"] == code
        assert "internal OneMap text" not in response.text
        # Only a missing route is remembered; quota and outages must be retried.
        assert amenities.cache.get(("block", "b1", "osm:node/1")) == ("no_route" if code == "no_route" else None)


def test_missing_credentials_and_timeout(monkeypatch):
    response = serve(monkeypatch, ok_handler(), credentials=None).get("/route/block/b1", params={"to": "osm:node/1"})
    assert response.json()["error"] == "no_credentials" and "credentials" in response.json()["message"]
    def slow(request):
        raise httpx.ConnectTimeout("slow")
    assert serve(monkeypatch, slow).get("/route/block/b1", params={"to": "osm:node/1"}).json()["error"] == "unavailable"
    def bad_json(request):
        if request.url.path.endswith("getToken"):
            return httpx.Response(200, json={"access_token": "t"})
        return httpx.Response(200, text="not json")
    assert serve(monkeypatch, bad_json).get("/route/block/b1", params={"to": "osm:node/1"}).json()["error"] == "unavailable"


def test_a_401_refreshes_the_token_once(monkeypatch):
    tokens = []
    def handler(request):
        if request.url.path.endswith("getToken"):
            tokens.append(1)
            return httpx.Response(200, json={"access_token": f"t{len(tokens)}", "expiry_timestamp": "9999999999"})
        if request.headers["authorization"] == "t1":
            return httpx.Response(401)
        return httpx.Response(200, json=ROUTE)
    assert serve(monkeypatch, handler).get("/route/block/b1", params={"to": "osm:node/1"}).status_code == 200
    assert len(tokens) == 2


def test_rate_limit_protects_the_shared_account(monkeypatch):
    client = serve(monkeypatch, ok_handler())
    amenities.caps().visitor.per_minute = 1
    codes = [client.get("/route/block/b1", params={"to": f"osm:node/{i}"}).status_code for i in (1, 2)]
    assert codes == [200, 429]  # two different routes, one allowed per minute


def test_chat_rate_limit_setting_is_unchanged(monkeypatch):
    from ask_hdb.api import Limits
    monkeypatch.setenv("API_RATE_PER_MINUTE", "7")
    assert Limits().per_minute == 7 and Limits(per_minute=3).per_minute == 3


def overpass(elements, remark=None):
    return {"elements": elements, **({"remark": remark} if remark else {})}


def test_build_parses_dedupes_and_checks_the_answer():
    node = {"type": "node", "id": 1, "lat": 1.3, "lon": 103.8, "tags": {"name": "Blk 5", "ref": "12345"}}
    twin = {"type": "node", "id": 2, "lat": 1.30005, "lon": 103.80005, "tags": {"name": "Blk 5"}}
    shop = {"type": "way", "id": 9, "center": {"lat": 1.4, "lon": 103.9}, "tags": {"name": "Mart"}}
    nothing = {"type": "way", "id": 10, "tags": {}}
    stops = build_amenities.merge_close(build_amenities.parse(overpass([node, twin, node, nothing]), "bus_stop"))
    assert len(stops) == 1 and stops[0]["ref"] == "12345"
    assert build_amenities.parse(overpass([shop]), "supermarket")[0]["id"] == "osm:way/9"
    with pytest.raises(ValueError, match="remark"):
        build_amenities.parse(overpass([node], remark="runtime error: timeout"), "bus_stop")
    exits = {"features": [{"properties": {"STATION_NA": "A MRT STATION"}, "geometry": {"coordinates": [103.8, 1.3]}}]}
    frame = build_amenities.build({"supermarket": overpass([shop]), "bus_stop": overpass([node])}, exits, "2026-10-29",
                                  floors={"supermarket": 1, "bus_stop": 1})
    assert set(frame.kind) == {"supermarket", "bus_stop", "mrt_exit"}
    with pytest.raises(ValueError, match="expected at least"):
        build_amenities.build({"supermarket": overpass([shop]), "bus_stop": overpass([node])}, exits, "2026-10-29")


def test_limits_allow_survives_concurrent_threads():
    from concurrent.futures import ThreadPoolExecutor

    from ask_hdb.api import Limits
    limits = Limits(per_minute=5)
    with ThreadPoolExecutor(20) as pool:
        answers = list(pool.map(lambda i: limits.allow("same", now=100.0), range(40)))
    assert answers.count(True) == 5
    with ThreadPoolExecutor(20) as pool:  # an idle visitor is forgotten while others arrive
        list(pool.map(lambda i: limits.allow(f"v{i}", now=500.0), range(40)))
