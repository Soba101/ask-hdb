"""Data for the map-first page: every block and place as GeoJSON, an info card per selection, and the selection
context sent to the agent. Everything is computed by code from the clean tables; the model writes none of it.

Ids from the browser are never trusted: a selection is only used when the id exists in the tables.
"""

import math
from functools import lru_cache
from string import capwords

import pandas as pd

from ask_hdb.bto.queries import load_projects
from ask_hdb.geo.distance import haversine_km, nearest_to_point
from ask_hdb.geo.loaders import load_blocks, load_places
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
        label = f"{capwords(row.name)} ({kind})"
        out.append(_feature(row.kind, row.place_id, label, row.lat, row.lng))
    for row in load_projects().itertuples():
        if not (_ok(row.lat) and _ok(row.lng)):
            continue  # a BTO project whose site was not found has no point
        out.append(_feature("bto", row.project_id, f"{row.name} (BTO, approximate site)", row.lat, row.lng,
                            town=row.town if isinstance(row.town, str) else ""))
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
        table, label = load_places().set_index("place_id"), lambda r: capwords(r["name"])
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
    return {"name": capwords(got[0]["name"]), "km": round(got[0]["km"], 2)} if got else None


def card(selection):
    """Facts for the selected place, with the sources and the limits that go with them."""
    kind = selection["kind"]
    base = {"kind": kind, "id": selection["id"], "label": selection["label"]}
    if kind == "block":
        return {**base, **_block_facts(selection)}
    if kind == "bto":
        row = load_projects().set_index("project_id").loc[selection["id"]]
        return {**base, "facts": [f"Category: {row.category}", f"Units: {int(row.units)}",
                                  f"Waiting time: about {int(row.wait_months)} months"],
                "limits": ["BTO sites are approximate; prices are indicative launch ranges, before grants."]}
    return {**base, **_place_facts(selection)}


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
    else:
        facts.append("No resale sales recorded for this block since 2017.")
    school = _nearest(selection["lat"], selection["lng"], "primary_school")
    station = _nearest(selection["lat"], selection["lng"], "mrt")
    if school:
        facts.append(f"Nearest primary school: {school['name']}, {school['km']:.2f} km")
        limits.append("School registration distance (1 km / 2 km) is measured by MOE with OneMap, not by us; check it there.")
    if station:
        facts.append(f"Nearest MRT: {station['name']}, {station['km']:.2f} km")
    return {"facts": facts, "limits": limits}


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
              "bto_sites": count(load_projects()[lambda d: d.project_id != own])}
    limits = ["Straight-line circle around the selected place; blocks are those with a resale since 2017."]
    if km in (1.0, 2.0):
        limits.append("MOE's 1 km / 2 km school priority distances are measured by MOE with OneMap, not by this circle.")
    return {"km": km, "counts": counts, "limits": limits}
