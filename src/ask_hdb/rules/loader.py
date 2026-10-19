"""Read dated local rules without changing their source data."""

from copy import deepcopy
from datetime import date
from functools import cache
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).resolve().parents[3] / "rules"


class Rules:
    def __init__(self, data: dict):
        self._data = deepcopy(data)

    def _leaf(self, dotted_path: str) -> dict:
        node = self._data
        try:
            for part in dotted_path.split("."):
                node = node[part]
            if not isinstance(node, dict) or not {"value", "source", "as_of"} <= node.keys():
                raise KeyError(dotted_path)
        except (KeyError, TypeError):
            raise KeyError(f"Unknown rule path: {dotted_path!r}") from None
        return node

    def get(self, dotted_path: str):
        # A caller must not be able to change a cached tier table.
        return deepcopy(self._leaf(dotted_path)["value"])

    def cite(self, dotted_path: str) -> dict:
        leaf = self._leaf(dotted_path)
        as_of = leaf["as_of"]
        return {
            "id": dotted_path,
            "source": leaf["source"],
            "as_of": as_of.isoformat() if isinstance(as_of, date) else as_of,
        }


@cache
def _load(path: Path) -> Rules:
    with path.open() as stream:
        return Rules(yaml.safe_load(stream))


@cache
def load_rules(path: str | Path | None = None) -> Rules:
    """Cache each file, choosing the newest filename for the default snapshot."""
    if path is None:
        paths = sorted(RULES_DIR.glob("*.yaml"))
        if not paths:
            raise FileNotFoundError(f"No rule snapshots in {RULES_DIR}")
        path = paths[-1]
    return _load(Path(path).resolve())
