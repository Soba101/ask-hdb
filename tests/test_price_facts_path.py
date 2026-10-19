"""Real-data checks must locate the same file from any working directory."""

import runpy
from pathlib import Path


def test_price_facts_path_from_other_cwd(tmp_path, monkeypatch):
    tests_dir = Path(__file__).resolve().parent
    monkeypatch.chdir(tmp_path)
    module = runpy.run_path(str(tests_dir / "test_price_facts.py"))
    assert module["CLEAN"] == tests_dir.parent / "data/clean/resale.parquet"
    reason = module["pytestmark"].kwargs["reason"]
    assert "uv run python scripts/fetch_resale.py" in reason
    assert "uv run python scripts/clean_resale.py" in reason
