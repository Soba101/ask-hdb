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
    if kind is not None:
        frame = frame.loc[frame.block_id.isin(block_ids_near(kind, km))]
    return frame, values, kind is not None


def nearest_places(block_id, kind, n=3):
    return {"places": nearest(load_blocks(), load_places(), block_id, kind, n), "note": NOTE}
