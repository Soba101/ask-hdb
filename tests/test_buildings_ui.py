"""Exercise page additions with Node and deterministic local data, without browser networking."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ask_hdb.sun import facade_day, positions, wall_exposure

STATIC = Path("src/ask_hdb/api/static")


def test_building_controls_and_sun_formula_offline(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    (tmp_path / "package.json").write_text('{"type":"module"}')
    for name in ("buildings.js", "building-card.js", "app.js"):
        source = (STATIC / name).read_text()
        assert "innerHTML" not in source
        (tmp_path / name).write_text(source)
        done = subprocess.run([node, "--check", str(tmp_path / name)], check=False, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
    samples = positions("2026-03-20")
    fixture = {
        "sun": {"date": "2026-03-20", "positions": samples},
        "facades": {"date": "2026-03-20", "facades": facade_day("2026-03-20", [90, 270]), "limits": "No shade"},
        "buildings": {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {},
                       "properties": {"block_id": "blk_a", "height_m": 33.6, "facing": [90, 270]}}]},
        "exposures": [{"args": [s["azimuth"], s["altitude"], b],
                       "value": wall_exposure(s["azimuth"], s["altitude"], b) if s["altitude"] > 0 else 0}
                      for s in samples for b in range(0, 360, 45)]}
    (tmp_path / "fixture.json").write_text(json.dumps(fixture))
    done = subprocess.run([node, "tests/buildings_ui.mjs", str(tmp_path)], check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
