"""Geocode primary schools by postal code, resuming from a disk cache."""

from pathlib import Path

import httpx
import pandas as pd

from ask_hdb.geo.client import OneMap, load_credentials
from ask_hdb.geo.schools import geocode_schools

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / "data/clean"
    places = pd.read_parquet(directory / "places.parquet")
    with httpx.Client() as client:
        complete = geocode_schools(places, OneMap(client, load_credentials()), directory)
    print(f"School coordinates and cache saved in {directory}")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
