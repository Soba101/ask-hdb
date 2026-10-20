"""Hand-written prompts and code-readable expectations for the local model check."""

PROFILE = {"scheme": "family", "citizenships": "SC,SC", "ages": "35,35",
           "monthly_household_income": 4400, "family_timers": "both_first",
           "first_timer": "not_applicable", "marital_status": "married", "previous_hdb_loans": 0,
           "works_12_months": True, "owns_private_property": False,
           "room": 4, "lease_left_months": 960, "price": 600000, "category": "standard"}
FAMILY = ("We are a family couple, both SC, both aged 35, both first-timers, "
          "household income $4400 monthly, continuously employed for the past year, "
          "no private property or previous HDB loans. The Standard resale flat is "
          "4-room with 960 months of lease left and a price of $600000. ")

# Each entry tests routing and the key arguments, not prose quality.
CASES = [
    {"question": "What are the recorded 4 ROOM resale price statistics in TAMPINES during 2025?",
     "tool": "price_stats", "args": {"town": "TAMPINES", "flat_type": "4 ROOM",
                                       "since": "2025-01", "until": "2025-12"}},
    {"question": "Find the newest 3 recorded 4 ROOM sales in BEDOK costing at most $600000.",
     "tool": "find_sales", "args": {"town": "BEDOK", "flat_type": "4 ROOM",
                                      "max_price": 600000, "limit": 3}},
    {"question": "Compare $620000 for a 4 ROOM flat at blk_406_ang-mo-kio-ave-10 "
                 "with recorded sales as of 2026-09. I have no floor, area or lease filter.",
     "tool": "compare_price", "args": {"block_id": "blk_406_ang-mo-kio-ave-10",
                                         "price": 620000, "flat_type": "4 ROOM",
                                         "as_of": "2026-09"}},
    {"question": FAMILY + "Check whether we can buy this resale flat.",
     "tool": "can_buy_resale", "args": PROFILE},
    {"question": FAMILY + "Compute only our CPF Housing Grant.",
     "tool": "cpf_housing_grant", "args": PROFILE},
    {"question": FAMILY + "Compute only our Enhanced CPF Housing Grant.",
     "tool": "ehg_amount", "args": PROFILE},
    {"question": FAMILY + "We will live with our parents. Compute our Proximity Housing Grant.",
     "tool": "phg_amount", "args": PROFILE | {"relation": "with"}},
    {"question": FAMILY + "Estimate our maximum HDB loan using the default qualifying rate.",
     "tool": "max_loan", "args": PROFILE},
    {"question": "Give recorded resale price statistics for blk_406_ang-mo-kio-ave-10, "
                 "4 ROOM, from 2026-01 to 2026-09 inclusive.",
     "tool": "price_stats", "args": {"block_id": "blk_406_ang-mo-kio-ave-10",
                                       "flat_type": "4 ROOM", "since": "2026-01",
                                       "until": "2026-09"}},
    {"question": "Predict the exact price of my flat next year. Can these tools do that?",
     "tool": None, "args": {}},
]
