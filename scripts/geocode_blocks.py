"""Geocode recent resale blocks, resuming from a local OneMap cache."""

import argparse
from pathlib import Path

import httpx
import pandas as pd

from ask_hdb.geo.client import OneMap, load_credentials
from ask_hdb.geo.runner import geocode
from ask_hdb.geo.storage import select_blocks

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Include every resale block")
    parser.add_argument("--limit", type=int, help="Process at most this many selected blocks")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be nonnegative")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    directory = ROOT / "data/clean"
    sales = pd.read_parquet(directory / "resale.parquet")
    blocks = select_blocks(sales, all_blocks=args.all, limit=args.limit)
    with httpx.Client() as client:
        complete = geocode(blocks, OneMap(client, load_credentials()), directory)
    print(f"Outputs saved in {directory}")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
