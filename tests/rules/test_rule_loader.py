"""Guard source values, caching, citations and public input shapes."""

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from ask_hdb.rules import (
    Flat,
    Rules,
    can_buy_resale,
    cpf_housing_grant,
    ehg_amount,
    load_rules,
    loader,
    max_loan,
    phg_amount,
)


def test_get_cite_and_missing_paths():
    rules = load_rules()
    path = "grants.ehg.families_income_ceiling"
    assert rules.get(path) == 9000
    citation = rules.cite(path)
    assert citation["id"] == path
    assert citation["source"].startswith("https://www.hdb.gov.sg/")
    assert citation["as_of"] == "2026-10-20"
    for missing in ("missing", "grants", path + ".missing", "grants.ehg.families_tiers.0"):
        with pytest.raises(KeyError, match="Unknown rule path"):
            rules.get(missing)
        with pytest.raises(KeyError, match="Unknown rule path"):
            rules.cite(missing)


def test_values_cannot_mutate_cached_rules():
    rules = load_rules()
    path = "grants.ehg.families_tiers"
    original = rules.get(path)
    rules.get(path)[0]["amount"] = -1
    assert rules.get(path) == original


def test_default_chooses_newest_filename_once(tmp_path, monkeypatch):
    leaf = {"source": "local", "as_of": "2026-10-20", "value": 1}
    (tmp_path / "2025-01.yaml").write_text(yaml.safe_dump({"test": leaf}))
    newest = tmp_path / "2026-01.yaml"
    newest.write_text(yaml.safe_dump({"test": leaf | {"value": 2}}))
    monkeypatch.setattr(loader, "RULES_DIR", tmp_path)
    load_rules.cache_clear()
    try:
        selected = load_rules()
        assert selected.get("test") == 2
        assert selected is load_rules(newest)
        newest.write_text("test: changed")
        assert selected is load_rules()
        assert load_rules(newest).get("test") == 2
    finally:
        load_rules.cache_clear()


def test_no_rule_files(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "RULES_DIR", tmp_path)
    load_rules.cache_clear()
    try:
        with pytest.raises(FileNotFoundError, match="No rule snapshots"):
            load_rules()
    finally:
        load_rules.cache_clear()


@pytest.mark.parametrize(
    "function", [can_buy_resale, cpf_housing_grant, ehg_amount, max_loan, phg_amount]
)
def test_every_used_value_is_cited(function, family, flat, monkeypatch):
    rules = load_rules()
    used = set()
    original = rules.get

    def record(path):
        used.add(path)
        return original(path)

    monkeypatch.setattr(rules, "get", record)
    extra = {"relation": "near"} if function is phg_amount else {}
    result = function(family(), flat(price=100000), rules=rules, **extra)
    assert {citation["id"] for citation in result.rules} == used
    assert len(result.rules) == len(used)


def test_custom_snapshot_drives_calculation(family, flat):
    path = Path(__file__).resolve().parents[2] / "rules" / "2026-10.yaml"
    data = yaml.safe_load(path.read_text())
    data["grants"]["cpf_family"]["first_timer_2_to_4_room_sc_sc"]["value"] = 123
    assert cpf_housing_grant(family(), flat(), rules=Rules(data)).amount == 123


@pytest.mark.parametrize(
    "changes",
    [
        {"citizenships": []},
        {"ages": [35]},
        {"ages": [-1, 35]},
        {"monthly_household_income": -1},
        {"citizenships": ["SC", "SC", "SC"], "ages": [35, 35, 35]},
        {"first_timer": True},
    ],
)
def test_profile_rejects_invalid_family_shapes(family, changes):
    with pytest.raises(ValidationError):
        family(**changes)


def test_single_default_income_and_scheme_fields(single):
    assert single().own_monthly_income == single().monthly_household_income
    with pytest.raises(ValidationError, match="Use first_timer"):
        single(family_timers="both_first")


@pytest.mark.parametrize(
    "changes", [{"room": 1}, {"room": 6}, {"price": -1}, {"lease_left_months": -1}]
)
def test_flat_rejects_invalid_shapes(changes):
    with pytest.raises(ValidationError):
        Flat(**({"room": 4, "lease_left_months": 960} | changes))


def test_no_numeric_rule_values_in_python():
    source_dir = Path(__file__).resolve().parents[2] / "src" / "ask_hdb" / "rules"
    forbidden = re.compile(r"\b(?:16000|24000|80000|120000|9000)\b")
    # Remove numeric separators too, so spelling cannot bypass the guard.
    for path in source_dir.glob("*.py"):
        assert not forbidden.search(path.read_text().replace("_", "")), path
