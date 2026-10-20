"""Accept coordinates only when both address parts agree."""

import math

from ask_hdb.geo.streets import normalize_street


def empty_record(status: str, query: str) -> dict:
    return {"status": status, "lat": None, "lng": None, "postal": None, "road_name": None, "query": query}


def _metres(a, b):
    # Equirectangular approximation is fine at this scale.
    dlat = (float(a["LATITUDE"]) - float(b["LATITUDE"])) * 111_000
    dlng = (float(a["LONGITUDE"]) - float(b["LONGITUDE"])) * 111_000 * math.cos(math.radians(1.35))
    return math.hypot(dlat, dlng)


def _close_together(rows, limit=150):
    return all(_metres(rows[0], other) <= limit for other in rows[1:])


def match_result(block: str, street: str, body: dict) -> dict:
    query = f"{block} {street}"
    candidates = [row for row in body.get("results", [])
                  if str(row.get("BLK_NO", "")).strip().casefold() == block.strip().casefold()]
    matches = [row for row in candidates
               if normalize_street(str(row.get("ROAD_NAME", ""))) == normalize_street(street)]
    status = "not_found"
    row = None
    if len(matches) == 1:
        status, row = "found", matches[0]
    elif len(matches) > 1 and _close_together(matches):
        # OneMap often lists the same block twice (e.g. two postal codes); take the first.
        status, row = "found", matches[0]
    elif not matches and len(candidates) == 1:
        status, row = "uncertain", candidates[0]
    record = empty_record(status, query)
    if row is not None:
        lat, lng = float(row["LATITUDE"]), float(row["LONGITUDE"])
        if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90
                and -180 <= lng <= 180):
            raise ValueError("Invalid coordinates")
        record.update(lat=lat, lng=lng, postal=row.get("POSTAL"), road_name=row.get("ROAD_NAME"))
    return record
