"""Distance adapters for tools; sales functions keep their existing inputs."""

from ask_hdb.bto.queries import load_projects
from ask_hdb.geo.distance import nearest, nearest_to_point, within_km
from ask_hdb.geo.loaders import load_blocks, load_places

NOTE = "Straight-line distance; HDB's official school-distance check uses OneMap"


def block_ids_near(kind, km):
    return within_km(load_blocks(), load_places(), kind, km)


def validate_near(values):
    kind, km = values["near_kind"], values["near_km"]
    if (kind is None) != (km is None):
        missing = "near_kind" if kind is None else "near_km"
        raise ValueError(f"Missing {missing}; supply both near_kind and near_km")


def filter_sales(frame, values):
    validate_near(values)
    values = values.copy()
    kind, km = values.pop("near_kind"), values.pop("near_km")
    unlocated = frame.iloc[0:0]
    if kind is not None:
        # Sales in blocks with no coordinates cannot be placed; keep them so the caller can count them
        # under the same other filters (town, months, ...) and tell the user.
        unlocated = frame.loc[~frame.block_id.isin(set(load_blocks().block_id))]
        frame = frame.loc[frame.block_id.isin(block_ids_near(kind, km))]
    return frame, values, kind is not None, unlocated


ORIGIN_PREFIXES = ("bto_", "mrt_", "lrt_", "school_")


def _origin_point(origin_id):
    """Coordinates of a BTO site or a station/school used as the starting point (never itself in the results)."""
    if origin_id.startswith("bto_"):
        rows = load_projects().loc[lambda d: d.project_id.eq(origin_id)]
        approx = " (approximate site)"
    else:
        rows = load_places().loc[lambda d: d.place_id.eq(origin_id)]
        approx = ""
    if rows.empty:
        raise ValueError(f"Unknown id: {origin_id}")
    row = rows.iloc[0]
    if row.isna()[["lat", "lng"]].any():
        raise ValueError(f"No coordinates for {origin_id}")
    return float(row.lat), float(row.lng), approx


def _nearest_from_point(origin_id, kind, n, within):
    lat, lng, approx = _origin_point(origin_id)
    places = load_places()
    every = [p for p in nearest_to_point(lat, lng, places, kind, max(len(places), 1)) if p["place_id"] != origin_id]
    if within is None:
        return {"places": every[:n], "note": NOTE + approx}
    found = [p for p in every if p["km"] <= within]
    return {"places": found[:n], "n_within": len(found), "within_km": within, "note": NOTE + approx}


def nearest_places(block_id, kind, n=3, within_km=None):
    if block_id.startswith(ORIGIN_PREFIXES):
        return _nearest_from_point(block_id, kind, n, within_km)
    if within_km is None:
        return {"places": nearest(load_blocks(), load_places(), block_id, kind, n), "note": NOTE}
    # Count in code, inclusive, over every place of this kind, so the model never counts list items.
    places = load_places()
    found = [p for p in nearest(load_blocks(), places, block_id, kind, max(len(places), 1))
             if p["km"] <= within_km]
    # Only the nearest n are listed so results stay small on 8k-context servers; n_within counts all.
    return {"places": found[:n], "n_within": len(found), "within_km": within_km, "note": NOTE}
