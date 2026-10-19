"""Turn raw resale records into consistent, reusable sale rows."""

import pandas as pd

REQUIRED_COLUMNS = (
    "month", "town", "flat_type", "block", "street_name", "storey_range",
    "floor_area_sqm", "flat_model", "lease_commence_date", "remaining_lease",
    "resale_price",
)


def _lease_months(raw: pd.Series, years: pd.Series, dates: pd.Series) -> pd.Series:
    text = raw.fillna("").astype(str).str.strip()
    parts = text.str.extract(r"^(\d+) years?(?:\s+(\d+) months?)?$")
    if (text.ne("") & parts[0].isna()).any():
        raise ValueError("remaining_lease must be years, years and months, or blank")

    parsed = pd.to_numeric(parts[0]) * 12 + pd.to_numeric(parts[1]).fillna(0)
    # Only the start year is known, so missing leases count from January.
    # Resale records describe flats with an original 99-year lease.
    fallback = (years + 99 - dates.dt.year) * 12 - (dates.dt.month - 1)
    return parsed.fillna(fallback).astype("int64")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean a copy of raw sales, preserving address text and every row."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    raw = df.loc[:, REQUIRED_COLUMNS].copy()
    dates = pd.to_datetime(raw["month"], format="%Y-%m")
    years = pd.to_numeric(raw["lease_commence_date"]).astype("int64")
    storeys = raw["storey_range"].str.extract(r"^\s*(\d+)\s+TO\s+(\d+)\s*$")
    if storeys.isna().any().any():
        raise ValueError("storey_range must contain two floors, such as '10 TO 12'")
    low, high = storeys[0].astype("int64"), storeys[1].astype("int64")

    # IDs use the address rather than a row index, so they survive new downloads.
    street_slug = (
        raw["street_name"].str.lower().str.replace(r"[^a-z0-9]+", "-", regex=True)
        .str.strip("-")
    )
    block_id = "blk_" + raw["block"].astype(str).str.lower() + "_" + street_slug
    result = pd.DataFrame({
        "sale_month": dates,
        "year": dates.dt.year.astype("int64"),
        "town": raw["town"],
        "flat_type": raw["flat_type"],
        "block": raw["block"].astype(str),
        "street_name": raw["street_name"],
        "block_id": block_id,
        "storey_low": low,
        "storey_high": high,
        "storey_mid": (low + high) / 2,
        "floor_area_sqm": pd.to_numeric(raw["floor_area_sqm"]).astype(float),
        "flat_model": raw["flat_model"],
        "lease_commence_year": years,
        "lease_left_months": _lease_months(raw["remaining_lease"], years, dates),
        "resale_price": pd.to_numeric(raw["resale_price"]).astype("int64"),
    })
    # Identical rows are kept: the data has no unit ID, so they may be real separate sales.
    return result
