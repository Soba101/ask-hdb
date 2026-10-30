"""Data for the map-first page: every block and place as GeoJSON, an info card per selection, and the selection
context sent to the agent. Everything is computed by code from the clean tables; the model writes none of it.

Ids from the browser are never trusted: a selection is only used when the id exists in the tables.
"""

import math
import re
from datetime import date
from functools import lru_cache
from string import capwords

import pandas as pd

from ask_hdb.api import blockinfo, buildings
from ask_hdb.bto.queries import load_projects
from ask_hdb.geo.distance import haversine_km, nearest_to_point
from ask_hdb.geo.loaders import ROOT, load_amenities, load_blocks, load_places
from ask_hdb.geo.names import pretty_name
from ask_hdb.rules.bto import BTO_FILE
from ask_hdb.rules.loader import RULES_DIR, load_rules
from ask_hdb.tools import load_sales

KINDS = ("block", "mrt", "lrt", "primary_school", "bto")
MIN_FOR_MEDIAN = 5


def _ok(value):
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def block_label(row):
    return f"Blk {row.block} {capwords(row.street_name)}"


@lru_cache(maxsize=1)
def features():
    """One GeoJSON feature per located block, MRT/LRT station, primary school and BTO site (ids and labels only)."""
    out = []
    blocks = load_blocks()
    for row in blocks[blocks.lat.notna() & blocks.lng.notna()].itertuples():
        out.append(_feature("block", row.block_id, block_label(row), row.lat, row.lng, town=row.town))
    for row in load_places().itertuples():
        kind = {"mrt": "MRT", "lrt": "LRT"}.get(row.kind, "primary school")
        label = f"{pretty_name(row.name)} ({kind})"
        out.append(_feature(row.kind, row.place_id, label, row.lat, row.lng))
    for row in load_projects().itertuples():
        if not (_ok(row.lat) and _ok(row.lng)):
            continue  # a BTO project whose site was not found has no point
        status = getattr(row, "status", "launched")
        label = f"{row.name}, not on sale yet" if status == "upcoming" else f"{row.name} (BTO, approximate site)"
        out.append(_feature("bto", row.project_id, label, row.lat, row.lng, town=row.town if isinstance(row.town, str) else "", status=status))
    return {"type": "FeatureCollection", "features": out}


def _feature(kind, key, label, lat, lng, **extra):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(float(lng), 5), round(float(lat), 5)]},
            "properties": {"kind": kind, "id": key, "label": label, **extra}}


def resolve(selected):
    """Return {kind, id, label, lat, lng} for a selection that exists in the tables, else None."""
    if not isinstance(selected, dict):
        return None
    kind, key = selected.get("kind"), selected.get("id")
    if kind not in KINDS or not isinstance(key, str):
        return None
    if kind == "block":
        table, label = load_blocks().set_index("block_id"), block_label
    elif kind == "bto":
        table, label = load_projects().set_index("project_id"), lambda r: r["name"]
    else:
        table, label = load_places().set_index("place_id"), lambda r: pretty_name(r["name"])
        if table.loc[key, "kind"] != kind if key in table.index else False:
            return None
    if key not in table.index:
        return None
    row = table.loc[key]
    if not (_ok(row.lat) and _ok(row.lng)):
        return None
    row = row.copy()
    if kind == "block":
        row = pd.Series({**row.to_dict(), "block": row.block, "street_name": row.street_name})
    return {"kind": kind, "id": key, "label": label(row), "lat": float(row.lat), "lng": float(row.lng)}


def context_line(selection):
    """The one line the agent sees about the map selection (a label made by code, no coordinates)."""
    if selection is None:
        return None
    ids = {"block": "block_id", "bto": "project_id"}.get(selection["kind"], "place_id")
    return (f"[Map context: the user selected {selection['label']} on the map ({ids}={selection['id']}). "
            f"\"this block\", \"here\" and \"this place\" mean it.]")


def _nearest(lat, lng, kind):
    got = nearest_to_point(lat, lng, load_places(), kind, 1)
    return {"name": pretty_name(got[0]["name"]), "km": round(got[0]["km"], 2)} if got else None


