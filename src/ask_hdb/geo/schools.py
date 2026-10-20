"""Resume postal-code school lookups using the shared polite OneMap client."""

import math
import os
import tempfile
from pathlib import Path

from ask_hdb.geo.client import GeocodeError, StopGeocoding
from ask_hdb.geo.matching import empty_record
from ask_hdb.geo.storage import load_cache, save_cache


def match_school(postal, body):
    record = empty_record("not_found", postal)
    for row in body["results"]:
        if str(row.get("POSTAL", "")).strip() != postal:
            continue
        lat, lng = float(row["LATITUDE"]), float(row["LONGITUDE"])
        if not (math.isfinite(lat) and math.isfinite(lng)
                and -90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError("Invalid school coordinates")
        record.update(status="found", lat=lat, lng=lng, postal=postal)
        break
    return record


def write_places(path, places, cache):
    places = places.copy()
    for index, row in places.loc[places.kind.eq("primary_school")].iterrows():
        record = cache.get(str(row.postal_code))
        if record and record["status"] == "found":
            places.loc[index, ["lat", "lng"]] = [record["lat"], record["lng"]]
    # Keep a readable parquet file even if this process is interrupted.
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".parquet")
    os.close(fd)
    try:
        places.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def geocode_schools(places, api, directory, checkpoint=25, notify=print):
    if checkpoint < 1:
        raise ValueError("checkpoint must be positive")
    path = directory / "school_geocode_cache.json"
    cache = load_cache(path)
    complete, processed, errors = True, 0, 0
    try:
        schools = places.loc[places.kind.eq("primary_school")]
        for postal in sorted(set(schools.postal_code.astype(str))):
            if cache.get(postal, {}).get("status") in {"found", "not_found"}:
                continue
            try:
                record = match_school(postal, api.search(postal))
            except StopGeocoding as exc:
                notify(str(exc))
                complete = False
                break
            except (GeocodeError, ValueError, KeyError, TypeError, OverflowError):
                record = empty_record("error", postal)
            cache[postal] = record
            processed += 1
            errors = errors + 1 if record["status"] == "error" else 0
            if processed % checkpoint == 0:
                save_cache(path, cache)
                write_places(directory / "places.parquet", places, cache)
            if errors >= 10:
                notify("Stopped after repeated OneMap errors; rerun to retry.")
                complete = False
                break
    except KeyboardInterrupt:
        notify("Interrupted. School geocode progress saved.")
        complete = False
    finally:
        save_cache(path, cache)
        write_places(directory / "places.parquet", places, cache)
    return complete
