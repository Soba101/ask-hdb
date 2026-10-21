"""Verify the BTO eval answers. Distances use the spherical law of cosines (not the app's haversine).

Rule answers (verdicts, EHG amounts) were derived by hand from rules/bto/2026-10.yaml and HDB's EHG tables, see each question's source.
Launch facts were read by hand from HDB's Annex A tables, then checked here against the parsed table.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data/clean"


def km(lat1, lng1, lat2, lng2):
    a, b, c, d = map(np.radians, (lat1, lng1, lat2, lng2))
    return 6371.0088 * np.arccos(np.clip(np.sin(a) * np.sin(c) + np.cos(a) * np.cos(c) * np.cos(d - b), -1, 1))


def expected(q, projects, flats, places):
    spec = q["query"]
    op = spec["operation"]
    if op == "launch_units":
        rows = flats[flats.project_id.eq(spec["project_id"]) & flats.launch.eq(spec["launch"])]
        if spec.get("flat_type"):
            rows = rows[rows.flat_type.eq(spec["flat_type"])]
        return int(rows.units.sum())
    if op == "launch_min_price":
        rows = flats[flats.project_id.eq(spec["project_id"]) & flats.launch.eq(spec["launch"]) & flats.flat_type.eq(spec["flat_type"])]
        return int(rows.price_low.min())
    if op == "launch_projects":
        return int(flats[flats.launch.eq(spec["launch"])].project_id.nunique())
    site = projects.loc[projects.project_id.eq(spec["project_id"])].iloc[0]
    targets = places[places.kind.eq(spec["place_kind"])].dropna(subset=["lat", "lng"])
    d = km(site.lat, site.lng, targets.lat.to_numpy(), targets.lng.to_numpy())
    return round(float(d.min()), 2) if op == "nearest" else int((d <= spec["km"]).sum())


def main():
    questions = [q for q in yaml.safe_load((ROOT / "eval/questions.yaml").read_text()) if q["kind"] == "bto" and "query" in q]
    projects, flats, places = (pd.read_parquet(CLEAN / f"{n}.parquet") for n in ("bto_projects", "bto_flats", "places"))
    bad = [f"{q['id']}: stored {q['expect']['number']}, want {expected(q, projects, flats, places)}"
           for q in questions if expected(q, projects, flats, places) != q["expect"]["number"]]
    if bad:
        raise SystemExit("\n".join(bad))
    print(f"Verified {len(questions)} BTO launch and distance answers")


if __name__ == "__main__":
    main()
