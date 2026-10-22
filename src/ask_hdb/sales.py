"""Query cleaned sales without changing the source table."""

import pandas as pd


def _filtered(
    df: pd.DataFrame,
    *,
    town=None,
    flat_type=None,
    block_id=None,
    storey_min=None,
    storey_max=None,
    min_lease_months=None,
    since=None,
    until=None,
    max_price=None,
) -> pd.DataFrame:
    bounds = []
    for name, value in (("since", since), ("until", until)):
        if value is not None:
            try:
                # A bare year is a whole year: 2024 would parse as 1970 and "2024" as January only.
                if isinstance(value, (int, str)) and str(value).strip().isdigit() and len(str(value).strip()) == 4:
                    value = f"{str(value).strip()}-{'01' if name == 'since' else '12'}"
                date = pd.to_datetime(value, errors="coerce")
                if pd.isna(date):
                    raise ValueError("Missing date")
                bounds.append((name, date.to_period("M").to_timestamp()))
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f"Invalid {name} date: {value!r}") from exc
    # Validate bounds even when there are no source rows.
    if df.empty:
        return df
    mask = pd.Series(True, index=df.index)
    for column, value in (("town", town), ("flat_type", flat_type), ("block_id", block_id)):
        if value is not None:
            mask &= df[column].eq(value)

    # A reported floor band has no exact floor; use its midpoint consistently.
    for column, value in (
        ("storey_mid", storey_min), ("lease_left_months", min_lease_months),
    ):
        if value is not None:
            mask &= df[column].ge(value)
    for column, value in (("storey_mid", storey_max), ("resale_price", max_price)):
        if value is not None:
            mask &= df[column].le(value)

    # Month bounds include the whole month, even when passed a specific day.
    for name, month in bounds:
        mask &= df["sale_month"].ge(month) if name == "since" else df["sale_month"].le(month)
    return df.loc[mask]


def find_sales(
    df: pd.DataFrame,
    *,
    town=None,
    flat_type=None,
    block_id=None,
    storey_min=None,
    storey_max=None,
    min_lease_months=None,
    since=None,
    until=None,
    max_price=None,
    limit=50,
) -> list[dict]:
    """Return newest sales, with inclusive bounds and midpoint floor filtering."""
    rows = _filtered(
        df, town=town, flat_type=flat_type, block_id=block_id,
        storey_min=storey_min, storey_max=storey_max, min_lease_months=min_lease_months,
        since=since, until=until, max_price=max_price,
    )
    if rows.empty:
        return []
    # Stable sorting keeps equal-month rows in their original order.
    rows = rows.sort_values("sale_month", ascending=False, kind="stable").head(max(0, limit))
    rows = rows.copy()
    rows["sale_month"] = rows["sale_month"].dt.strftime("%Y-%m")
    rows = rows.rename(columns={"resale_price": "price"})
    return rows.to_dict(orient="records")


def price_stats(df: pd.DataFrame, **filters) -> dict:
    """Summarise all matching sales; round prices to the nearest integer, ties to even.

    Accept the same filters as find_sales, except limit. Storey bounds use midpoints.
    """
    rows = _filtered(df, **filters)
    if rows.empty:
        return {"n_sales": 0}
    prices = rows["resale_price"]
    start = rows["sale_month"].min().strftime("%Y-%m")
    end = rows["sale_month"].max().strftime("%Y-%m")
    return {
        "n_sales": len(rows),
        "median": round(prices.median()),
        "mean": round(prices.mean()),
        "min": int(prices.min()),
        "max": int(prices.max()),
        "p25": round(prices.quantile(0.25)),
        "p75": round(prices.quantile(0.75)),
        "period": f"{start}..{end}",
    }