def card(selection):
    """Facts for the selected place, with the sources and the limits that go with them."""
    kind = selection["kind"]
    base = {"kind": kind, "id": selection["id"], "label": selection["label"]}
    if kind == "block":
        return {**base, **_block_facts(selection)}
    if kind == "bto":
        row = load_projects().set_index("project_id").loc[selection["id"]]
        if row.get("status") == "upcoming":
            return {**base, "facts": ["Not on sale yet: HDB lists this as an upcoming project. Its next sales exercise is in November 2026.", f"Units: {int(row.units)}",
                                      f"Flat types: {row.flat_types}",
                                      "No prices, waiting time or completion date are published yet."],
                    "limits": ["HDB marks upcoming projects as preliminary and subject to change; the site is HDB's indicative point.",
                               "Source: HDB Flat Portal, upcoming BTO projects (read 2026-10-30)."]}
        facts = [f"Units: {int(row.units)}"]
        if isinstance(row.category, str):
            facts.insert(0, f"Category: {row.category}")
        elif isinstance(row.get("first_launch"), str):
            facts.insert(0, f"Launched: {row.first_launch} (an earlier exercise; its prices are not shown here)")
        if _ok(row.wait_months):
            facts.append(f"Waiting time: about {int(row.wait_months)} months")
        done = _bto_completion(row.get("first_launch"), row.get("wait_months"), load_sales().sale_month.max())
        if done:
            facts.append(done)
        return {**base, "facts": facts,
                "limits": ["BTO sites are approximate; prices are indicative launch ranges, before grants."]}
    return {**base, **_place_facts(selection)}


def _bto_completion(first_launch, wait_months, latest):
    """Launch month plus HDB's stated waiting time, as an estimate. None when either input is missing or unreadable."""
    if not (isinstance(first_launch, str) and _ok(wait_months)):
        return None
    try:
        done = pd.Period(first_launch, "M") + int(wait_months)
    except ValueError:
        return None
    if done < latest.to_period("M"):
        return "Estimated completion has passed; check HDB for the actual date."
    return f"Estimated completion: about {done} (launch month plus stated waiting time; approximate)"


def _mop_years():
    """MOP length in years for standard flats, from the rules file (one seam so tests can change it)."""
    return load_rules(BTO_FILE).get("mop.standard_years")


def _mop_code(start, data_year, years):
    """0 = within MOP, 1 = MOP ends around the data's latest year, 2 = past MOP. Lease start year stands in for key collection."""
    end = int(start) + years
    return 0 if end > data_year else 1 if end == data_year else 2


def _mop_limits(years):
    plus_prime = load_rules(BTO_FILE).get("mop.plus_prime_years")
    return (f"MOP is {years} years from key collection for standard flats. We only know each block's lease start year, so this status is approximate "
            "(a block can reach MOP months earlier or later). "
            f"Plus and Prime flats have a {plus_prime}-year MOP; the data cannot identify them, and none has been resold yet. "
            "Blocks with no resale yet are not shown. Check HDB for a specific flat.")


def _block_facts(selection):
    sales = load_sales()
    mine = sales[sales.block_id == selection["id"]]
    facts, limits = [], ["Straight-line distances, not walking or travel times."]
    row = load_blocks().set_index("block_id").loc[selection["id"]]
    facts.append(f"Town: {capwords(row.town)}")
    if len(mine):
        latest = sales.sale_month.max()  # the data's latest month, not this block's last sale
        recent = mine[mine.sale_month > latest - pd.DateOffset(years=1)]
        start = int(mine.sort_values("sale_month").lease_commence_year.iloc[-1])
        facts.append(f"Lease started: {start}")
        years = _mop_years()
        code = _mop_code(start, latest.year, years)
        facts.append("MOP (estimated, approximate): " + (f"within the {years}-year MOP", f"MOP ends around {latest.year}", "past MOP")[code])
        if len(recent):
            facts.append(f"Sales in the 12 months to {latest:%Y-%m}: {len(recent)}")
            for flat_type, group in recent.groupby("flat_type"):
                # A median of a handful of sales says little; say how many instead.
                if len(group) >= MIN_FOR_MEDIAN:
                    facts.append(f"{flat_type.title()}: {len(group)} sales, median ${int(group.resale_price.median()):,}")
                else:
                    facts.append(f"{flat_type.title()}: {len(group)} sale{'s' if len(group) != 1 else ''} (too few for a median)")
        else:
            facts.append(f"No sales in the 12 months to {latest:%Y-%m}")
        limits.append("Resale data from data.gov.sg (HDB), Jan 2017 to " + f"{sales.sale_month.max():%Y-%m}"
                      + "; the newest month may be incomplete. Not a valuation.")
        limits.append(_mop_limits(years))
    else:
        facts.append("No resale sales recorded for this block since 2017.")
    school = _nearest(selection["lat"], selection["lng"], "primary_school")
    station = _nearest(selection["lat"], selection["lng"], "mrt")
    if school:
        facts.append(f"Nearest primary school: {school['name']}, {school['km']:.2f} km")
        limits.append("School registration distance (1 km / 2 km) is measured by MOE with OneMap, not by us; check it there.")
    if station:
        facts.append(f"Nearest MRT: {station['name']}, {station['km']:.2f} km")
    return {"facts": facts, "limits": limits, "more_info": blockinfo.block_info(selection["id"], mine),
            **buildings.card_facts(selection["id"], sales, MIN_FOR_MEDIAN)}


