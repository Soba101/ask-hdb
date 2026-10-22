"""Independent expected values for the map-first eval questions (plain pandas and numpy, not ask_hdb.geo).

Usage: uv run --no-sync python scripts/build_map_expected.py ORIGIN_ID KIND [KM]
ORIGIN_ID is a block_id, a place_id (mrt_..., school_...) or a project_id (bto_...). Prints the nearest place of KIND
(straight-line, haversine, mean Earth radius 6371.0088 km) and, with KM, how many places of KIND are within KM (inclusive).
"""

import sys

import numpy as np
import pandas as pd

origin, kind = sys.argv[1], sys.argv[2]
km = float(sys.argv[3]) if len(sys.argv) > 3 else None
blocks = pd.read_parquet("data/clean/blocks.parquet")
places = pd.read_parquet("data/clean/places.parquet")
projects = pd.read_parquet("data/clean/bto_projects.parquet")
for frame, column in ((blocks, "block_id"), (places, "place_id"), (projects, "project_id")):
    hit = frame[frame[column] == origin]
    if len(hit):
        lat, lng = float(hit.lat.iloc[0]), float(hit.lng.iloc[0])
        break
else:
    sys.exit(f"unknown id {origin}")
pool = places[(places.kind == kind) & (places.place_id != origin)].dropna(subset=["lat", "lng"])
p1, p2 = np.radians(lat), np.radians(pool.lat.to_numpy())
a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(pool.lng.to_numpy() - lng) / 2) ** 2
dist = 6371.0088 * 2 * np.arcsin(np.sqrt(a))
order = np.argsort(dist)
print("nearest:", pool.name.iloc[order[0]], round(float(dist[order[0]]), 4), "km")
if km is not None:
    print(f"within {km} km:", int((dist <= km).sum()))
