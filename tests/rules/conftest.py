"""Small profiles keep boundary tests focused on one changed input."""

import pytest

from ask_hdb.rules import BuyerProfile, Flat


@pytest.fixture
def family():
    def make(**changes):
        values = {
            "scheme": "family",
            "citizenships": ["SC", "SC"],
            "ages": [35, 35],
            "monthly_household_income": 4400,
            "family_timers": "both_first",
        }
        return BuyerProfile(**(values | changes))

    return make


@pytest.fixture
def single():
    def make(**changes):
        values = {
            "scheme": "single",
            "citizenships": ["SC"],
            "ages": [35],
            "monthly_household_income": 2000,
            "first_timer": True,
            "marital_status": "unmarried",
        }
        return BuyerProfile(**(values | changes))

    return make


@pytest.fixture
def flat():
    def make(**changes):
        return Flat(**({"room": 4, "lease_left_months": 80 * 12} | changes))

    return make
