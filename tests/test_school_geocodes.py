"""School lookup tests use fake APIs and temporary local caches."""

import json

import pandas as pd
import pytest

from ask_hdb.geo.client import GeocodeError, StopGeocoding
from ask_hdb.geo.schools import geocode_schools, match_school


def school_rows():
    return pd.DataFrame({"place_id": ["school_a", "school_b", "mrt_c"],
                         "kind": ["primary_school", "primary_school", "mrt"],
                         "postal_code": ["012345", "012345", None],
                         "lat": [float("nan"), float("nan"), 2.],
                         "lng": [float("nan"), float("nan"), 104.]})


def body():
    return {"results": [{"POSTAL": "999999", "LATITUDE": "9", "LONGITUDE": "99"},
                        {"POSTAL": "012345", "LATITUDE": "1", "LONGITUDE": "103"}]}


def test_matches_postal_and_rejects_invalid_coordinates():
    assert match_school("012345", body())["lng"] == 103
    assert match_school("000000", body())["status"] == "not_found"
    with pytest.raises(ValueError):
        match_school("012345", {"results": [{"POSTAL": "012345", "LATITUDE": "nan",
                                             "LONGITUDE": "103"}]})


def test_resume_and_shared_postal(tmp_path):
    calls = []

    class API:
        def search(self, query):
            calls.append(query)
            return body()

    places = school_rows()
    assert geocode_schools(places, API(), tmp_path, checkpoint=1)
    assert geocode_schools(places, API(), tmp_path)
    assert calls == ["012345"]
    saved = pd.read_parquet(tmp_path / "places.parquet")
    assert saved.lat.tolist() == [1., 1., 2.]
    assert saved.lng.tolist() == [103., 103., 104.]
    assert json.loads((tmp_path / "school_geocode_cache.json").read_text())["012345"]


@pytest.mark.parametrize("error", [StopGeocoding("HTTP 403"), StopGeocoding("HTTP 401"),
                                  KeyboardInterrupt()])
def test_stop_saves_progress(tmp_path, error):
    class API:
        def search(self, query):
            raise error

    assert not geocode_schools(school_rows(), API(), tmp_path, notify=lambda _: None)
    assert (tmp_path / "places.parquet").exists()
    assert (tmp_path / "school_geocode_cache.json").exists()


def test_transient_error_can_retry(tmp_path):
    class API:
        def search(self, query):
            raise GeocodeError()

    geocode_schools(school_rows(), API(), tmp_path)
    cache = json.loads((tmp_path / "school_geocode_cache.json").read_text())
    assert cache["012345"]["status"] == "error"
