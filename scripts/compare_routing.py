"""A/B test: our OSM walking router against OneMap on the same block-to-place pairs (needs OneMap login in .env).

Usage: uv run python scripts/compare_routing.py [pairs]
OneMap is the reference only for distance and time; where the two disagree a person should look at the route on a map.
"""

import random
import statistics
import sys
import time
from pathlib import Path

import httpx
import pandas as pd

from ask_hdb.api import amenities, mapdata
from ask_hdb.geo import walk
from ask_hdb.geo.client import OneMap, load_credentials
from ask_hdb.geo.route import RouteError

ROOT = Path(__file__).resolve().parents[1]


def mean_gap(a, b):
    """Average metres from the points of line a to the nearest point of line b (a rough shape match)."""
    total = 0.0
    for lng, lat in a[::max(1, len(a) // 25)]:
        total += min(walk.metres(lat, lng, p[1], p[0]) for p in b)
    return total / len(a[::max(1, len(a) // 25)])


def main(count):
    random.seed(7)
    router = walk.Router(ROOT / "data/clean/walk_graph.npz")
    onemap = OneMap(httpx.Client(), load_credentials(), sleep=lambda s: None)
    blocks = pd.read_parquet(ROOT / "data/clean/blocks.parquet").block_id.tolist()
    rows = []
    while len(rows) < count:
        selection = mapdata.resolve({"kind": "block", "id": random.choice(blocks)})
        kind = random.choice(["supermarket", "mrt", "bus"])
        data = amenities.nearby("block", selection["id"], kind, 3)
        item = random.choice(data["items"])
        goal = amenities._destination(selection, item["id"])
        if goal is None:
            continue
        start = (selection["lat"], selection["lng"])
        t = time.time(); ours = router.route(start, goal[:2]); ours_ms = (time.time() - t) * 1000
        time.sleep(1.0)  # be polite to OneMap
        try:
            theirs = onemap.route(start, goal[:2])
        except RouteError as error:
            theirs = {"error": error.code}
        straight = walk.metres(*start, *goal[:2])
        row = {"kind": kind, "block": selection["id"], "to": goal[2], "straight_m": round(straight), "ours_ms": round(ours_ms)}
        row["ours_m"] = ours["distance_m"] if ours else None
        row["onemap_m"] = theirs.get("distance_m") if "error" not in theirs else None
        row["onemap_error"] = theirs.get("error")
        if ours and "error" not in theirs:
            row["gap_m"] = round(mean_gap(ours["line"], theirs["line"]))
        rows.append(row)
        print(len(rows), kind, row["straight_m"], row["ours_m"], row["onemap_m"], row.get("gap_m"), flush=True)
    frame = pd.DataFrame(rows)
    both = frame.dropna(subset=["ours_m", "onemap_m"]).copy()
    both["ratio"] = both.ours_m / both.onemap_m
    both["ours_detour"] = both.ours_m / both.straight_m.clip(lower=30)
    both["onemap_detour"] = both.onemap_m / both.straight_m.clip(lower=30)
    print("\npairs:", len(frame), "| both routed:", len(both), "| ours failed:", int(frame.ours_m.isna().sum()),
          "| OneMap failed:", int(frame.onemap_m.isna().sum()))
    within10, within25 = 100 * ((both.ratio - 1).abs() <= .10).mean(), 100 * ((both.ratio - 1).abs() <= .25).mean()
    print(f"ours / OneMap distance: median {both.ratio.median():.2f}, within 10%: {within10:.0f}%, within 25%: {within25:.0f}%")
    print(f"detour (route / straight line): ours median {both.ours_detour.median():.2f}, OneMap median "
          f"{both.onemap_detour.median():.2f}; worst ours {both.ours_detour.max():.1f}, worst OneMap {both.onemap_detour.max():.1f}")
    print(f"mean gap between the two lines: median {both.gap_m.median():.0f} m, 90th percentile {both.gap_m.quantile(.9):.0f} m")
    print(f"our time per route: median {statistics.median(frame.ours_ms):.0f} ms")
    print("\nlargest disagreements:")
    print(both.assign(delta=(both.ours_m - both.onemap_m).abs()).sort_values("delta", ascending=False).head(8)[
        ["kind", "to", "straight_m", "ours_m", "onemap_m", "gap_m"]].to_string(index=False))
    frame.to_csv(ROOT / "eval/reports/2026-10-29-routing-ab.csv", index=False)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
