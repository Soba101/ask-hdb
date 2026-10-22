"""Map points for a tool result, found by code (never by the model) from ids in the arguments and the result.

Blocks come from blocks.parquet, MRT and school places from places.parquet and BTO sites from bto_projects.parquet.
BTO sites are approximate; the point says so. Blocks without coordinates are left out.
"""

import math

from ask_hdb.bto.queries import load_projects
from ask_hdb.geo.loaders import load_blocks, load_places

MAX_POINTS = 40


def _ok(value):
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def map_points(args, result):
    """Return [{kind, id, label, lat, lng, role}] for the places a tool call is about."""
    blocks = load_blocks().set_index("block_id")
    places = load_places().set_index("place_id")
    projects = load_projects().set_index("project_id")
    found = {}

    def add(kind, key, label, lat, lng, role, note=None):
        if key in found or not (_ok(lat) and _ok(lng)):
            return
        point = {"kind": kind, "id": key, "label": label, "lat": round(float(lat), 5), "lng": round(float(lng), 5),
                 "role": role}
        if note:
            point["note"] = note
        found[key] = point

    def block(key, role):
        if key in blocks.index:
            row = blocks.loc[key]
            add("block", key, f"Blk {row.block} {row.street_name.title()}", row.lat, row.lng, role)

    def project(key, role):
        if key in projects.index:
            row = projects.loc[key]
            add("bto", key, f"{row['name']} (BTO)", row.lat, row.lng, role, "approximate site")

    if isinstance(args.get("block_id"), str):
        block(args["block_id"], "origin")
    if isinstance(args.get("project_id"), str):
        project(args["project_id"], "origin")
    for item in _walk(result):
        if isinstance(item.get("block_id"), str):
            block(item["block_id"], "result")
        if isinstance(item.get("project_id"), str):
            project(item["project_id"], "result")
        key = item.get("place_id")
        if isinstance(key, str) and key in places.index:
            row = places.loc[key]
            add(row.kind, key, f"{row['name'].title()} ({'MRT' if row.kind == 'mrt' else row.kind.replace('_', ' ')})",
                row.lat, row.lng, "result")
    return list(found.values())[:MAX_POINTS]