def _blocks_within(lat, lng, km):
    blocks = load_blocks()
    blocks = blocks[blocks.lat.notna() & blocks.lng.notna()]
    return int((haversine_km(float(lat), float(lng), blocks.lat.to_numpy(), blocks.lng.to_numpy()) <= km).sum())


def _place_facts(selection):
    kind, lat, lng = selection["kind"], selection["lat"], selection["lng"]
    facts = [{"mrt": "MRT station", "lrt": "LRT station", "primary_school": "Primary school"}[kind]]
    facts.append(f"Blocks with resales since 2017 within 1 km (straight-line): {_blocks_within(lat, lng, 1):,}")
    limits = ["Straight-line distances, counted from our block and place coordinates."]
    if kind == "primary_school":
        limits.append("School registration distance (1 km / 2 km) is measured by MOE with OneMap, not by us; check it there.")
    else:
        facts.append(f"Blocks with resales since 2017 within 500 m (straight-line): {_blocks_within(lat, lng, 0.5):,}")
    return {"facts": facts, "limits": limits}


RADII_KM = (0.5, 1.0, 2.0)


def _upcoming(projects):
    """True for projects HDB lists as upcoming (not on sale yet); older tables have no status column."""
    return projects["status"].eq("upcoming") if "status" in projects else pd.Series(False, index=projects.index)


def around(selection, km):
    """Counts of blocks, stations, schools and BTO sites within km (inclusive, straight-line) of the selection."""
    if km not in RADII_KM:
        raise ValueError("Unsupported radius")
    lat, lng = selection["lat"], selection["lng"]

    def count(frame):
        frame = frame[frame.lat.notna() & frame.lng.notna()]
        return int((haversine_km(lat, lng, frame.lat.to_numpy(), frame.lng.to_numpy()) <= km).sum())

    places = load_places()
    own = selection["id"]
    counts = {"blocks": count(load_blocks()[lambda d: d.block_id != own]),
              "mrt_lrt": count(places[places.kind.isin(["mrt", "lrt"]) & (places.place_id != own)]),
              "primary_schools": count(places[(places.kind == "primary_school") & (places.place_id != own)]),
              "bto_sites": count(load_projects()[lambda d: d.project_id.ne(own) & ~_upcoming(d)]),
              "bto_upcoming": count(load_projects()[lambda d: d.project_id.ne(own) & _upcoming(d)])}
    limits = ["Straight-line circle around the selected place; blocks are those with a resale since 2017."]
    if km in (1.0, 2.0):
        limits.append("MOE's 1 km / 2 km school priority distances are measured by MOE with OneMap, not by this circle.")
    return {"km": km, "counts": counts, "limits": limits}


BORDERLINE_KM = 0.3  # our own allowance: MOE measures to the school boundary, our school points are single points


def schools_nearby(selection, km=2.0):
    """Every primary school within km of the selection, nearest first, tagged with its distance band.

    Bands follow MOE's balloting tiers (within 1 km, 1-2 km). Schools just beyond 2 km by our point are listed as
    borderline because MOE measures from the school boundary. All distances here are straight-line.
    """
    lat, lng = selection["lat"], selection["lng"]
    places = load_places()
    schools = places[(places.kind == "primary_school") & places.lat.notna() & places.lng.notna()
                     & (places.place_id != selection["id"])].copy()
    schools["km"] = haversine_km(lat, lng, schools.lat.to_numpy(), schools.lng.to_numpy())
    schools = schools[schools.km <= km + BORDERLINE_KM].sort_values(["km", "place_id"])
    out = []
    for row in schools.itertuples():
        band = "within 1 km" if row.km <= 1 else "1 to 2 km" if row.km <= km else "borderline"
        out.append({"kind": "primary_school", "id": row.place_id, "label": pretty_name(row.name), "km": round(float(row.km), 2),
                    "band": band, "lat": round(float(row.lat), 5), "lng": round(float(row.lng), 5)})
    return {"km": km, "schools": out, "limits": [
        "Straight-line distances from our coordinates, not MOE's measurement.",
        ("When a school has more applicants than places in the later registration phases, MOE ranks them by citizenship and then by distance (within 1 km, then 1 to 2 km, then beyond 2 km), "
         "measured from the school boundary to the home address, so the bands here are approximate. "
         "A child can apply to any school; being nearby does not guarantee a place. Check MOE's P1 registration page and "
         "OneMap before relying on this."),
        "Borderline: just over 2 km by our point, which may fall within 2 km of the school boundary."]}


