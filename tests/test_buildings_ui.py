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


@pytest.mark.parametrize("script", ["card_ui.mjs", "card_map_ui.mjs", "mobile_ui.mjs"])
def test_card_offline(tmp_path, script):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    (tmp_path / "package.json").write_text('{"type":"module"}')
    for name in ("card.js", "card-map.js", "building-card.js", "buildings.js"):
        source = (STATIC / name).read_text()
        assert "innerHTML" not in source
        (tmp_path / name).write_text(source)
    page = PageTree()
    page.feed((STATIC / "index.html").read_text())
    assert len(page.stack) == 1
    (tmp_path / "page.json").write_text(json.dumps(page.root))
    done = subprocess.run([node, "tests/" + script, str(tmp_path)], check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def css_block(source, selector):
    """Inspect scoped rules, including media blocks, without a browser or CSS dependency."""
    start = source.index(selector + " {") + len(selector) + 2
    depth = 1
    for end in range(start, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return " ".join(source[start:end].split())
    raise AssertionError(f"Unclosed CSS block: {selector}")


def test_phone_markup_and_touch_css_offline():
    page = PageTree()
    page.feed((STATIC / "index.html").read_text())
    assert len(page.stack) == 1

    def walk(node):
        yield node
        for child in node["children"]:
            if isinstance(child, dict):
                yield from walk(child)

    nodes = list(walk(page.root))
    ids = [node["attrs"]["id"] for node in nodes if "id" in node["attrs"]]
    assert len(ids) == len(set(ids))
    by_id = {node["attrs"]["id"]: node for node in nodes if "id" in node["attrs"]}
    # Preserve the published DOM contract while adding a separate disclosure button.
    contract = ("card card-close card-title card-facts card-limits card-actions schools schools-list "
                "schools-summary schools-limits radius-counts points toggle-3d sun-panel sun-date "
                "sun-time sun-time-label sun-position building-error card-buildings card-sun budget flat-type")
    assert set(contract.split()) <= by_id.keys()
    toggle = by_id["layers-toggle"]
    assert toggle["tag"] == "button"
    assert toggle["attrs"]["aria-controls"] == "layers"
    assert toggle["attrs"]["aria-expanded"] == "false"
    assert "Layers" in toggle["children"]
    siblings = by_id["map-controls"]["children"]
    assert siblings.index(toggle) < siblings.index(by_id["layers"])
    assert by_id["layers"]["attrs"]["aria-label"] == "Colour the blocks"
    assert {node["attrs"]["data-mode"] for node in nodes if "data-mode" in node["attrs"]} == {"type", "price", "lease"}
    assert {node["attrs"]["data-km"] for node in nodes if "data-km" in node["attrs"]} == {"0", "0.5", "1", "2"}
    viewport = next(node for node in nodes if node["attrs"].get("name") == "viewport")
    assert "viewport-fit=cover" in viewport["attrs"]["content"]
    assert len([node for node in nodes if node["attrs"].get("class") == "legend-item"]) == 4
    for control in ("sun-date", "sun-time"):
        assert any(node["tag"] == "label" and by_id[control] in list(walk(node)) for node in nodes)

    css = (STATIC / "style.css").read_text()
    mobile = css_block(css, "@media (max-width: 800px)")
    coarse = css_block(css, "@media (pointer: coarse)")
    assert "flex-wrap: wrap" in css_block(css, ".legend")
    assert "white-space: nowrap" in css_block(css, ".legend-item")
    assert "right: 64px" in css_block(css, "#map-controls")
    assert "grid-template-columns: auto minmax(0, 1fr)" in css_block(mobile, "#map-controls")
    assert "display: none" in css_block(css, "#layers-toggle")
    assert "display: block" in css_block(mobile, "#layers-toggle")
    assert "min-height: 44px" in css_block(mobile, "#layers-toggle")
    assert "display: none" in css_block(mobile, "#layers")
    assert "position: absolute" in css_block(mobile, "#layers")
    assert "width: min(320px, 100%)" in css_block(mobile, "#layers")
    assert "max-height:" in css_block(mobile, "#layers")
    assert "display: block" in css_block(mobile, '#layers-toggle[aria-expanded="true"] ~ #layers')
    assert "grid-template-columns: minmax(0, 1fr)" in css_block(mobile, "#app")
    assert "grid-template-rows: 42dvh minmax(0, 1fr)" in css_block(mobile, "#app")
    sheet = css_block(mobile, ".card")
    for rule in ("top: auto", "bottom: 0", "width: 100%", "max-height: 58dvh", "overflow-y: auto",
                 "env(safe-area-inset-bottom)", "overscroll-behavior-y: contain"):
        assert rule in sheet
    targets = css_block(coarse, "button, summary, input, select, textarea")
    assert "min-height: 44px" in targets and "min-width: 44px" in targets
    assert "min-width: 44px" in css_block(coarse, ".layers .seg button")
    assert "font-size: 16px" in css_block(coarse, "input, select, textarea, .layers input[type=date], .layers select")
    assert "touch-action: pan-y" in css_block(coarse, "input[type=range]")
    assert "width: 100%" in css_block(coarse, ".layers input[type=date]")
