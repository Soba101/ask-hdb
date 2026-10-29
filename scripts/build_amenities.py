"""Build data/clean/amenities.parquet: bus stops and supermarkets from OpenStreetMap (Overpass), MRT exits from the raw file.

Run once after scripts/build_places.py. OSM may be incomplete or stale; the app says so next to the lists.
The parse and dedupe steps are plain functions so tests run them on a small fixture with no network.
"""

import json
import math
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_places import stations

ROOT = Path(__file__).resolve().parents[1]
OVERPASS = "https://overpass-api.de/api/interpreter"
BBOX = "1.15,103.55,1.50,104.15"  # south, west, north, east: all of Singapore
USER_AGENT = "ask-hdb/0.1 (HDB resale map; one-off amenity build)"
QUERIES = {
    "supermarket": f'[out:json][timeout:120];nwr["shop"="supermarket"]({BBOX});out center;',
    # A stop is often tagged twice on one node (highway=bus_stop and public_transport=platform); both come back.
    "bus_stop": (f'[out:json][timeout:120];(nwr["highway"="bus_stop"]({BBOX});'
                 f'nwr["public_transport"="platform"]["bus"="yes"]({BBOX}););out center;'),
}
# A count under these means a partial answer, not a quiet part of Singapore.
FLOORS = {"supermarket": 300, "bus_stop": 4000}
COLUMNS = ["id", "kind", "name", "ref", "lat", "lng", "place_id", "source", "as_of"]
OSM_SOURCE = "OpenStreetMap contributors (ODbL), via Overpass"
EXIT_SOURCE = "LTA MRT Station Exit (data.gov.sg)"
FALLBACK_NAME = {"supermarket": "Supermarket", "bus_stop": "Bus stop"}


def fetch(query, post=httpx.post, sleep=time.sleep, tries=2):
    """One request with a timeout and one retry; any non-200 or bad JSON counts as a failed try."""
    for attempt in range(tries):
        try:
            response = post(OVERPASS, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=180)
            if response.status_code == 200:
                return response.json()
        except (httpx.RequestError, ValueError):
            pass
        if attempt < tries - 1:
            sleep(30)
    raise RuntimeError("Overpass request failed")


def parse(body, kind):
    """Rows from an Overpass answer. A remark means a timeout or partial data, so the build stops."""
    if not isinstance(body, dict) or not isinstance(body.get("elements"), list):
        raise TypeError(f"{kind}: unexpected Overpass response")
    if body.get("remark"):
        raise ValueError(f"{kind}: Overpass remark: {body['remark']}")
    rows = {}  # keyed by OSM id, so an element returned twice counts once
    for element in body["elements"]:
        point = element if "lat" in element else element.get("center", {})
        if "lat" not in point or "lon" not in point:
            continue  # a way or relation without a centre cannot be placed
        tags = element.get("tags", {})
        ref = next((tags[k].strip() for k in ("ref", "asset_ref") if re.fullmatch(r"\d{5}", tags.get(k, "").strip())), "")
        key = f"osm:{element['type']}/{element['id']}"
        rows[key] = {"id": key, "kind": kind, "name": tags.get("name", "").strip(), "ref": ref or None,
                     "lat": float(point["lat"]), "lng": float(point["lon"]), "place_id": None}
    return list(rows.values())


def metres(a, b):
    # Flat-earth distance is exact enough at 15 m.
    dy = (a["lat"] - b["lat"]) * 110574
    dx = (a["lng"] - b["lng"]) * 111320 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy)


def merge_close(rows, limit=15):
    """Merge stops within `limit` metres that share a name or a stop code (node and platform of one stop)."""
    kept, cells = [], {}
    for row in sorted(rows, key=lambda r: r["id"]):
        cx, cy = math.floor(row["lat"] / 0.0005), math.floor(row["lng"] / 0.0005)
        twin = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in cells.get((cx + dx, cy + dy), []):
                    same = ((row["name"] and row["name"].lower() == other["name"].lower())
                            or (row["ref"] and row["ref"] == other["ref"]))
                    if same and metres(row, other) <= limit:
                        twin = other
        if twin is None:
            kept.append(row)
            cells.setdefault((cx, cy), []).append(row)
        elif not twin["ref"]:
            twin["ref"] = row["ref"]
    return kept


def exit_rows(exits):
    out = []
    for station in stations(exits)[0]:
        for i, (lat, lng) in enumerate(sorted(station["coordinates"])):
            out.append({"id": f"exit:{station['place_id']}:{i + 1}", "kind": "mrt_exit", "name": station["name"],
                        "ref": None, "lat": lat, "lng": lng, "place_id": station["place_id"]})
    return out


def build(bodies, exits, today, floors=FLOORS):
    frames = []
    for kind, body in bodies.items():
        rows = parse(body, kind)
        if kind == "bus_stop":
            rows = merge_close(rows)
        if len(rows) < floors[kind]:
            raise ValueError(f"{kind}: only {len(rows)} found, expected at least {floors[kind]}; not writing")
        for row in rows:
            row["name"] = row["name"] or (f"Bus stop {row['ref']}" if row["ref"] else FALLBACK_NAME[kind])
            row["source"] = OSM_SOURCE
        frames.append(pd.DataFrame(rows))
    stops = pd.DataFrame(exit_rows(exits))
    if stops.empty:
        raise ValueError("No MRT exits found; run scripts/fetch_places.py first")
    stops["source"] = EXIT_SOURCE
    out = pd.concat([*frames, stops], ignore_index=True)
    out["as_of"] = today
    return out[COLUMNS].sort_values(["kind", "id"]).reset_index(drop=True)


def main():
    exits = json.loads((ROOT / "data/raw/places/mrt_exits.geojson").read_text())
    bodies = {}
    for kind, query in QUERIES.items():
        bodies[kind] = fetch(query)
        time.sleep(5)  # polite gap between the two requests
    frame = build(bodies, exits, date.today().isoformat())
    output = ROOT / "data/clean/amenities.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    frame.to_parquet(temp, index=False)
    temp.replace(output)  # a failed run never leaves a half-written file
    for kind, count in frame.kind.value_counts().items():
        print(f"{kind}: {count}")


if __name__ == "__main__":
    main()
