"""BTO launch questions answered from the tables built by scripts/build_bto.py (indicative prices at launch)."""

from functools import lru_cache
from pathlib import Path

import pandas as pd

from ask_hdb.geo.distance import nearest_to_point
from ask_hdb.geo.loaders import load_places

CLEAN = Path(__file__).resolve().parents[3] / "data/clean"
PRICE_NOTE = ("Indicative price ranges at launch, excluding grants, for 99-year leases; actual prices vary with "
              "each flat's attributes. Sites are approximate.")


@lru_cache(maxsize=1)
def load_projects():
    return pd.read_parquet(CLEAN / "bto_projects.parquet")


@lru_cache(maxsize=1)
def load_flats():
    return pd.read_parquet(CLEAN / "bto_flats.parquet")


def list_bto_projects(name=None, town=None, flat_type=None, launch_month=None, category=None, max_price=None, limit=10):
    projects, flats = load_projects(), load_flats()
    if name:
        projects = projects[projects.name.str.upper().str.contains(name.upper(), regex=False)]
    if town:
        projects = projects[projects.town.fillna("").str.upper().eq(town.upper())]
    if category:
        projects = projects[projects.category.str.upper().eq(category.upper())]
    if launch_month:
        # A project can be offered again in a later launch (for example Redhill Peaks); match any of its launches.
        launched = set(flats[flats.launch.eq(launch_month)].project_id)
        projects = projects[projects.project_id.isin(launched)]
    rows = flats[flats.project_id.isin(projects.project_id)]
    if flat_type:
        rows = rows[rows.flat_type.str.upper().eq(flat_type.upper())]
    if max_price is not None:
        rows = rows[rows.price_low <= max_price]
    if launch_month:
        rows = rows[rows.launch.eq(launch_month)]
    out = []
    for project in projects.itertuples():
        mine = rows[rows.project_id.eq(project.project_id)]
        if mine.empty:
            continue
        out.append({"project_id": project.project_id, "name": project.name, "town": project.town if isinstance(project.town, str) else "unknown (site not found)",
                    "category": project.category, "wait_months": int(project.wait_months),
                    "launches": sorted(set(mine.launch)),
                    "flats": [{"flat_type": r.flat_type, "units": int(r.units), "price_low": int(r.price_low),
                               "price_high": int(r.price_high)} for r in mine.itertuples()]})
    return {"n_projects": len(out), "projects": out[:limit], "note": PRICE_NOTE}


def bto_nearby(project_id, kind, n=3):
    row = load_projects().loc[lambda d: d.project_id.eq(project_id)]
    if row.empty:
        raise ValueError(f"Unknown project_id: {project_id}")
    site = row.iloc[0]
    if pd.isna(site.lat):
        raise ValueError(f"No site coordinates for {project_id} (OneMap does not list it yet)")
    return {"project": site["name"], "places": nearest_to_point(site.lat, site.lng, load_places(), kind, n),
            "note": "Straight-line distance from an approximate site (a BTO site has no block number)."}


HISTORY_LIMITS = [
    "Descriptive only, not a forecast: past launches compared with later resale, never an expected gain.",
    "Resale prices include the 2021-2023 price rise; ratios and gaps between cohorts are not stable.",
    "Launch ranges are before grants; resale prices are what buyers paid. Neither includes loan interest, CPF accrued interest, fees or renovation.",
    "Town and flat type only (no project, floor or lease detail). Only 9 non-mature towns have enough sales.",
    "Comparable resale = same town and flat type, lease start 3 to 5 years after the launch financial year, sold 5 to 7 years after lease start (approximate).",
]


@lru_cache(maxsize=1)
def load_history():
    return pd.read_parquet(CLEAN / "bto_launch_vs_resale_town.parquet")


def bto_history(town, flat_type, financial_year=None):
    """Past BTO launch price ranges next to resale prices of comparable flats 5-7 years after lease start."""
    rows = load_history()
    rows = rows[rows.town.str.upper().eq(town.upper()) & rows.flat_type.eq(flat_type.upper().replace("-", " "))]
    if financial_year is not None:
        rows = rows[rows.financial_year.eq(financial_year)]
    cols = ["financial_year", "launch_low", "launch_high", "n_resales", "resale_median", "resale_p25", "resale_p75"]
    out = rows.sort_values("financial_year")[cols].to_dict("records")
    return {"town": town.upper(), "flat_type": flat_type, "n_rows": len(out), "rows": out, "limits": HISTORY_LIMITS,
            "coverage": "launch financial years 2008-2018; towns: " + ", ".join(sorted(load_history().town.unique()))}
