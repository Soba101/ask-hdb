"""Resume block geocoding without repeating completed lookups."""

from ask_hdb.geo.client import GeocodeError, StopGeocoding
from ask_hdb.geo.matching import empty_record, match_result
from ask_hdb.geo.storage import load_cache, save_cache, write_outputs

TERMINAL = {"found", "uncertain", "not_found"}


def geocode(blocks, api, directory, checkpoint=25, notify=print) -> bool:
    if checkpoint < 1:
        raise ValueError("checkpoint must be positive")
    path = directory / "geocode_cache.json"
    cache = load_cache(path)
    errors = processed = 0
    complete = True
    try:
        for block in blocks.to_dict("records"):
            key = block["block_id"]
            if cache.get(key, {}).get("status") in TERMINAL:
                continue
            query = f"{block['block']} {block['street_name']}"
            try:
                body = api.search(query)
                record = match_result(block["block"], block["street_name"], body)
            except StopGeocoding as exc:
                cache[key] = empty_record("error", query)
                notify(str(exc))
                complete = False
                break
            except (GeocodeError, ValueError, KeyError, TypeError, OverflowError):
                # Store no exception text: remote responses may contain secrets.
                record = empty_record("error", query)
            cache[key] = record
            processed += 1
            errors = errors + 1 if record["status"] == "error" else 0
            if processed % checkpoint == 0:
                save_cache(path, cache)
            if errors >= 10:
                notify("Stopped after 10 consecutive OneMap errors. Cache saved; rerun to retry.")
                complete = False
                break
    except KeyboardInterrupt:
        notify("Interrupted. Geocode progress saved.")
        complete = False
    finally:
        save_cache(path, cache)
        write_outputs(directory, blocks, cache)
    return complete
