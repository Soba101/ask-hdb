"""Town-level comparison of past BTO launch price ranges with later resale prices (descriptive, not a forecast)."""

import pandas as pd

MOP_YEARS = 5
AFTER_MOP_YEARS = 2  # only sales in the first years after the MOP, so launch and resale are not decades apart


def launch_vs_resale(sales: pd.DataFrame, ranges: pd.DataFrame, min_n: int = 30,
                     lease_offset: tuple[int, int] = (3, 5)) -> pd.DataFrame:
    """One row per (financial year, town, room type) launch range with resale prices of comparable later flats.

    Comparable = same town and flat type, lease start between FY+3 and FY+5, sold at least MOP_YEARS after the lease
    start, and no later than MOP_YEARS + AFTER_MOP_YEARS (sale years are used, so this is approximate). Rows with fewer than min_n sales are dropped.
    """
    lows = ranges.assign(room_type=ranges.room_type.str.strip(),
                         price_low=pd.to_numeric(ranges.price_low, errors="coerce"),
                         price_high=pd.to_numeric(ranges.price_high, errors="coerce"))
    lows = lows[lows.price_low.notna() & lows.price_high.notna() & (lows.price_low > 0)]
    later = sales.assign(sale_year=sales.sale_month.dt.year)
    later = later[(later.sale_year - later.lease_commence_year).between(MOP_YEARS, MOP_YEARS + AFTER_MOP_YEARS)]
    rows = []
    for r in lows.itertuples():
        pick = later[(later.town == r.town) & (later.flat_type == r.room_type.upper().replace("-", " "))
                     & later.lease_commence_year.between(r.financial_year + lease_offset[0],
                                                         r.financial_year + lease_offset[1])]
        if len(pick) < min_n:
            continue
        median = float(pick.resale_price.median())
        rows.append({"financial_year": r.financial_year, "town": r.town, "flat_type": pick.flat_type.iloc[0],
                     "launch_low": int(r.price_low), "launch_high": int(r.price_high),
                     "n_resales": len(pick), "resale_median": median,
                     "resale_p25": float(pick.resale_price.quantile(.25)),
                     "resale_p75": float(pick.resale_price.quantile(.75)),
                     "median_minus_launch_high": median - r.price_high})
    return pd.DataFrame(rows)
