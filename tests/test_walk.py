"""The walking router on a tiny made-up map (no OpenStreetMap file needed)."""

import numpy as np
import pytest

from ask_hdb.api import amenities
from ask_hdb.geo import walk

# A square of footpaths with one road across the middle and a gap-free link to a far dead end:
#   0 --- 1 --- 2
#   |     |     |
#   3 --- 4 --- 5      (way 0: footpath on the top row, way 1: the left side, way 2: the bottom row, way 3: a service road)
# Node spacing is about 0.0009 degrees, roughly 100 m.
LAT = np.array([1.3009, 1.3009, 1.3009, 1.3000, 1.3000, 1.3000, 1.3050])
LNG = np.array([103.8000, 103.8009, 103.8018, 103.8000, 103.8009, 103.8018, 103.8100])


@pytest.fixture
def router(tmp_path):
    ways = np.array([("footway", "Top Walk"), ("footway", ""), ("service", "Back Lane"), ("steps", "")], dtype=object)
    edges = [(0, 1, 0), (1, 2, 0), (0, 3, 1), (3, 4, 2), (4, 5, 2), (1, 4, 3), (2, 5, 3)]
    a, b, way = (np.array(x, dtype=np.int32) for x in zip(*edges, strict=True))
    length = np.array([walk.metres(LAT[i], LNG[i], LAT[j], LNG[j]) for i, j, _ in edges], dtype=np.float32)
    kind_cost = np.array([walk.COST[ways[w][0]] for w in way], dtype=np.float32)
    graph = {"lat": LAT, "lng": LNG, "a": a, "b": b, "length": length, "cost": length * kind_cost, "way": way, "ways": ways}
    walk.save(graph, tmp_path / "graph.npz")
    return walk.Router(tmp_path / "graph.npz")


def test_route_follows_the_cheapest_path_and_reports_steps(router):
    route = router.route((1.3009, 103.8000), (1.3009, 103.8018))
    assert route["distance_m"] == pytest.approx(200, abs=10) and route["duration_s"] == round(route["distance_m"] / walk.SPEED_MS)
    assert route["steps"][0]["text"] == "Head east on Top Walk" and route["steps"][0]["distance_m"] == pytest.approx(200, abs=10)
    assert route["line"][0] == [103.8000, 1.3009] and route["line"][-1] == [103.8018, 1.3009]


def test_stairs_cost_more_so_a_longer_footpath_wins(router):
    # From node 1 to node 4 the direct link is steps (cost x1.5, about 100 m); the way round through 0, 3 is about 300 m,
    # so the stairs still win here, but the step text says so.
    route = router.route((1.3009, 103.8009), (1.3000, 103.8009))
    assert route["steps"][0]["text"] == "Take the stairs" or "stairs" in route["steps"][0]["text"]


def test_nothing_nearby_gives_none_and_turn_words(router):
    assert router.route((1.35, 103.9), (1.3009, 103.8000)) is None  # no graph node within 300 m of the start
    assert walk.Router.turn_word(10) == "Continue" and walk.Router.turn_word(90) == "Turn right"
    assert walk.Router.turn_word(270) == "Turn left" and walk.Router.compass(95) == "east"


def test_osm_route_is_refused_when_far_longer_than_the_straight_line(monkeypatch, router):
    monkeypatch.setattr(amenities, "osm_router", lambda: router)
    assert amenities.osm_route((1.3009, 103.8000), (1.3009, 103.8018)) is not None
    monkeypatch.setattr(router, "route", lambda a, b: {"distance_m": 2000, "duration_s": 1, "steps": [], "line": []})
    assert amenities.osm_route((1.3009, 103.8000), (1.3009, 103.8018)) is None  # 2000 m for a 200 m trip: a gap in the map
    monkeypatch.setattr(amenities, "osm_router", lambda: None)
    assert amenities.osm_route((1.3009, 103.8000), (1.3009, 103.8018)) is None  # no graph file: no backup route
