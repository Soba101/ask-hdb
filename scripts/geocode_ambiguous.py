"""Retry 'not_found' blocks using HDB building outlines to pick between same-road listings."""

import json
from pathlib import Path

import httpx
import pandas as pd

from ask_hdb.geo.client import OneMap, load_credentials
from ask_hdb.geo.matching import match_with_outlines
from ask_hdb.geo.storage import load_cache, save_cache, select_blocks, write_outputs

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / "data/clean"
    cache = load_cache(directory / "geocode_cache.json")
    blocks = select_blocks(pd.read_parquet(directory / "resale.parquet"))
    outlines = json.loads((ROOT / "data/raw/places/hdb_buildings.geojson").read_text())
    postals = {(str(f["properties"]["BLK_NO"]).strip().upper(), str(f["properties"]["POSTAL_COD"]).strip())
               for f in outlines["features"]}
    todo = blocks[blocks.block_id.map(lambda b: cache.get(b, {}).get("status") == "not_found")]
    fixed = 0
    with httpx.Client() as client:
        api = OneMap(client, load_credentials())  # same 2 requests/second politeness as the main run
        for row in todo.to_dict("records"):
            record = match_with_outlines(row["block"], row["street_name"], api.search(
                f"{row['block']} {row['street_name']}"), postals)
            if record["status"] == "found":
                cache[row["block_id"]] = record
                fixed += 1
    save_cache(directory / "geocode_cache.json", cache)
    write_outputs(directory, blocks, cache)
    print(f"not_found -> found: {fixed} of {len(todo)}")


if __name__ == "__main__":
    main()
