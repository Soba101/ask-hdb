"""Load local geo tables only when a distance tool needs them."""

from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]


def _load(name):
    path = ROOT / "data/clean" / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path.name}; build local geo data first")
    return pd.read_parquet(path)


@lru_cache(maxsize=1)
def load_blocks():
    return _load("blocks")


@lru_cache(maxsize=1)
def load_places():
    return _load("places")


@lru_cache(maxsize=1)
def load_amenities():
    # Bus stops, supermarkets and MRT exits; built by scripts/build_amenities.py.
    return _load("amenities")
