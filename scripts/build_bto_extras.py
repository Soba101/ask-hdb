"""Add to data/clean/bto_projects.parquet what the launch annexes do not cover: earlier Tengah projects and HDB's upcoming projects.

Run after scripts/build_bto.py (which rewrites the file). It is safe to run again: it replaces its own rows.
- status "launched": the Tengah projects of 2021 to 2023 from bto_flats_history.parquet, located with OneMap by name.
- status "upcoming": the 7 projects HDB lists for the November 2026 exercise (data_sources/bto_upcoming/upcoming_2026-11.csv, tracked in Git: HDB's server refuses scripts, so it cannot be downloaded again).
  They have no name, price, wait time or category yet, so none is invented.
"""

import httpx
import numpy as np
import pandas as pd
from build_bto import CLEAN, ROOT, locate, slug

from ask_hdb.geo.client import OneMap, load_credentials

# History name -> (clean name, the OneMap names to search; several searches are averaged into one site).
TENGAH = {
    "Parc Woods @ Tengah": ("Parc Woods @ Tengah", ["Parc Woods @ Tengah"]),
    "Garden Bloom @ Tengah": ("Garden Bloom @ Tengah", ["Garden Bloom @ Tengah"]),
    "Parc Glen @ Tengah": ("Parc Glen @ Tengah", ["Parc Glen @ Tengah"]),
    "Parc Clover @ Tengah": ("Parc Clover @ Tengah", ["Parc Clover @ Tengah"]),
    "Brickland Weave": ("Brickland Weave", ["Brickland Weave"]),
    "Non-Mature Town Plantation Verge": ("Plantation Verge", ["Plantation Verge"]),
    "Parc Meadow @ Tengah 37/": ("Parc Meadow @ Tengah", ["Parc Meadow @ Tengah"]),
    "Plantation Edge I & II 36 (Plantation Edge I) 40 (Plantation Edge II)": ("Plantation Edge I & II", ["Plantation Edge I", "Plantation Edge II"]),
}


def history_rows(api, cache):
    history = pd.read_parquet(CLEAN / "bto_flats_history.parquet")
    rows = []
    for raw, (name, searches) in TENGAH.items():
        group = history[history.project == raw]
        if group.empty:
            continue
        sites = [s for s in (locate(api, q, cache) for q in searches) if s]
        first = group.iloc[0]
        rows.append({"project_id": "bto_" + slug(name), "name": name, "category": first.category, "first_launch": group.launch.min(),
                     "wait_months": first.wait_months, "units": int(group.drop_duplicates(["launch", "flat_type", "price_low"]).units.sum()),
                     "lat": float(np.mean([s["lat"] for s in sites])) if sites else np.nan,
                     "lng": float(np.mean([s["lng"] for s in sites])) if sites else np.nan,
                     "road_name": sites[0]["road_name"] if sites else None, "town": "TENGAH",
                     "site": "approximate" if sites else "not_found", "status": "launched", "flat_types": None})
    return rows


def upcoming_rows():
    table = pd.read_csv(ROOT / "data_sources/bto_upcoming/upcoming_2026-11.csv")
    return [{"project_id": "bto_up_" + row.code.lower(), "name": f"{row.town.title()} upcoming BTO (HDB code {row.code})", "category": None,
             "first_launch": "2026-11", "wait_months": np.nan, "units": int(row.units), "lat": row.lat, "lng": row.lng, "road_name": None,
             "town": row.town, "site": "hdb_indicative", "status": "upcoming", "flat_types": row.flat_types.replace("|", ", ")}
            for row in table.itertuples()]


def main():
    projects = pd.read_parquet(CLEAN / "bto_projects.parquet")
    if "status" not in projects:
        projects["status"] = "launched"
    if "flat_types" not in projects:
        projects["flat_types"] = None
    own = projects.project_id.str.startswith("bto_up_") | projects.project_id.isin(["bto_" + slug(n) for n, _ in TENGAH.values()])
    projects = projects[~own]  # this script's own earlier rows; the annex rows are kept
    cache_path = CLEAN / "bto_site_cache.json"
    import json
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    with httpx.Client() as client:
        api = OneMap(client, load_credentials())
        extra = history_rows(api, cache) + upcoming_rows()
    cache_path.write_text(json.dumps(cache, indent=1))
    out = pd.concat([projects, pd.DataFrame(extra)], ignore_index=True)
    out.to_parquet(CLEAN / "bto_projects.parquet", index=False)
    print(out.groupby("status").size().to_dict(), "| not found:", int((out.site == "not_found").sum()))


if __name__ == "__main__":
    main()
