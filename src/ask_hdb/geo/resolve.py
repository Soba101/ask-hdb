"""Turn a place named in words into ids, by code. The model never guesses an id or a coordinate.

Order: a block ("Blk 227 Bishan St 23", "227 Bishan"), then MRT/LRT stations, primary schools and BTO projects by name,
then a town name (a town is not a point, so no candidate is returned for it).
"""

from functools import lru_cache
from string import capwords

import pandas as pd

from ask_hdb.bto.queries import load_projects
from ask_hdb.geo.loaders import load_blocks, load_places
from ask_hdb.geo.names import pretty_name
from ask_hdb.geo.streets import normalize_street

MAX_CANDIDATES = 5
STOP = {"MRT", "LRT", "STATION", "STN", "PRIMARY", "SCHOOL", "THE", "OF", "BTO", "PROJECT"}
KIND_WORDS = {"MRT": ("mrt", "lrt"), "LRT": ("mrt", "lrt"), "STATION": ("mrt", "lrt"), "STN": ("mrt", "lrt"),
              "PRIMARY": ("primary_school",), "SCHOOL": ("primary_school",)}


def _ok(value):
    return pd.notna(value)


def _candidate(kind, key, label, lat, lng, **extra):
    return {"kind": kind, "id": key, "label": label, "lat": round(float(lat), 5), "lng": round(float(lng), 5), **extra}


@lru_cache(maxsize=1)
def _block_index():
    blocks = load_blocks()
    blocks = blocks[blocks.lat.notna() & blocks.lng.notna()]
    return [(str(r.block).upper(), normalize_street(r.street_name), r) for r in blocks.itertuples()]


def _block_candidates(tokens):
    if not tokens or not (tokens[0][0].isdigit() and tokens[0].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").isdigit()):
        return None
    number, street = tokens[0], " ".join(tokens[1:])
    same = [(s, r) for n, s, r in _block_index() if n == number]
    exact = [r for s, r in same if street and s == street]
    partial = [r for s, r in same if street and street in s] if not exact else []
    found = exact or partial or ([r for _, r in same] if not street else [])
    return [_candidate("block", r.block_id, f"Blk {r.block} {capwords(r.street_name)}", r.lat, r.lng, town=capwords(r.town))
            for r in found]


def _core(words):
    return [w for w in words if w not in STOP]


def _named_candidates(tokens):
    core = _core(tokens)
    if not core:
        return []
    kinds = {k for w in tokens for k in KIND_WORDS.get(w, ())}
    found, exact = [], []
    places = load_places()
    for r in places[places.lat.notna() & places.lng.notna()].itertuples():
        if kinds and r.kind not in kinds:
            continue
        name = _core(normalize_street(r.name).split())
        if name == core or (len(core) >= 1 and set(core) <= set(name)):
            label = {"mrt": "MRT", "lrt": "LRT"}.get(r.kind, "primary school")
            item = _candidate(r.kind, r.place_id, f"{pretty_name(r.name)} ({label})", r.lat, r.lng)
            (exact if name == core else found).append(item)
    if not kinds or "BTO" in tokens or "PROJECT" in tokens:
        projects = load_projects()
        for r in projects[projects.lat.notna() & projects.lng.notna()].itertuples():
            name = _core(normalize_street(r.name).split())
            if name == core or set(core) <= set(name):
                item = _candidate("bto", r.project_id, f"{r.name} (BTO, approximate site)", r.lat, r.lng)
                (exact if name == core else found).append(item)
    return exact or found


def resolve_place(text):
    """Return {status: ok|ambiguous|not_found|town, candidates: [...]} for a place named in words."""
    tokens = normalize_street(str(text)).split()
    if tokens and tokens[0] == "BLOCK":
        tokens = tokens[1:]
    if not tokens:
        return {"status": "not_found", "candidates": [], "note": "No place name was given."}
    towns = {normalize_street(t) for t in load_blocks().town.dropna().unique()}
    if " ".join(tokens) in towns:  # "Bishan" alone means the estate, not the station that shares its name
        return {"status": "town", "candidates": [],
                "note": "A town is an area, not a point. Ask for a block, an MRT station, a school or a BTO project."}
    found = _block_candidates(tokens) or _named_candidates(tokens)
    if not found:
        return {"status": "not_found", "candidates": [], "note": "No block, station, school or BTO project matches."}
    status = "ok" if len(found) == 1 else "ambiguous"
    out = {"status": status, "candidates": found[:MAX_CANDIDATES], "n_matches": len(found)}
    if status == "ambiguous":
        out["note"] = "Several places match; ask the user which one. Do not pick one yourself."
    return out
