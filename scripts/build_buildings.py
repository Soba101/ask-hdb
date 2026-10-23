"""Build compact block outlines offline. Facing is approximate per block, never per unit."""

import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from ask_hdb.geo.outlines import compass, long_axis, simplify_polygon
from ask_hdb.geo.streets import normalize_street

ROOT = Path(__file__).resolve().parents[1]


def postal(value):
    text = str(value).strip()
    return text.zfill(6) if text.isdigit() and len(text) <= 6 else None


def height_lookup(blocks, properties, sales):
    exact = {}
    for row in properties.itertuples():
        if pd.notna(row.max_floor_lvl) and float(row.max_floor_lvl) > 0:
            key = (str(row.blk_no).strip().upper(), normalize_street(row.street))
            exact[key] = max(exact.get(key, 0), int(row.max_floor_lvl))
    fallback = sales.groupby("block_id").storey_high.max().to_dict()
    out = {}
    for row in blocks.itertuples():
        key = (str(row.block).strip().upper(), normalize_street(row.street_name))
        if key in exact:
            out[row.block_id] = (exact[key], "property_info")
        elif pd.notna(fallback.get(row.block_id)) and fallback[row.block_id] > 0:
            out[row.block_id] = (int(fallback[row.block_id]), "sales")
        else:
            out[row.block_id] = (4, "default")
    return out


def build(outlines, blocks, properties, sales):
    by_postal = defaultdict(set)
    for row in blocks.itertuples():
        if code := postal(row.postal):
            by_postal[code].add(row.block_id)
    heights = height_lookup(blocks, properties, sales)
    polygons, matched = defaultdict(list), 0
    for feature in outlines["features"]:
        ids = by_postal.get(postal(feature["properties"].get("POSTAL_COD")), set())
        # An ambiguous postal is left out rather than assigning a shape to the wrong block.
        if len(ids) != 1:
            continue
        geometry = feature["geometry"]
        if geometry["type"] not in ("Polygon", "MultiPolygon"):
            continue
        key = next(iter(ids))
        parts = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        polygons[key].extend(parts)
        matched += 1
    features = []
    for key, parts in sorted(polygons.items()):
        axis = long_axis([p for polygon in parts for p in polygon[0]])
        facing = [round((axis + 90) % 360, 1), round((axis + 270) % 360, 1)]
        floors, source = heights[key]
        simplified = [simplify_polygon(polygon) for polygon in parts]
        features.append({"type": "Feature", "properties": {
            "block_id": key, "floors": floors, "height_m": round(floors * 2.8, 1),
            "height_source": source, "long_axis_deg": axis, "facing": facing,
            "facing_label": " and ".join(compass(b) for b in facing)},
            "geometry": {"type": "Polygon" if len(parts) == 1 else "MultiPolygon",
                         "coordinates": simplified[0] if len(parts) == 1 else simplified}})
    total = len(outlines["features"])
    counts = Counter(f["properties"]["height_source"] for f in features)
    report = {"outlines": total, "matched_outlines": matched,
              "outline_match_pct": round(100 * matched / total, 2) if total else 0,
              "matched_blocks": len(features), "blocks": len(blocks),
              "height_sources": {s: {"blocks": counts[s], "pct": round(100 * counts[s] / len(features), 2)
                                    if features else 0} for s in ("property_info", "sales", "default")}}
    return {"type": "FeatureCollection", "features": features}, report


def main():
    clean = ROOT / "data/clean"
    result, report = build(
        json.loads((ROOT / "data/raw/places/hdb_buildings.geojson").read_text()),
        pd.read_parquet(clean / "blocks.parquet"),
        pd.read_csv(ROOT / "data/raw/property/hdb_property_information.csv", dtype={"blk_no": str}),
        pd.read_parquet(clean / "resale.parquet"))
    path = clean / "buildings.geojson"
    path.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False))
    print(json.dumps({**report, "output_bytes": path.stat().st_size}, indent=2))


if __name__ == "__main__":
    main()
