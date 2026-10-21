"""Build BTO launch tables from the downloaded HDB annexes and locate each project (approximately) with OneMap.

Writes data/clean/bto_flats.parquet (one row per project and flat type per launch) and
data/clean/bto_projects.parquet (one row per project with an approximate site and town).
"""

import json
import re
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from pypdf import PdfReader

from ask_hdb.bto.parse import parse_annex_a
from ask_hdb.geo.client import GeocodeError, OneMap, load_credentials
from ask_hdb.geo.distance import haversine_km

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN = ROOT / "data/raw/bto", ROOT / "data/clean"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def locate(api, name, cache):
    """Approximate site: the mean of OneMap results named exactly like the project (its blocks)."""
    if name not in cache:
        try:
            results = api.search(name).get("results", [])
        except GeocodeError:
            results = []  # an unknown name comes back as an error with no results
        hits = [r for r in results if r.get("SEARCHVAL", "").upper() == name.upper() and r.get("POSTAL") != "NIL"]
        cache[name] = ({"lat": float(np.mean([float(r["LATITUDE"]) for r in hits])),
                        "lng": float(np.mean([float(r["LONGITUDE"]) for r in hits])),
                        "road_name": hits[0]["ROAD_NAME"], "postal": hits[0]["POSTAL"]} if hits else None)
    return cache[name]


def town_of(lat, lng, blocks, sales_towns):
    """Town of the nearest existing blocks (a site has no block number, so this is approximate)."""
    near = blocks.assign(km=haversine_km(lat, lng, blocks.lat.to_numpy(), blocks.lng.to_numpy())).nsmallest(5, "km")
    return None if near.km.iloc[0] > 2 else sales_towns[near.block_id].mode().iloc[0]


def main():
    flats = []
    for pdf in sorted(RAW.glob("*-annex-a.pdf")):
        text = "\n".join((page.extract_text() or "") for page in PdfReader(pdf).pages)
        flats += parse_annex_a(text, pdf.name[:7])
    flats = pd.DataFrame(flats)
    flats["project_id"] = "bto_" + flats.project.map(slug)
    flats.to_parquet(CLEAN / "bto_flats.parquet", index=False)

    cache_path = CLEAN / "bto_site_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    blocks = pd.read_parquet(CLEAN / "blocks.parquet")
    towns = pd.read_parquet(CLEAN / "resale.parquet").drop_duplicates("block_id").set_index("block_id").town
    rows = []
    with httpx.Client() as client:
        api = OneMap(client, load_credentials())
        for name, group in flats.groupby("project", sort=False):
            site = locate(api, name, cache)
            cache_path.write_text(json.dumps(cache, indent=1))
            first = group.iloc[0]
            rows.append({"project_id": first.project_id, "name": name, "category": first.category,
                         "first_launch": group.launch.min(), "wait_months": first.wait_months,
                         "units": int(group.drop_duplicates(["launch", "flat_type", "price_low"]).units.sum()),
                         "lat": site and site["lat"], "lng": site and site["lng"],
                         "road_name": site and site["road_name"],
                         "town": site and town_of(site["lat"], site["lng"], blocks, towns),
                         "site": "approximate" if site else "not_found"})
    pd.DataFrame(rows).astype({"lat": float, "lng": float}).to_parquet(CLEAN / "bto_projects.parquet", index=False)
    print(f"{len(flats)} flat rows, {len(rows)} projects, {sum(r['site'] == 'not_found' for r in rows)} sites not found")


if __name__ == "__main__":
    main()
