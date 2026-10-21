"""Exercise persistence and CLI selection without network access."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from test_geocode_client import FakeClient, result

from ask_hdb.geo.client import OneMap
from ask_hdb.geo.matching import empty_record
from ask_hdb.geo.runner import geocode
from ask_hdb.geo.storage import load_cache, save_cache, select_blocks


def blocks(count=1):
    return pd.DataFrame([{"block_id": f"blk_{i}", "block": "001A", "street_name": "BEDOK NTH ST 1",
                              "town": "BEDOK"} for i in range(count)])


def api(responses):
    fake = FakeClient(responses)
    return OneMap(fake, sleep=lambda _: None), fake


def test_resume_and_outputs(tmp_path):
    records = {f"blk_{i}": empty_record(status, "old query") for i, status in
               enumerate(["found", "uncertain", "not_found", "error"])}
    records["blk_0"].update(lat=1.3, lng=103.9)
    save_cache(tmp_path / "geocode_cache.json", records)
    client, fake = api([(200, {"results": [result()]})])
    assert geocode(blocks(4), client, tmp_path)
    assert len(fake.calls) == 1
    assert geocode(blocks(4), client, tmp_path)
    assert len(fake.calls) == 1
    output = pd.read_parquet(tmp_path / "blocks.parquet")
    assert list(output.block_id) == ["blk_0", "blk_3"]
    report = (tmp_path / "geocode_report.txt").read_text()
    assert "found: 2" in report and "uncertain: blk_1" in report
    assert "not_found: blk_2" in report
    assert "SECRET" not in (tmp_path / "geocode_cache.json").read_text()


def test_ten_errors_stop(tmp_path):
    client, fake = api([(503, {})] * 50)
    messages = []
    assert not geocode(blocks(12), client, tmp_path, notify=messages.append)
    assert len(fake.calls) == 50
    assert len(load_cache(tmp_path / "geocode_cache.json")) == 10
    assert "10 consecutive" in messages[0]
    assert pd.read_parquet(tmp_path / "blocks.parquet").empty


def test_errors_reset(tmp_path):
    responses = [(400, {})] * 9 + [(200, {"results": []})] + [(400, {})] * 9
    client, fake = api(responses)
    assert geocode(blocks(19), client, tmp_path)
    assert len(fake.calls) == 19


@pytest.mark.parametrize("status", [401, 403])
def test_auth_stops_whole_run(tmp_path, status):
    client, fake = api([(status, {})])
    messages = []
    assert not geocode(blocks(3), client, tmp_path, notify=messages.append)
    assert len(fake.calls) == 1
    assert str(status) in messages[0]
    assert load_cache(tmp_path / "geocode_cache.json")["blk_0"]["status"] == "error"


def test_interrupt_and_checkpoint(tmp_path, monkeypatch):
    client, _ = api([(200, {"results": []})] * 25 + [KeyboardInterrupt()])
    # Interrupts are not HTTP responses.
    original = client.search
    calls = 0

    def search(query):
        nonlocal calls
        calls += 1
        if calls == 26:
            raise KeyboardInterrupt
        return original(query)

    client.search = search
    from ask_hdb.geo import runner
    save = Mock(wraps=save_cache)
    monkeypatch.setattr(runner, "save_cache", save)
    assert not geocode(blocks(30), client, tmp_path, notify=lambda _: None)
    assert save.call_count == 2
    assert len(load_cache(tmp_path / "geocode_cache.json")) == 25


def test_atomic_write(tmp_path, monkeypatch):
    path = tmp_path / "geocode_cache.json"
    old = {"old": empty_record("not_found", "old")}
    new = {"new": empty_record("not_found", "new")}
    save_cache(path, old)

    def failed_replace(source, target):
        assert json.loads(path.read_text()) == old
        assert json.loads(Path(source).read_text()) == new
        raise OSError("disk failure")

    monkeypatch.setattr("ask_hdb.geo.storage.os.replace", failed_replace)
    with pytest.raises(OSError):
        save_cache(path, new)
    assert load_cache(path) == old
    assert list(tmp_path.iterdir()) == [path]


def test_month_window_and_limit():
    sales = blocks(4)
    sales["sale_month"] = pd.to_datetime(["2026-10-01", "2023-10-01", "2023-11-01", "2020-01-01"])
    sales = pd.concat([sales, sales.iloc[[0]]])
    assert list(select_blocks(sales).block_id) == ["blk_0", "blk_2"]
    assert len(select_blocks(sales, all_blocks=True)) == 4
    assert list(select_blocks(sales, limit=1).block_id) == ["blk_0"]
    assert select_blocks(sales, limit=0).empty


def test_cli_limit(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("geocode_script", "scripts/geocode_blocks.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    directory = tmp_path / "data/clean"
    directory.mkdir(parents=True)
    sales = blocks(3)
    sales["sale_month"] = pd.Timestamp("2026-10-01")
    sales.to_parquet(directory / "resale.parquet")
    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "load_credentials", lambda: None)
    fake = FakeClient([(200, {"results": []})])
    monkeypatch.setattr(script, "OneMap", lambda *_: OneMap(fake, sleep=lambda _: None))
    assert script.main(["--all", "--limit", "1"]) == 0
    assert len(fake.calls) == 1
    with pytest.raises(SystemExit):
        script.parse_args(["--limit", "-1"])


def test_duplicate_listing_of_one_block_is_found_but_far_apart_is_uncertain():
    from ask_hdb.geo.matching import match_result
    row = {"BLK_NO": "100", "ROAD_NAME": "BEDOK NORTH AVENUE 4", "LATITUDE": "1.33", "LONGITUDE": "103.93"}
    near = dict(row, LATITUDE="1.3301")
    far = dict(row, LATITUDE="1.40")
    assert match_result("100", "BEDOK NTH AVE 4", {"results": [row, near]})["status"] == "found"
    assert match_result("100", "BEDOK NTH AVE 4", {"results": [row, far]})["status"] == "not_found"


def test_commonwealth_abbreviation():
    from ask_hdb.geo.streets import normalize_street
    assert normalize_street("C'WEALTH CRES") == "COMMONWEALTH CRESCENT"


def test_outline_postals_break_a_same_road_tie():
    from ask_hdb.geo.matching import match_with_outlines
    far = {"BLK_NO": "102", "ROAD_NAME": "TOWNER ROAD", "POSTAL": "327826", "LATITUDE": "1.32", "LONGITUDE": "103.86"}
    hdb = {"BLK_NO": "102", "ROAD_NAME": "TOWNER ROAD", "POSTAL": "322102", "LATITUDE": "1.33", "LONGITUDE": "103.85"}
    body = {"results": [far, hdb]}
    assert match_with_outlines("102", "TOWNER RD", body, {("102", "322102")})["postal"] == "322102"
    # No outline match, or two outline matches: stay not found rather than guess.
    assert match_with_outlines("102", "TOWNER RD", body, set())["status"] == "not_found"
    assert match_with_outlines("102", "TOWNER RD", body, {("102", "322102"), ("102", "327826")})["status"] == "not_found"
