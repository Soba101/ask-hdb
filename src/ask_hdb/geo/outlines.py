"""Small planar helpers for Singapore building outlines; no GIS runtime needed."""

from itertools import pairwise
from math import atan2, cos, degrees, hypot, radians


def projected(points):
    """Local metres, so a degree of longitude is not mistaken for a degree of latitude."""
    lng, lat = points[0][:2]
    scale = 111320 * cos(radians(lat))
    return [((p[0] - lng) * scale, (p[1] - lat) * 111320) for p in points]


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def hull(points):
    points = sorted(set(points))
    halves = []
    for ordered in (points, points[::-1]):
        half = []
        for p in ordered:
            while len(half) > 1 and cross(half[-2], half[-1], p) <= 0:
                half.pop()
            half.append(p)
        halves.extend(half[:-1])
    return halves


def long_axis(points):
    """Compass bearing modulo 180 of the minimum-area rectangle's longer edge."""
    boundary = hull(projected(points))
    best_area, bearing = float("inf"), 0.0
    for a, b in zip(boundary, boundary[1:] + boundary[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = hypot(dx, dy)
        ux, uy = dx / length, dy / length
        along = [x * ux + y * uy for x, y in boundary]
        across = [-x * uy + y * ux for x, y in boundary]
        width, height = max(along) - min(along), max(across) - min(across)
        area = width * height
        if area < best_area:
            best_area = area
            bearing = degrees(atan2(ux, uy) if width >= height else atan2(-uy, ux)) % 180
    return round(bearing, 1) % 180


def simplify_ring(ring, tolerance=0.15):
    """Remove nearly collinear vertices, keeping corners and rounding only at the end.

    A very small tolerance keeps recesses and holes; this is not a footprint generalisation.
    Measure against the previous retained vertex to avoid keeping redundant straight edges.
    """
    points = projected(ring)
    keep = [0]
    for i in range(1, len(points) - 1):
        a, p, b = points[keep[-1]], points[i], points[i + 1]
        length = hypot(b[0] - a[0], b[1] - a[1])
        between = (p[0] - a[0]) * (p[0] - b[0]) + (p[1] - a[1]) * (p[1] - b[1]) <= 0
        if not length or not between or abs(cross(a, b, p)) / length > tolerance:
            keep.append(i)
    if len(keep) < 3:
        keep = list(range(len(ring) - 1))
    rounded = []
    for i in keep:
        p = [round(v, 6) for v in ring[i][:2]]
        if not rounded or p != rounded[-1]:
            rounded.append(p)
    if rounded[-1] != rounded[0]:
        rounded.append(rounded[0])
    return rounded


def compass(bearing):
    return ("N", "NE", "E", "SE", "S", "SW", "W", "NW")[int((bearing + 22.5) // 45) % 8]


def simplify_polygon(polygon):
    rings = [simplify_ring(ring) for ring in polygon]

    def has_area(ring):
        return len(set(map(tuple, ring))) >= 3 and abs(sum(
            cross(ring[0], a, b) for a, b in pairwise(ring))) > 1e-15

    if not has_area(rings[0]):
        raise ValueError("Building exterior collapsed at six decimal places")
    # Tiny sliver holes can collapse on the rounded grid; a line is not a valid hole.
    return [rings[0], *(ring for ring in rings[1:] if has_area(ring))]
