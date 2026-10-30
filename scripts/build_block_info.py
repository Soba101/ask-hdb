"""Build data/clean/block_info.parquet: HDB's own property information, one row per located block.

Source: HDB Property Information on data.gov.sg (Singapore Open Data Licence v1.0), saved as
data/raw/property/hdb_property_information.csv. A block is matched by block number and normalised street name.
A key with more than one residential row is left out rather than guessed.

Run after scripts/geocode_blocks.py:  uv run python scripts/build_block_info.py
"""

from pathlib import Path

import pandas as pd

from ask_hdb.geo.streets import normalize_street

ROOT = Path(__file__).resolve().parents[1]
SOLD = ["1room_sold", "2room_sold", "3room_sold", "4room_sold", "5room_sold", "exec_sold", "multigen_sold", "studio_apartment_sold"]
RENTAL = ["1room_rental", "2room_rental", "3room_rental", "other_room_rental"]
KEEP = ["year_completed", "max_floor_lvl", "total_dwelling_units", "commercial", "market_hawker", "multistorey_carpark", *SOLD, *RENTAL]


def build(blocks, properties):
    properties = properties[properties.residential.eq("Y")].copy()
    properties["key"] = list(zip(properties.blk_no.str.strip().str.upper(), properties.street.map(normalize_street)))
    properties = properties[~properties.key.duplicated(keep=False)]
    lookup = dict(zip(properties.key, properties[KEEP].to_dict("records")))
    rows = []
    for row in blocks.itertuples():
        key = (str(row.block).strip().upper(), normalize_street(row.street_name))
        if key in lookup:
            rows.append({"block_id": row.block_id, **lookup[key]})
    out = pd.DataFrame(rows)
    for column in ["year_completed", "max_floor_lvl", "total_dwelling_units", *SOLD, *RENTAL]:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("Int64")
    for column in ["commercial", "market_hawker", "multistorey_carpark"]:
        out[column] = out[column].eq("Y")
    return out


def main():
    blocks = pd.read_parquet(ROOT / "data/clean/blocks.parquet")
    properties = pd.read_csv(ROOT / "data/raw/property/hdb_property_information.csv", dtype={"blk_no": str})
    out = build(blocks, properties)
    out.to_parquet(ROOT / "data/clean/block_info.parquet", index=False)
    print(f"block_info.parquet: {len(out)} of {len(blocks)} blocks matched")


if __name__ == "__main__":
    main()
