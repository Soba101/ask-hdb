"""All HTTP is replaced with local, queued responses."""

import httpx
import pytest

from ask_hdb.geo.client import GeocodeError, OneMap, StopGeocoding, load_credentials
from ask_hdb.geo.matching import match_result
from ask_hdb.geo.streets import normalize_street


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        status, body = response
        return httpx.Response(status, json=body)


def result(block="001a", road="BEDOK NORTH STREET 1"):
    return {"BLK_NO": block, "ROAD_NAME": road, "LATITUDE": "1.32", "LONGITUDE": "103.9",
                "POSTAL": "001234", "SECRET": "discard"}


@pytest.mark.parametrize(("raw", "expected"), [
    (" bedok nth st. 1 ", "BEDOK NORTH STREET 1"),
    ("TAMPINES AVE 2", "TAMPINES AVENUE 2"),
    ("BLK 3 CTRL", "BLOCK 3 CENTRAL"),
    ("BT BATOK WEST AVE 1", "BUKIT BATOK WEST AVENUE 1"),
    ("UPP SERANGOON CRES", "UPPER SERANGOON CRESCENT"),
    ("STAMFORD RD", "STAMFORD ROAD"),
    ("JLN KG TER PK GDNS DR CL PL STH", "JALAN KAMPONG TERRACE PARK GARDENS DRIVE CLOSE PLACE SOUTH"),
])
def test_streets(raw, expected):
    assert normalize_street(raw) == expected


@pytest.mark.parametrize(("rows", "status"), [
    ([result()], "found"),
    ([result(road="OTHER ROAD")], "uncertain"),
    ([result(block="002")], "not_found"),
    ([result(road="OTHER"), result(road="ANOTHER")], "not_found"),
    ([result(), result()], "found"),
    ([], "not_found"),
    ([result(), result(road="OTHER")], "found"),
])
def test_matching(rows, status):
    record = match_result("001A", "BEDOK NTH ST 1", {"results": rows})
    assert record["status"] == status
    assert set(record) == {"status", "lat", "lng", "postal", "road_name", "query"}
    if status == "found":
        assert record["postal"] == "001234"
        assert record["lat"] == 1.32


def test_retry_and_headers():
    fake = FakeClient([(200, {"access_token": "secret"}), (429, {}), (503, {}),
                       (200, {"results": [result()], "error": "missing token"})])
    sleeps = []
    api = OneMap(fake, {"email": "private", "password": "private"}, sleep=sleeps.append)
    assert api.search("001A BEDOK NTH ST 1")["results"]
    for method, _, kwargs in fake.calls:
        assert kwargs["timeout"] == 15
        assert kwargs["headers"]["User-Agent"] == "ask-hdb/0.1"
        if method == "GET":
            assert kwargs["headers"]["Authorization"] == "secret"
            assert kwargs["params"] == {"searchVal": "001A BEDOK NTH ST 1", "returnGeom": "Y",
                                             "getAddrDetails": "Y", "pageNum": 1}
    assert sleeps == [0.5, 0.5, 1, 0.5, 2, 0.5]


@pytest.mark.parametrize("response", [(503, {}), (429, {}), httpx.ConnectError("offline")])
def test_retry_exhaustion(response):
    fake = FakeClient([response] * 5)
    with pytest.raises(GeocodeError):
        OneMap(fake, sleep=lambda _: None).search("query")
    assert len(fake.calls) == 5
    assert all("Authorization" not in call[2]["headers"] for call in fake.calls)


@pytest.mark.parametrize("status", [401, 403])
def test_unauthenticated_stop(status):
    fake = FakeClient([(status, {})])
    with pytest.raises(StopGeocoding, match=str(status)):
        OneMap(fake, sleep=lambda _: None).search("query")
    assert len(fake.calls) == 1


def test_refresh_once():
    fake = FakeClient([(200, {"access_token": "old"}), (401, {}),
                       (200, {"access_token": "new"}), (200, {"results": []})])
    api = OneMap(fake, {"email": "x", "password": "y"}, sleep=lambda _: None)
    assert api.search("query") == {"results": []}
    assert fake.calls[-1][2]["headers"]["Authorization"] == "new"


def test_failed_refresh_stops():
    fake = FakeClient([(200, {"access_token": "old"}), (401, {}), (401, {})])
    with pytest.raises(StopGeocoding):
        OneMap(fake, {"email": "x", "password": "y"}, sleep=lambda _: None).search("query")


def test_credentials(monkeypatch):
    monkeypatch.setattr("ask_hdb.geo.client.load_dotenv", lambda: None)
    monkeypatch.setenv("ONEMAP_EMAIL", "")
    monkeypatch.setenv("ONEMAP_PASSWORD", "")
    assert load_credentials() is None
    monkeypatch.setenv("ONEMAP_EMAIL", "email")
    assert load_credentials() is None
    monkeypatch.setenv("ONEMAP_PASSWORD", "password")
    assert load_credentials() == {"email": "email", "password": "password"}


@pytest.mark.parametrize("body", [{"error": "missing token", "results": []},
                                  {"results": "bad"}, {"results": [None]}, []])
def test_bad_body(body):
    with pytest.raises(GeocodeError):
        OneMap(FakeClient([(200, body)]), sleep=lambda _: None).search("query")


def test_rejected_new_token_stops():
    fake = FakeClient([(200, {"access_token": "old"}), (401, {}),
                       (200, {"access_token": "new"}), (401, {})])
    with pytest.raises(StopGeocoding):
        OneMap(fake, {"email": "x", "password": "y"}, sleep=lambda _: None).search("query")
    assert len(fake.calls) == 4


@pytest.mark.parametrize("latitude", ["nan", "inf", "91", "bad"])
def test_invalid_coordinates(latitude):
    row = result()
    row["LATITUDE"] = latitude
    with pytest.raises(ValueError):
        match_result("001A", "BEDOK NTH ST 1", {"results": [row]})
