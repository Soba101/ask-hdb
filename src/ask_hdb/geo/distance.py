"""Straight-line distances for locally stored coordinates."""

import numpy as np
import pandas as pd

KINDS = {"mrt", "primary_school"}


def haversine_km(lat1, lng1, lat2, lng2):
    """Accept scalars or broadcastable arrays, with coordinates in degrees."""
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2
    a = a + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _coordinates(frame):
    values = frame[["lat", "lng"]].apply(pd.to_numeric, errors="coerce")
    return (np.isfinite(values).all(axis=1)
            & values.lat.between(-90, 90) & values.lng.between(-180, 180))


def _places(places, kind):
    if kind not in KINDS:
        raise ValueError(f"Unknown kind: {kind}")
    rows = places.loc[places.kind.eq(kind)]
    if rows.empty:
        raise ValueError(f"No places for kind: {kind}")
    # Ungeocoded schools must never turn into zero-distance matches.
    rows = rows.loc[_coordinates(rows)].copy()
    if rows.empty:
        raise ValueError(f"Missing coordinates for kind: {kind}")
    return rows.astype({"lat": float, "lng": float})


def nearest(blocks_df, places_df, block_id, kind, n=3):
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n must be a positive integer")
    rows = blocks_df.loc[blocks_df.block_id.eq(block_id)]
    if rows.empty:
        raise ValueError(f"Unknown block_id: {block_id}")
    if not _coordinates(rows).all():
        raise ValueError(f"Missing coordinates for block_id: {block_id}")
    block = rows.iloc[0]
    places = _places(places_df, kind)
    places["km"] = haversine_km(float(block.lat), float(block.lng),
                                places.lat.to_numpy(), places.lng.to_numpy())
    places = places.sort_values(["km", "place_id"]).head(n)
    return [{"place_id": row.place_id, "name": row["name"], "km": float(row.km),
             "kind": kind, "method": "straight-line"} for _, row in places.iterrows()]


def within_km(blocks_df, places_df, kind, km):
    if not np.isfinite(km) or km < 0:
        raise ValueError("km must be a finite nonnegative number")
    places = _places(places_df, kind)
    blocks = blocks_df.loc[_coordinates(blocks_df)].astype({"lat": float, "lng": float})
    result = set()
    # Bound temporary memory while doing each chunk in compiled numpy operations.
    for start in range(0, len(blocks), 1024):
        chunk = blocks.iloc[start:start + 1024]
        distances = haversine_km(chunk.lat.to_numpy()[:, None], chunk.lng.to_numpy()[:, None],
                                 places.lat.to_numpy(), places.lng.to_numpy())
        result.update(chunk.loc[(distances <= km).any(axis=1), "block_id"])
    return result
