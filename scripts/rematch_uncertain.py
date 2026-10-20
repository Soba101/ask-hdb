"""Re-check 'uncertain' geocodes offline after a street-name fix. Makes no OneMap calls."""

from pathlib import Path

import pandas as pd

from ask_hdb.geo.storage import load_cache, save_cache, select_blocks, write_outputs
from ask_hdb.geo.streets import normalize_street

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / "data/clean"
    cache = load_cache(directory / "geocode_cache.json")
    blocks = select_blocks(pd.read_parquet(directory / "resale.parquet"))
    streets = dict(zip(blocks.block_id, blocks.street_name))
    fixed = 0
    for block_id, record in cache.items():
        if record["status"] != "uncertain" or block_id not in streets:
            continue
        # The stored candidate has the OneMap road name; accept it if the streets now agree.
        if normalize_street(record["road_name"] or "") == normalize_street(streets[block_id]):
            record["status"] = "found"
            fixed += 1
    save_cache(directory / "geocode_cache.json", cache)
    write_outputs(directory, blocks, cache)
    print(f"uncertain -> found: {fixed}")


if __name__ == "__main__":
    main()
