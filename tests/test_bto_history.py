import pandas as pd

from ask_hdb.bto.history import launch_vs_resale


def sales(year, lease, price, n=3):
    return [{"sale_month": pd.Timestamp(f"{year}-06-01"), "town": "PUNGGOL", "flat_type": "4 ROOM",
             "lease_commence_year": lease, "resale_price": price + i} for i in range(n)]


def test_uses_lease_window_and_mop():
    rows = sales(2026, 2021, 600000) + sales(2024, 2021, 1) + sales(2026, 2030, 1) + sales(2030, 2021, 1)  # too early, wrong lease year, too late
    ranges = pd.DataFrame([{"financial_year": 2018, "town": "PUNGGOL", "room_type": "4-room ",
                            "price_low": "286000", "price_high": "362000"}])
    out = launch_vs_resale(pd.DataFrame(rows), ranges, min_n=3)
    assert len(out) == 1 and out.n_resales[0] == 3 and out.resale_median[0] == 600001
    assert out.median_minus_launch_high[0] == 600001 - 362000
    assert launch_vs_resale(pd.DataFrame(rows), ranges, min_n=4).empty
