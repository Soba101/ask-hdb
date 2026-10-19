"""Use the published examples without copying their expected amounts."""

from pathlib import Path

import pytest
import yaml

from ask_hdb.rules import BuyerProfile, Flat, cpf_housing_grant, ehg_amount

SNAPSHOT = Path(__file__).resolve().parents[2] / "rules" / "2026-10.yaml"
EXAMPLES = yaml.safe_load(SNAPSHOT.read_text())["examples"]


@pytest.mark.parametrize("name,example", EXAMPLES.items(), ids=EXAMPLES.keys())
def test_published_example(name, example):
    inputs = example["inputs"]
    family = inputs["buyer"].startswith("family_")
    citizenships = [part.upper() for part in inputs["buyer"].split("_")[1:]]
    # Missing income does not affect the employment-failure examples.
    values = {
        "scheme": "family" if family else "single",
        "citizenships": citizenships,
        "ages": [inputs.get("age", 35)] * len(citizenships),
        "monthly_household_income": inputs.get("income", 0),
        "works_12_months": inputs.get("continuous_work_12_months", True),
    }
    if family:
        values["family_timers"] = {"both": "both_first", "one_of_two": "one_first"}[
            inputs["first_timers"]
        ]
    else:
        values["first_timer"] = inputs["first_timer"]
    profile = BuyerProfile(**values)
    flat = Flat(room=int(inputs["flat"].split("-")[0]), lease_left_months=80 * 12)
    functions = {
        "family_grant": cpf_housing_grant,
        "singles_grant": cpf_housing_grant,
        "ehg": ehg_amount,
    }
    for key, amount in example["expected"].items():
        result = functions[key](profile, flat)
        assert result.amount == amount, (name, key, result)
        assert result.eligible is (amount > 0)
        assert result.rules
