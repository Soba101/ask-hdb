"""Distance tools filter before aggregation and keep JSON-safe output."""

import json

import pandas as pd
import pytest

from ask_hdb import tools
from ask_hdb.geo import filters, loaders
from ask_hdb.tool_inputs import NearestArgs


@pytest.fixture
def local_geo(monkeypatch, sales):
    block_id = sales.iloc[0].block_id
    monkeypatch.setattr(tools, "load_sales", lambda: sales)
    monkeypatch.setattr(filters, "load_blocks", lambda: pd.DataFrame({
        "block_id": [block_id], "lat": [1.], "lng": [103.]}))
    monkeypatch.setattr(filters, "load_places", lambda: pd.DataFrame({
        "place_id": ["mrt_a"], "name": ["A"], "kind": ["mrt"], "lat": [1.], "lng": [103.]}))
    return block_id


@pytest.mark.parametrize("name", ["find_sales", "price_stats"])
def test_filter_wiring(local_geo, name):
    tool = getattr(tools, name)
    actual = tool.invoke({"near_kind": "mrt", "near_km": 0})
    expected = tool.invoke({"block_id": local_geo})
    assert actual == expected | {"distance_method": "straight-line"}
    json.dumps(actual, allow_nan=False)


@pytest.mark.parametrize("name", ["find_sales", "price_stats"])
@pytest.mark.parametrize("args,missing", [({"near_kind": "mrt"}, "near_km"),
                                         ({"near_km": 1}, "near_kind")])
def test_paired_args(local_geo, monkeypatch, name, args, missing):
    monkeypatch.setattr(tools, "load_sales", lambda: pytest.fail("loaded sales"))
    assert missing in getattr(tools, name).invoke(args)["error"]


@pytest.mark.parametrize("missing", ["blocks", "places"])
def test_missing_files(local_geo, monkeypatch, tmp_path, missing):
    monkeypatch.setattr(loaders, "ROOT", tmp_path)
    # Ensure the missing-file path is used instead of the fixture loaders.
    monkeypatch.setattr(filters, f"load_{missing}", getattr(loaders, f"load_{missing}"))
    loaders.load_blocks.cache_clear()
    loaders.load_places.cache_clear()
    try:
        result = tools.find_sales.invoke({"near_kind": "mrt", "near_km": 1})
        assert f"{missing}.parquet" in result["error"]
        result = tools.nearest_places.invoke({"block_id": local_geo, "kind": "mrt"})
        assert f"{missing}.parquet" in result["error"]
    finally:
        loaders.load_blocks.cache_clear()
        loaders.load_places.cache_clear()


def test_nearest_registered_json_safe(local_geo, monkeypatch):
    assert tools.nearest_places in tools.TOOLS
    assert set(NearestArgs.model_json_schema()["required"]) == {"block_id", "kind"}
    # Nearest does not need the sales dataset.
    monkeypatch.setattr(tools, "load_sales", lambda: pytest.fail("loaded sales"))
    result = tools.nearest_places.invoke({"block_id": local_geo, "kind": "mrt"})
    assert result["places"][0]["km"] == 0
    assert result["places"][0]["method"] == "straight-line"
    assert result["note"] == filters.NOTE
    json.dumps(result, allow_nan=False)
    assert "block_id" in tools.nearest_places.invoke({"kind": "mrt"})["error"]
    assert "Unknown block_id" in tools.nearest_places.invoke({
        "block_id": "absent", "kind": "mrt"})["error"]


def test_lazy_geo_loaders(monkeypatch, tmp_path):
    directory = tmp_path / "data/clean"
    directory.mkdir(parents=True)
    for name in ("blocks", "places"):
        pd.DataFrame({"id": [name]}).to_parquet(directory / f"{name}.parquet")
    monkeypatch.setattr(loaders, "ROOT", tmp_path)
    calls = []
    reader = pd.read_parquet
    monkeypatch.setattr(loaders.pd, "read_parquet", lambda p: calls.append(p) or reader(p))
    try:
        for load in (loaders.load_blocks, loaders.load_places):
            load.cache_clear()
            assert load() is load()
        assert len(calls) == 2
    finally:
        loaders.load_blocks.cache_clear()
        loaders.load_places.cache_clear()
