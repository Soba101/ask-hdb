"""Select stable block IDs and save only the small geocode records."""

import json
import os
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd

ADDRESS_COLUMNS = ["block_id", "block", "street_name", "town"]
FIELDS = ["status", "lat", "lng", "postal", "road_name", "query"]


def select_blocks(sales: pd.DataFrame, all_blocks=False, limit=None) -> pd.DataFrame:
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative")
    if not all_blocks and not sales.empty:
        months = pd.to_datetime(sales["sale_month"]).dt.to_period("M")
        sales = sales.loc[months > months.max() - 36]
    blocks = sales[ADDRESS_COLUMNS].drop_duplicates("block_id").sort_values("block_id")
    return blocks if limit is None else blocks.head(limit)


def load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace on the same filesystem so an interruption keeps the old cache intact.
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({key: {field: row[field] for field in FIELDS}
                       for key, row in cache.items()}, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_outputs(directory: Path, blocks: pd.DataFrame, cache: dict) -> None:
    rows, details = [], []
    counts = Counter()
    for block in blocks.to_dict("records"):
        record = cache.get(block["block_id"])
        if record is None:
            continue
        counts[record["status"]] += 1
        if record["status"] == "found":
            rows.append({**block, **{field: record[field] for field in FIELDS}})
        if record["status"] in {"not_found", "uncertain"}:
            details.append(f"{record['status']}: {block['block_id']} | {record['query']}")
    frame = pd.DataFrame(rows, columns=ADDRESS_COLUMNS + FIELDS)
    frame = frame.astype({"lat": "float64", "lng": "float64"})
    frame.to_parquet(directory / "blocks.parquet", index=False)
    lines = [f"{status}: {counts[status]}" for status in
             ("found", "uncertain", "not_found", "error")]
    lines.append(f"pending: {len(blocks) - sum(counts.values())}")
    (directory / "geocode_report.txt").write_text("\n".join(lines + [""] + details) + "\n")
