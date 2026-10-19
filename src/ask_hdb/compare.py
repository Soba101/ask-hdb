"""Compare an asking price with recent sales of similar flats."""

import pandas as pd

from ask_hdb.sales import _filtered, find_sales, price_stats


def _locations(df, block_id):
    rows = df.loc[df["block_id"].eq(block_id)]
    if not rows.empty:
        return [
            ("block", df["block_id"].eq(block_id)),
            ("street", df["street_name"].isin(rows["street_name"])
             & df["town"].isin(rows["town"])),
            ("town", df["town"].isin(rows["town"])),
        ]

    # A missing block can still share a recorded street's stable address suffix.
    parts = str(block_id).split("_", 2)
    if len(parts) == 3 and parts[0] == "blk" and parts[2]:
        suffixes = df["block_id"].str.split("_", n=2).str[-1]
        towns = df.loc[suffixes.eq(parts[2]), "town"].dropna().unique()
        # An ambiguous street must not silently choose a town.
        if len(towns) == 1:
            return [("town", df["town"].eq(towns[0]))]
    return []


def compare_price(
    df: pd.DataFrame,
    block_id,
    price,
    *,
    flat_type,
    storey_mid=None,
    lease_left_months=None,
    floor_area_sqm=None,
    as_of=None,
    months=12,
    storey_tol=3,
    lease_tol_months=60,
    area_tol_sqm=10,
    min_n=5,
    max_examples=10,
) -> dict:
    """Use the narrowest sufficient sample; this is no prediction of future prices.

    Quartile boundaries belong to the middle half. Statistics use the same
    linear interpolation and integer rounding as price_stats.
    """
    if months < 1 or min_n < 1:
        raise ValueError("months and min_n must be positive")
    if min(storey_tol, lease_tol_months, area_tol_sqm) < 0:
        raise ValueError("Tolerances must be nonnegative")

    notes = ["Comparison of past sales, not a valuation"]
    locations = _locations(df, block_id)
    if not locations:
        return {"n_comparables": 0, "level": None, "notes": notes + [
            f"Thin sample: fewer than {min_n} comparables", "Unknown block; town unavailable",
        ]}

    # Anchor to the data so a repeated query does not drift with the calendar.
    end = df["sale_month"].max() if as_of is None else pd.Timestamp(as_of)
    end = end.to_period("M")
    start = end - (months - 1)
    rows = _filtered(
        df, flat_type=flat_type, since=start.to_timestamp(), until=end.to_timestamp(),
    )
    for column, value, tolerance in (
        ("storey_mid", storey_mid, storey_tol),
        ("lease_left_months", lease_left_months, lease_tol_months),
        ("floor_area_sqm", floor_area_sqm, area_tol_sqm),
    ):
        if value is not None:
            rows = rows.loc[rows[column].between(value - tolerance, value + tolerance)]

    # Keep the widest result when every level falls short.
    for level, mask in locations:
        comparable = rows.loc[mask.loc[rows.index]]
        if len(comparable) >= min_n:
            break
    if level != "block":
        notes.append(f"Widened to {level} level")
    if len(comparable) < min_n:
        notes.append(f"Thin sample: fewer than {min_n} comparables")
    result = {
        "level": level, "n_comparables": len(comparable),
        "window": f"{start}..{end}", "price": price, "examples": [], "notes": notes,
    }
    # No price statistics exist for an empty sample.
    if comparable.empty:
        return result

    stats = price_stats(comparable)
    result.update({key: stats[key] for key in ("median", "p25", "p75", "min", "max")})
    median = stats["median"]
    result.update({
        "diff_vs_median": int(price - median),
        "pct_vs_median": round((price - median) / median * 100, 1),
        "position": ("below_p25" if price < stats["p25"] else
                     "above_p75" if price > stats["p75"] else "within_middle_half"),
    })
    columns = [
        "block_id", "sale_month", "resale_price", "storey_low", "storey_high",
        "floor_area_sqm", "lease_left_months",
    ]
    result["examples"] = find_sales(comparable.loc[:, columns], limit=max_examples)
    return result
