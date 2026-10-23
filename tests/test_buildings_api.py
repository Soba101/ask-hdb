"""Building routes remain useful offline, with missing files and sparse historical sales."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from ask_hdb import api
from ask_hdb.api import buildings, mapdata


@pytest.fixture
def client(monkeypatch, tmp_path):
    path = tmp_path / "buildings.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Polygon", "coordinates": []},
        "properties": {"block_id": "blk_a", "floors": 12, "height_source": "property_info",
                       "facing": [90, 270], "facing_label": "E and W", "pad": "x" * 2000}}]}))
    monkeypatch.setattr(buildings, "PATH", path)
    blocks = pd.DataFrame([{"block_id": "blk_a", "block": "1", "street_name": "A ST",
                            "town": "BEDOK", "lat": 1.3, "lng": 103.8}])
    monkeypatch.setattr(mapdata, "load_blocks", lambda: blocks)
    for cached in (buildings.features, buildings.raw, buildings.zipped, buildings.index):
        cached.cache_clear()
    yield TestClient(api.create_app())
    for cached in (buildings.features, buildings.raw, buildings.zipped, buildings.index):
        cached.cache_clear()


def test_buildings_are_gzipped_cached_and_missing_file_is_clear(client):
    response = client.get("/map/buildings", headers={"accept-encoding": "gzip"})
    assert response.status_code == 200 and response.headers["content-encoding"] == "gzip"
    assert response.headers["cache-control"] == "public, max-age=3600"
    buildings.PATH.unlink()
    assert client.get("/map/buildings").status_code == 200  # process cache
    for cached in (buildings.raw, buildings.zipped):
        cached.cache_clear()
    response = client.get("/map/buildings")
    assert response.status_code == 404 and "build_buildings.py" in response.json()["detail"]
    assert buildings.metadata("blk_a") == {}


@pytest.mark.parametrize("query", ["2026-02-30", "2026-13-01", "20260320", "today", ""])
def test_both_sun_routes_reject_invalid_dates(client, query):
    assert client.get("/sun", params={"date": query}).status_code == 422
    assert client.get("/sun/block/blk_a", params={"date": query}).status_code == 422


def test_sun_routes_validate_the_block_and_default_to_singapore_today(client):
    data = client.get("/sun").json()
    assert data["date"] == datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()
    assert len(data["positions"]) == 96 and data["timezone"] == "+08:00"
    data = client.get("/sun/block/blk_a?date=2024-02-29").json()
    assert data["date"] == "2024-02-29" and len(data["facades"]) == 2
    assert data["facades"][0]["bearing"] == 90 and "not measured heat" in data["limits"]
    assert client.get("/sun/block/not-a-block").status_code == 404
    buildings.PATH.unlink()
    for cached in (buildings.features, buildings.raw, buildings.zipped, buildings.index):
        cached.cache_clear()
    assert client.get("/sun/block/blk_a").status_code == 404


def test_card_storey_prices_threshold_window_and_height(client, monkeypatch):
    sales = pd.DataFrame([
        *[{"block_id": "blk_a", "sale_month": pd.Timestamp(month), "storey_low": low,
           "storey_high": high, "resale_price": price, "flat_type": "4 ROOM", "lease_commence_year": 1990}
          for month, low, high, price in [
              *[("2026-09-01", 1, 3, 400000 + i * 1000) for i in range(4)],
              ("2024-11-01", 1, 3, 100000),  # fifth sale, inside the data's last 24 months
              ("2024-10-01", 1, 3, 900000),  # excluded, even though this block last sold in September
              *[("2026-09-01", 4, 6, 600000) for _ in range(4)],
              *[("2026-09-01", 1, 5, 900000) for _ in range(5)]]],
        {"block_id": "other", "sale_month": pd.Timestamp("2026-10-01"), "storey_low": 4,
         "storey_high": 6, "resale_price": 999999}])
    monkeypatch.setattr(mapdata, "load_sales", lambda: sales)
    monkeypatch.setattr(mapdata, "_nearest", lambda *args: None)
    data = client.get("/card/block/blk_a").json()
    assert data["floors"] == 12 and data["height_source"] == "property_info" and data["facing_label"] == "E and W"
    assert data["storey_prices"] == [{"storey_low": 1, "storey_high": 3, "label": "1–3",
                                      "sales": 5, "median_price": 401000}]
    assert data["storey_prices_as_of"] == "2026-10"
    assert "All flat types pooled" in data["storey_prices_limits"]
    buildings.PATH.unlink()
    for cached in (buildings.features, buildings.raw, buildings.zipped, buildings.index):
        cached.cache_clear()
    data = client.get("/card/block/blk_a").json()
    assert data["floors"] is None and data["storey_prices"]
