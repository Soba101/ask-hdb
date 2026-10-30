"""Map points for a tool result, found by code (never by the model) from ids in the arguments and the result.

Blocks come from blocks.parquet, MRT and school places from places.parquet and BTO sites from bto_projects.parquet.
BTO sites are approximate; the point says so. Blocks without coordinates are left out.
"""

import math
from string import capwords

from ask_hdb.bto.queries import load_projects
from ask_hdb.geo.loaders import load_blocks, load_places
from ask_hdb.geo.names import pretty_name

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
            add("block", key, f"Blk {row.block} {capwords(row.street_name)}", row.lat, row.lng, role)

    def project(key, role):
        if key in projects.index:
            row = projects.loc[key]
            upcoming = row.get("status") == "upcoming"
            add("bto", key, f"{row['name']} (upcoming BTO, not on sale yet)" if upcoming else f"{row['name']} (BTO)", row.lat, row.lng, role,
                "approximate site")

    if isinstance(args.get("block_id"), str):
        block(args["block_id"], "origin")
    if isinstance(args.get("project_id"), str):
        project(args["project_id"], "origin")
    for item in _walk(result):
        if isinstance(item.get("block_id"), str):
            block(item["block_id"], "result")
        if isinstance(item.get("project_id"), str):
            project(item["project_id"], "result")
        for found_item in item.get("candidates", []) if isinstance(item.get("candidates"), list) else []:
            if isinstance(found_item, dict) and {"kind", "id", "label", "lat", "lng"} <= found_item.keys():
                add(found_item["kind"], found_item["id"], found_item["label"], found_item["lat"], found_item["lng"],
                    "result", "approximate site" if found_item["kind"] == "bto" else None)
        key = item.get("place_id")
        if isinstance(key, str) and key in places.index:
            row = places.loc[key]
            kind = {"mrt": "MRT", "lrt": "LRT"}.get(row.kind, row.kind.replace("_", " "))
            add(row.kind, key, f"{pretty_name(row['name'])} ({kind})",
                row.lat, row.lng, "result")
    return list(found.values())[:MAX_POINTS]


def map_actions(points):
    """What the map should do for these points: highlight them and fly to them (a bounding box [w, s, e, n])."""
    if not points:
        return []
    lngs, lats = [p["lng"] for p in points], [p["lat"] for p in points]
    return [{"op": "highlight", "points": points},
            {"op": "fly_to", "bbox": [min(lngs), min(lats), max(lngs), max(lats)]}]
