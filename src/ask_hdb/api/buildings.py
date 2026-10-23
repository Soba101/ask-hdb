"""Offline building data, historical storey medians and illustrative solar geometry."""

import json
import re
from datetime import date as Date
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ask_hdb import sun
from ask_hdb.geo.loaders import ROOT

PATH = ROOT / "data/clean/buildings.geojson"
router = APIRouter()


@lru_cache(maxsize=1)
def features():
    # Exceptions are not cached: a missing file can be built without restarting the app.
    return json.loads(PATH.read_text())


@lru_cache(maxsize=1)
def index():
    return {f["properties"]["block_id"]: f["properties"] for f in features()["features"]}


def metadata(key):
    try:
        return index().get(key, {})
    except FileNotFoundError:
        return {}  # old deployments still have usable block cards


def storey_prices(sales, key, minimum):
    """Pool recorded flat types, but never invent a floor within a reported storey range."""
    if sales.empty or not {"storey_low", "storey_high"}.issubset(sales.columns):
        return []
    latest = sales.sale_month.max()
    recent = sales[(sales.block_id == key) & (sales.sale_month > latest - pd.DateOffset(months=24))]
    # Older wide bands cannot be allocated honestly to individual three-storey bands.
    recent = recent[(recent.storey_low % 3 == 1) & (recent.storey_high == recent.storey_low + 2)]
    out = []
    for (low, high), group in recent.groupby(["storey_low", "storey_high"]):
        if len(group) >= minimum:
            out.append({"storey_low": int(low), "storey_high": int(high), "label": f"{int(low)}–{int(high)}",
                        "sales": len(group), "median_price": int(group.resale_price.median())})
    return out


def card_facts(key, sales, minimum):
    building = metadata(key)
    return {**{name: building.get(name) for name in ("floors", "height_source", "facing_label")},
            "storey_prices": storey_prices(sales, key, minimum),
            "storey_prices_as_of": f"{sales.sale_month.max():%Y-%m}" if not sales.empty else None,
            "storey_prices_limits": (f"Recorded resale medians by storey band over the last 24 months of data; "
                                     f"only bands with at least {minimum} sales. All flat types pooled; "
                                     "size, type and condition differ. Wider storey ranges are omitted. "
                                     "No unit-level price or facing; not a valuation or a forecast.")}


def parse_date(value):
    if value is None:
        return datetime.now(ZoneInfo("Asia/Singapore")).date()
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return Date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Use a valid date in YYYY-MM-DD format.") from None


@router.get("/map/buildings")
def map_buildings():
    try:
        return JSONResponse(features(), headers={"Cache-Control": "public, max-age=3600"})
    except FileNotFoundError:
        raise HTTPException(404, "Building outlines are unavailable; run scripts/build_buildings.py.") from None


@router.get("/sun")
def sun_positions(date: str | None = None):
    day = parse_date(date)
    return {"date": day.isoformat(), "timezone": "+08:00", "positions": sun.positions(day), "limits": sun.LIMITS}


@router.get("/sun/block/{key}")
def block_sun(key: str, date: str | None = None):
    from ask_hdb.api import mapdata

    day = parse_date(date)
    if mapdata.resolve({"kind": "block", "id": key}) is None:
        raise HTTPException(404, "Unknown block.")
    building = metadata(key)
    if not building:
        raise HTTPException(404, "No building outline or facing is available for this block.")
    return {"block_id": key, "date": day.isoformat(), "timezone": "+08:00",
            "facades": sun.facade_day(day, building["facing"]), "limits": sun.LIMITS}
