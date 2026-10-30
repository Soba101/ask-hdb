import pandas as pd

from ask_hdb.api import blockinfo


def sales(rows):
    return pd.DataFrame([{"sale_month": pd.Timestamp(month), "flat_type": t, "flat_model": m, "floor_area_sqm": a}
                         for month, t, m, a in rows])


def test_observed_groups_by_type_and_model_with_the_area_range_in_both_units():
    got = blockinfo.observed(sales([("2024-01-01", "4 ROOM", "MODEL A", 90), ("2025-02-01", "4 ROOM", "MODEL A", 93),
                                    ("2025-03-01", "3 ROOM", "NEW GENERATION", 67)]))
    assert got[0] == {"flat_type": "4 Room", "flat_model": "Model A", "sales": 2, "area_sqm": [90, 93], "area_sqft": [969, 1001]}
    assert got[1]["flat_type"] == "3 Room" and got[1]["area_sqft"] == [721, 721]  # 67 sqm x 10.7639


def test_official_facts_come_from_the_table_and_skip_zero_counts(monkeypatch):
    info = pd.DataFrame([{"block_id": "b", "year_completed": 1978, "max_floor_lvl": 14, "total_dwelling_units": 206, "commercial": True,
                          "market_hawker": False, "multistorey_carpark": False, "1room_sold": 0, "2room_sold": 0, "3room_sold": 178,
                          "4room_sold": 26, "5room_sold": 1, "exec_sold": 1, "multigen_sold": 0, "studio_apartment_sold": 0,
                          "1room_rental": 0, "2room_rental": 0, "3room_rental": 0, "other_room_rental": 0}]).set_index("block_id")
    monkeypatch.setattr(blockinfo, "_info", lambda: info)
    got = blockinfo.official("b")
    assert got["completed"] == 1978 and got["top_floor"] == 14 and got["dwellings"] == 206
    assert got["sold"] == {"3-room": 178, "4-room": 26, "5-room": 1, "Executive": 1} and got["rental"] == {}
    assert got["also"] == ["commercial units"]
    assert blockinfo.official("missing") is None


def test_block_info_is_none_without_facts_or_sales_and_states_its_limits(monkeypatch):
    monkeypatch.setattr(blockinfo, "_info", lambda: pd.DataFrame())
    assert blockinfo.block_info("x", sales([])) is None
    got = blockinfo.block_info("x", sales([("2024-01-01", "4 ROOM", "MODEL A", 90)]))
    assert got["official"] is None and got["observed_period"] == "2024-01 to 2024-01"
    assert any("do not show the room layout" in text for text in got["limits"])
