"""Build the cleaned resale table from the local raw download."""

from pathlib import Path

import pandas as pd

from ask_hdb.clean import clean

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = ROOT / "data/raw/resale.csv"
    target = ROOT / "data/clean/resale.parquet"
    # Read blocks as text so leading zeroes remain part of their stable IDs.
    raw = pd.read_csv(source, dtype={"block": str})
    result = clean(raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(target, index=False)


if __name__ == "__main__":
    main()
