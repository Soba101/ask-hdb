"""Nearest supermarkets, MRT/LRT stations and bus stops, and walking routes to them (OneMap)."""

import threading
from collections import OrderedDict
from functools import lru_cache

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ask_hdb.api import mapdata
from ask_hdb.geo import walk
from ask_hdb.geo.client import OneMap, load_credentials
from ask_hdb.geo.distance import haversine_km
from ask_hdb.geo.loaders import ROOT, load_amenities, load_places
from ask_hdb.geo.names import pretty_name
from ask_hdb.geo.route import RouteError

router = APIRouter()
TYPES = {"supermarket": "supermarket", "bus": "bus_stop"}
STATUS = {"no_credentials": 200, "no_route": 404, "quota": 429, "unavailable": 502}
MESSAGES = {
    "no_credentials": "Walking directions need OneMap credentials in .env.",
    "no_route": "OneMap found no walking route between these two places.",
    "quota": "Too many route requests right now. Please try again in a minute.",
    "unavailable": "Walking directions are not available right now.",
}
OSM_LIMIT = "Straight-line distance. OpenStreetMap data may be incomplete or out of date."
CACHE_SIZE = 256
cache, cache_lock = OrderedDict(), threading.Lock()


class Caps:
    """A visitor limit and a global cap in front of the shared OneMap account (the /chat Limits class, other numbers)."""

    def __init__(self):
        from ask_hdb.api import Limits
        self.visitor, self.everyone = Limits(per_minute=10), Limits(per_minute=100)

    def allow(self, who):
        return self.visitor.allow(who) and self.everyone.allow("all")


@lru_cache(maxsize=1)
def caps():
    return Caps()


@lru_cache(maxsize=1)
def onemap():
    return OneMap(httpx.Client(), load_credentials())


@lru_cache(maxsize=1)
def osm_router():
    """Our own walking router over OpenStreetMap paths (scripts/build_walk_graph.py), or None when its file is missing."""
    path = ROOT / "data/clean/walk_graph.npz"
    return walk.Router(path) if path.exists() else None


def osm_route(start, end):
    """A route from our own graph when OneMap cannot answer. None when there is no graph, no path, or a path so much longer
    than the straight line that it more likely shows a gap in the map than a real detour (2 times plus 100 m; tuned on the
    60 pairs of docs/routing-ab.md, so the real gain is probably a little smaller)."""
    router = osm_router()
    found = router.route(start, end) if router else None
    if found is None or found["distance_m"] > 2 * walk.metres(*start, *end) + 100:
        return None
    return {key: found[key] for key in ("distance_m", "duration_s", "steps", "line")}


def _rank(selection, rows, n):
    km = haversine_km(selection["lat"], selection["lng"], rows.lat.to_numpy(), rows.lng.to_numpy())
    rows = rows.assign(km=km).nsmallest(n, "km")
    return [{"id": r.id, "name": r.name, "ref": r.ref if isinstance(r.ref, str) else None,
             "lat": float(r.lat), "lng": float(r.lng), "km": round(float(r.km), 2)} for r in rows.itertuples()]


@router.get("/nearby/{kind}/{key}")
def nearby(kind: str, key: str, type: str, n: int = 3):
    selection = mapdata.resolve({"kind": kind, "id": key})
    if selection is None:
        raise HTTPException(404, "Unknown place.")
    if type not in (*TYPES, "mrt"):
        raise HTTPException(422, "type must be supermarket, mrt or bus.")
    n = max(1, min(n, 5))
    if type == "mrt":
        places = load_places()
        places = places[places.kind.isin(["mrt", "lrt"])]
        rows = places.rename(columns={"place_id": "id"}).assign(ref=None)
        rows["name"] = rows["name"].map(pretty_name)
        source, limits = "LTA MRT station exits (data.gov.sg)", ["Straight-line distance to the station centre."]
    else:
        amenities = load_amenities()
        rows = amenities[amenities.kind == TYPES[type]]
        source, limits = rows.source.iloc[0], [OSM_LIMIT]
    return {"type": type, "items": _rank(selection, rows, n), "source": source, "limits": limits,
            "as_of": str(load_amenities().as_of.iloc[0])}


def _destination(selection, target):
    """(lat, lng, name) of the target. A station is reached through its exit nearest to the start."""
    amenities = load_amenities()
    hit = amenities[amenities.id == target]
    if not hit.empty:
        row = hit.iloc[0]
        return float(row.lat), float(row.lng), row["name"]
    places = load_places()
    station = places[(places.place_id == target) & places.kind.isin(["mrt", "lrt"])]
    if station.empty:
        return None
    exits = amenities[(amenities.kind == "mrt_exit") & (amenities.place_id == target)]
    name = pretty_name(station.iloc[0]["name"])
    if exits.empty:
        return float(station.iloc[0].lat), float(station.iloc[0].lng), name
    km = haversine_km(selection["lat"], selection["lng"], exits.lat.to_numpy(), exits.lng.to_numpy())
    best = exits.iloc[int(km.argmin())]
    return float(best.lat), float(best.lng), f"{name} (nearest exit)"


def _reply(code):
    return JSONResponse({"error": code, "message": MESSAGES[code]}, status_code=STATUS[code])


@router.get("/route/{kind}/{key}")
def route(kind: str, key: str, to: str, request: Request):
    selection = mapdata.resolve({"kind": kind, "id": key})
    goal = _destination(selection, to) if selection else None
    if goal is None:
        raise HTTPException(404, "Unknown place.")  # the client never sends coordinates, only ids we know
    cache_key = (kind, key, to)
    with cache_lock:
        if cache_key in cache:
            cache.move_to_end(cache_key)
            hit = cache[cache_key]
            return _reply("no_route") if hit == "no_route" else hit
    if not caps().allow(request.client.host if request.client else "unknown"):
        return _reply("quota")
    try:
        found = onemap().route((selection["lat"], selection["lng"]), goal[:2])
    except RouteError as error:
        if error.code == "no_route":
            _remember(cache_key, "no_route")
        elif (backup := osm_route((selection["lat"], selection["lng"]), goal[:2])):
            # OneMap is out of reach (no login, quota or outage): answer from OpenStreetMap paths, and do not cache it.
            return {**backup, "to": goal[2], "source": "Route: OpenStreetMap paths, walking estimate",
                    "limits": [("Walking time and distance are estimates from OpenStreetMap paths. They can miss void decks and "
                                "covered links, so a real walk may be shorter.")]}
        return _reply(error.code)
    body = {**found, "to": goal[2], "source": "Route: OneMap (SLA), walking estimate",
            "limits": ["Walking time and distance are estimates from OneMap and can differ from a real walk."]}
    _remember(cache_key, body)
    return body


def _remember(key, value):
    with cache_lock:
        cache[key] = value
        while len(cache) > CACHE_SIZE:
            cache.popitem(last=False)
