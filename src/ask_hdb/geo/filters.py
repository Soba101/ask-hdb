"""Distance adapters for tools; sales functions keep their existing inputs."""

from ask_hdb.geo.distance import nearest, within_km
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


def nearest_places(block_id, kind, n=3, within_km=None):
    if within_km is None:
        return {"places": nearest(load_blocks(), load_places(), block_id, kind, n), "note": NOTE}
    # Count in code, inclusive, over every place of this kind, so the model never counts list items.
    places = load_places()
    found = [p for p in nearest(load_blocks(), places, block_id, kind, max(len(places), 1))
             if p["km"] <= within_km]
    return {"places": found, "n_within": len(found), "within_km": within_km, "note": NOTE}
