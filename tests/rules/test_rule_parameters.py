"""Changed snapshots must control thresholds independently of unrelated rules."""

from pathlib import Path

import pytest
import yaml

from ask_hdb.rules import Rules, can_buy_resale, cpf_housing_grant, ehg_amount, max_loan


@pytest.fixture
def snapshot():
    path = Path(__file__).resolve().parents[2] / "rules/2026-10.yaml"
    return yaml.safe_load(path.read_text())


def test_mixed_income_share_from_snapshot(snapshot, family, flat):
    snapshot["grants"]["ehg"]["mixed_couple_assessed_income_share"]["value"] = 0.25
    # A quarter of 4400 is 1100, in the band up to 1250 awarding 52500.
    result = ehg_amount(family(family_timers="one_first"), flat(), rules=Rules(snapshot))
    assert result.amount == 52500
    assert "grants.ehg.mixed_couple_assessed_income_share" in {
        citation["id"] for citation in result.rules
    }


def test_large_flat_threshold_is_independent(snapshot, family, flat):
    snapshot["eligibility"]["singles"]["max_flat_room_with_grants"]["value"] = 4
    # Changing a singles limit must leave the family four-room award at 80000.
    assert cpf_housing_grant(family(), flat(), rules=Rules(snapshot)).amount == 80000
    snapshot["grants"]["cpf_family"]["large_flat_min_room"]["value"] = 4
    assert cpf_housing_grant(family(), flat(), rules=Rules(snapshot)).amount == 50000


def test_project_room_from_snapshot(snapshot, family, flat):
    snapshot["eligibility"]["families"]["plus_prime_project_ceiling_room"]["value"] = 4
    result = can_buy_resale(family(), flat(category="prime"), rules=Rules(snapshot))
    assert result.needs_check == ["prime_resale_project_ceiling", "prime_4room_project_ceiling"]
    result = can_buy_resale(family(), flat(category="prime", room=3), rules=Rules(snapshot))
    assert result.needs_check == ["prime_resale_project_ceiling"]


def test_previous_loan_limit_from_snapshot(snapshot, family, flat):
    snapshot["loan"]["max_previous_hdb_loans_in_core_nucleus_exclusive"]["value"] = 1
    result = max_loan(family(previous_hdb_loans=1), flat(), rules=Rules(snapshot))
    assert result.eligible is False
    assert result.amount == 0
    assert "Too many previous HDB loans" in result.reasons


@pytest.mark.parametrize("section,key,value", [
    ("eligibility.families", "plus_prime_project_ceiling_room", 3),
    ("grants.cpf_family", "large_flat_min_room", 5),
    ("grants.ehg", "mixed_couple_assessed_income_share", 0.5),
])
def test_added_rule_metadata(snapshot, section, key, value):
    rules = Rules(snapshot)
    assert rules.get(f"{section}.{key}") == value
    citation = rules.cite(f"{section}.{key}")
    assert citation["as_of"] == "2026-10-20"
    assert citation["source"].startswith("https://www.hdb.gov.sg/")
