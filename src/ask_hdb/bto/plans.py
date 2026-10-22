"""Planned rail lines from the dated LTA factsheet in rules/plans (facts as written, never a price effect)."""

from functools import lru_cache
from pathlib import Path

import yaml

PATH = Path(__file__).resolve().parents[3] / "rules/plans/2026-10.yaml"
NOTE = ("Targets as stated by LTA on the as_of date; they can change. Areas are only those the factsheet names. "
        "This says nothing about the effect on flat prices.")


@lru_cache(maxsize=1)
def _load():
    return yaml.safe_load(PATH.read_text())


def rail_plans(area=None):
    data = _load()
    lines = data["lines"]
    if area:
        word = area.lower()
        lines = [line for line in lines if word in line["name"].lower() or word in line["areas"].lower()]
    return {"n_lines": len(lines), "lines": lines, "source": data["source"], "as_of": str(data["as_of"]), "note": NOTE}