METRIC_FLAT_TYPES = ("3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE")
METRIC_MONTHS = 24
METRIC_MIN_SALES = 3
LEASE_YEARS = 99
SQFT_PER_SQM = 10.7639104


@lru_cache(maxsize=8)
def metrics(flat_type):
    """Per block: median resale price of one flat type over the last 24 months (when at least 3 sales) and remaining lease.

    Each row is [median price, sales, lease years, MOP code (see _mop_code), median price per sqm, median price per sq ft]. Remaining lease is the lease left at the block's newest sale, less the months since then, in whole years (rounded down).
    Blocks with fewer sales have no price and are drawn grey. Descriptive only: not a valuation or a forecast.
    """
    if flat_type not in METRIC_FLAT_TYPES:
        raise ValueError("Unsupported flat type")
    sales = load_sales()
    latest = sales.sale_month.max()
    recent = sales[(sales.flat_type == flat_type) & (sales.sale_month > latest - pd.DateOffset(months=METRIC_MONTHS))]
    grouped = recent.groupby("block_id").resale_price.agg(["median", "count"])
    per_sqm = (recent.resale_price / recent.floor_area_sqm).groupby(recent.block_id).median()
    newest = sales.sort_values("sale_month").groupby("block_id").last()
    years = _mop_years()
    blocks = {}
    for block_id, sale in newest.iterrows():
        # Months left at the data's latest month: the lease left at that block's newest sale, less the months since it.
        since = (latest.year - sale.sale_month.year) * 12 + latest.month - sale.sale_month.month
        row = [None, 0, max(0, int(sale.lease_left_months - since) // 12), _mop_code(sale.lease_commence_year, latest.year, years), None, None]
        if block_id in grouped.index:
            row[1] = int(grouped.loc[block_id, "count"])
            if row[1] >= METRIC_MIN_SALES:
                row[0] = int(grouped.loc[block_id, "median"])
                row[4] = int(round(per_sqm.loc[block_id]))  # median price per sqm
                row[5] = int(round(per_sqm.loc[block_id] / SQFT_PER_SQM))  # the same median per sq ft
        blocks[block_id] = row
    return {"flat_type": flat_type, "window_months": METRIC_MONTHS, "min_sales": METRIC_MIN_SALES,
            "as_of": f"{latest:%Y-%m}", "blocks": blocks, "mop_years": years,
            "mop_rule": load_rules(BTO_FILE).cite("mop.standard_years"), "mop_limits": _mop_limits(years),
            "limits": [(f"Median of the last {METRIC_MONTHS} months of recorded resales (data.gov.sg, to {latest:%Y-%m}) for one flat type, "
                        f"only where a block has at least {METRIC_MIN_SALES} sales; other blocks are grey."),
                       "Per sqm and per sq ft: the median of each sale's price divided by its recorded floor area (1 sqm = 10.7639 sq ft).",
                       "Flat size, floor and renovation differ within a block, so this is not a valuation or a forecast.",
                       "Remaining lease is in whole years (rounded down), from the lease left at each block's newest recorded sale."]}


def _built(name):
    """The day a data file was built, from its modification time (kept by the image build)."""
    return date.fromtimestamp((ROOT / "data/clean" / name).stat().st_mtime).isoformat()


def _rules_date(path):
    found = re.findall(r"as_of: (\d{4}-\d{2}-\d{2})", path.read_text())
    return max(found) if found else None


def data_freshness():
    """What each part of the page is built from and how recent it is, for the page footer."""
    sales = load_sales()
    latest = sales.sale_month.max()
    return [
        {"label": "Resale prices", "as_of": f"sales to {latest:%Y-%m}, data built {_built('resale.parquet')}",
         "source": "HDB via data.gov.sg"},
        {"label": "HDB rules and grants", "as_of": f"rules dated {_rules_date(RULES_DIR / '2026-10.yaml')}",
         "source": "hdb.gov.sg, each rule with its own date"},
        {"label": "BTO launches", "as_of": f"rules dated {_rules_date(RULES_DIR / 'bto' / '2026-10.yaml')}, data built {_built('bto_projects.parquet')}",
         "source": "HDB launch pages"},
        {"label": "Block locations", "as_of": f"built {_built('blocks.parquet')}", "source": "OneMap geocoding"},
        {"label": "3D outlines and floors", "as_of": f"built {_built('buildings.geojson')}", "source": "HDB building outlines and property information"},
        {"label": "Bus stops and supermarkets", "as_of": f"downloaded {load_amenities().as_of.iloc[0]}", "source": "OpenStreetMap"},
        {"label": "Walking paths", "as_of": f"built {_built('walk_graph.npz')}", "source": "OpenStreetMap extract of 25 Oct 2026"},
        {"label": "Map tiles", "as_of": "live", "source": "OpenStreetMap"},
    ]
