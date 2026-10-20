"""Check local block points against downloaded building outlines, offline."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ask_hdb.geo.distance import haversine_km

ROOT = Path(__file__).resolve().parents[1]


def check_geocodes(blocks, buildings):
    centroids = {}
    for feature in buildings["features"]:
        postal = str(feature["properties"].get("POSTAL_COD", "")).strip()
        if not postal:
            continue
        ring = np.asarray(feature["geometry"]["coordinates"][0], dtype=float)
        # A repeated closing vertex should not bias the mean towards one corner.
        if len(ring) > 1 and np.array_equal(ring[0], ring[-1]):
            ring = ring[:-1]
        lng, lat = ring[:, :2].mean(axis=0)
        centroids.setdefault(postal, []).append((lat, lng))
    matched, unmatched, flagged = 0, 0, []
    for row in blocks.to_dict("records"):
        candidates = centroids.get(str(row["postal"]).strip(), [])
        lat, lng = row["lat"], row["lng"]
        if not candidates or pd.isna(lat) or pd.isna(lng):
            unmatched += 1
            continue
        # Multiple outlines can share a postal code; compare to the closest one.
        metres = min(float(haversine_km(lat, lng, a, b)) * 1000 for a, b in candidates)
        matched += 1
        if metres > 300:
            flagged.append((row["block_id"], metres))
    lines = [f"matched: {matched}", f"unmatched: {unmatched}", f"over 300 m: {len(flagged)}"]
    lines += [f"{block_id}: {metres:.1f} m" for block_id, metres in sorted(flagged)]
    return "\n".join(lines) + "\n"


def main():
    directory = ROOT / "data/clean"
    blocks = pd.read_parquet(directory / "blocks.parquet")
    buildings = json.loads((ROOT / "data/raw/places/hdb_buildings.geojson").read_text())
    report = check_geocodes(blocks, buildings)
    (directory / "geocode_check.txt").write_text(report)
    print(report, end="")


if __name__ == "__main__":
    main()
