"""Build a static copy of the app in site/ (for GitHub Pages): the page, the map data and one file per place.

Run after the data scripts and scripts/build_walk_graph.py:  uv run python scripts/build_static_demo.py
Chat and per-block sun hours are off in the demo; walking routes come from our own OpenStreetMap router (estimates).
"""

import json
import shutil
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from ask_hdb import sun
from ask_hdb.api import amenities, buildings, mapdata

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/ask_hdb/api/static"
SITE = ROOT / "site"
TYPES = ("supermarket", "mrt", "bus")
RADII = (0.5, 1.0, 2.0)


def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, separators=(",", ":"), ensure_ascii=False, default=str))


def round_line(route):
    return {**route, "line": [[round(x, 5), round(y, 5)] for x, y in route["line"]]}


def place_bundle(selection):
    """Everything the page asks about one place, so the demo needs one file per click."""
    bundle = {"card": mapdata.card(selection), "schools": mapdata.schools_nearby(selection),
              "around": {str(km): mapdata.around(selection, km) for km in RADII}, "nearby": {}, "routes": {}}
    for kind in TYPES:
        listing = amenities.nearby(selection["kind"], selection["id"], kind, 3)
        bundle["nearby"][kind] = listing
        for item in listing["items"]:
            goal = amenities._destination(selection, item["id"])
            route = amenities.osm_route((selection["lat"], selection["lng"]), goal[:2]) if goal else None
            if route:
                bundle["routes"][item["id"]] = round_line({**route, "to": goal[2],
                    "source": "Route: OpenStreetMap paths, walking estimate",
                    "limits": ["Estimated from OpenStreetMap paths; it can miss void decks and covered links, so a real walk may be shorter."]})
    return bundle


def copy_page():
    """The page, scripts and styles (not the data), with the demo shim loaded first."""
    shutil.copytree(STATIC, SITE, dirs_exist_ok=True)
    shutil.copy(ROOT / "scripts/demo/demo.js", SITE / "demo.js")
    page = (STATIC / "index.html").read_text()
    (SITE / "index.html").write_text(page.replace('<script type="module" src="app.js">', '<script src="demo.js"></script>\n<script type="module" src="app.js">'))
    (SITE / ".nojekyll").write_text("")  # serve every file as it is


def main(limit=None):
    if limit == "assets":  # refresh the page files only, keeping the data already built
        return copy_page()
    if amenities.osm_router() is None:
        sys.exit("data/clean/walk_graph.npz is missing: run scripts/build_walk_graph.py first")
    if SITE.exists():
        shutil.rmtree(SITE)
    copy_page()
    data = SITE / "data"
    features = mapdata.features()
    write(data / "features.json", features)
    shutil.copy(buildings.PATH, data / "buildings.json")
    for flat in mapdata.METRIC_FLAT_TYPES:
        write(data / "metrics" / f"{flat}.json", mapdata.metrics(flat))
    day = date(2026, 1, 1)
    while day.year == 2026:
        write(data / "sun" / f"{day:%m-%d}.json", {"timezone": "+08:00", "positions": sun.positions(day), "limits": sun.LIMITS})
        day += timedelta(days=1)
    write(data / "sun" / "02-29.json", json.loads((data / "sun" / "02-28.json").read_text()))
    places = [f["properties"] for f in features["features"]]
    places = places[:limit] if limit else places
    start = time.time()
    for number, properties in enumerate(places, 1):
        selection = mapdata.resolve({"kind": properties["kind"], "id": properties["id"]})
        if selection is None:
            continue
        write(data / "place" / f"{selection['kind']}__{selection['id']}.json", place_bundle(selection))
        if number % 500 == 0:
            print(number, "of", len(places), "places,", round(time.time() - start), "s", flush=True)
    size = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file()) // 1_000_000
    print("site/ built:", len(places), "places,", size, "MB")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg if arg == "assets" else int(arg) if arg else None)
