"""Reading a OneMap walking route: the error type, the polyline decoder and the response parser."""

import re


class RouteError(Exception):
    """code is one of no_credentials, no_route, quota, unavailable."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def decode_polyline(text, precision=5):
    """Standard encoded polyline (OneMap uses precision 5) to [[lng, lat], ...]."""
    points, index, lat, lng = [], 0, 0, 0
    scale = 10 ** precision
    while index < len(text):
        for axis in (0, 1):
            shift = result = 0
            while True:
                byte = ord(text[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lng += delta
        points.append([lng / scale, lat / scale])
    return points


def _step(row):
    # Rows are [direction, road, metres, "lat,lng", seconds, ..., text]: take the last wordy string as the text.
    text = next((c for c in reversed(row[4:]) if isinstance(c, str) and len(c) > 3 and re.search("[A-Za-z]", c)), None)
    road = row[1] if isinstance(row[1], str) else ""
    return {"text": text or f"{row[0]} {road}".strip(), "road": road, "distance_m": round(float(row[2]))}


def parse_route(body):
    """{distance_m, duration_s, steps, line} from a OneMap route body, or RouteError('unavailable') if it is malformed."""
    try:
        summary = body["route_summary"]
        line = decode_polyline(body["route_geometry"])
        steps = [_step(row) for row in body["route_instructions"]]
        out = {"distance_m": round(float(summary["total_distance"])), "duration_s": round(float(summary["total_time"])),
               "steps": steps, "line": line}
    except (KeyError, IndexError, TypeError, ValueError):
        raise RouteError("unavailable") from None
    if len(line) < 2:
        raise RouteError("unavailable")
    return out
