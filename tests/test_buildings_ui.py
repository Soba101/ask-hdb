"""Exercise page additions with Node and deterministic local data, without browser networking."""

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from ask_hdb.sun import facade_day, positions, wall_exposure

STATIC = Path("src/ask_hdb/api/static")


def test_building_controls_and_sun_formula_offline(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    (tmp_path / "package.json").write_text('{"type":"module"}')
    for name in ("buildings.js", "building-card.js", "card.js", "card-map.js", "app.js"):
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


class PageTree(HTMLParser):
    """Let Node exercise the actual HTML structure without a browser or a dependency."""

    def __init__(self):
        super().__init__()
        self.root = {"tag": "document", "attrs": {}, "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        if tag not in {"meta", "link", "input", "br"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        assert self.stack[-1]["tag"] == tag, f"Unbalanced HTML: {tag}"
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1]["children"].append(data)


@pytest.mark.parametrize("script", ["card_ui.mjs", "card_map_ui.mjs"])
def test_card_offline(tmp_path, script):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    (tmp_path / "package.json").write_text('{"type":"module"}')
    for name in ("card.js", "card-map.js", "building-card.js"):
        source = (STATIC / name).read_text()
        assert "innerHTML" not in source
        (tmp_path / name).write_text(source)
    page = PageTree()
    page.feed((STATIC / "index.html").read_text())
    assert len(page.stack) == 1
    (tmp_path / "page.json").write_text(json.dumps(page.root))
    done = subprocess.run([node, "tests/" + script, str(tmp_path)], check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
