"""Build place records from the downloaded MRT exits and school directory."""

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["place_id", "kind", "name", "postal_code", "lat", "lng", "exit_count"]


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def unique_id(prefix, name, used):
    base = f"{prefix}_{slug(name)}"
    candidate, suffix = base, 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def build_places(exits, schools):
    groups = {}
    for feature in exits["features"]:
        name = feature["properties"]["STATION_NA"].strip()
        # GeoJSON puts longitude first, unlike the distance helpers.
        lng, lat = feature["geometry"]["coordinates"][:2]
        groups.setdefault(name, []).append((lat, lng))
    rows, used = [], set()
    for source_name, coordinates in sorted(groups.items()):
        # LRT (light rail: Punggol, Sengkang, Bukit Panjang) is a different service; keep it apart from MRT.
        kind = "lrt" if re.search(r" LRT STATION$", source_name, re.IGNORECASE) else "mrt"
        name = re.sub(r" (?:MRT|LRT) STATION$", "", source_name, flags=re.IGNORECASE)
        rows.append({"place_id": unique_id(kind, name, used), "kind": kind, "name": name,
                     "lat": sum(p[0] for p in coordinates) / len(coordinates),
                     "lng": sum(p[1] for p in coordinates) / len(coordinates),
                     "exit_count": len(coordinates), "postal_code": None})
    selected = schools.loc[schools.mainlevel_code.isin(["PRIMARY", "MIXED LEVEL (P1-S4)"])]
    for row in selected.sort_values(["school_name", "postal_code"]).to_dict("records"):
        name = row["school_name"].strip()
        rows.append({"place_id": unique_id("school", name, used), "kind": "primary_school",
                     "name": name, "postal_code": str(row["postal_code"]).strip().zfill(6),
                     "lat": None, "lng": None, "exit_count": None})
    return pd.DataFrame(rows, columns=COLUMNS).astype({"lat": float, "lng": float})


def main():
    raw = ROOT / "data/raw/places"
    places = build_places(json.loads((raw / "mrt_exits.geojson").read_text()),
                          pd.read_csv(raw / "schools.csv", dtype=str, keep_default_na=False))
    output = ROOT / "data/clean/places.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    places.to_parquet(output, index=False)
    for kind, count in places.kind.value_counts().items():
        print(f"{kind}: {count}")
    print(f"MRT exits: {int(places.exit_count.sum())}")


if __name__ == "__main__":
    main()
