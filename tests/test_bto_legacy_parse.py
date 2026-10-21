from ask_hdb.bto.parse import parse_legacy_annex

TEXT = """Table A(1)(h): February 2021 BTO Flat Supply and Pricing Details
Project Flat Type Estimated Floor Area * (sqm) Estimated Internal Floor Area ^ (sqm) No. of Units Indicative Price Range # (Excluding Grants)
Non-Mature Towns
West Hill @ Bukit Batok
2-room
Flexi +
38 36 56 $101,000  -  $115,000
48 46 107 $119,000  -  $144,000
4-room 93 90 387 $260,000  -  $334,000
Mature Towns / Estates
McNair Heights
2-room
Flexi ^^
(40-year
Lease)
38 36 46 $117,000  -  $136,000
Sun Plaza Spring 4-room 93 90 1,150 $381,000  -  $438,000 5-room 113 110 117 $520,000  -  $590,000
Note:
1) * Refers to the estimated area
"""


def test_legacy_rows_inherit_flat_type_and_project():
    rows = parse_legacy_annex(TEXT, "2021-02")
    assert [(r["project"], r["flat_type"], r["units"]) for r in rows] == [
        ("West Hill @ Bukit Batok", "2-room Flexi", 56),
        ("West Hill @ Bukit Batok", "2-room Flexi", 107),
        ("West Hill @ Bukit Batok", "4-room", 387),
        ("McNair Heights", "2-room Flexi short lease", 46),
        ("Sun Plaza Spring", "4-room", 1150),
        ("Sun Plaza Spring", "5-room", 117),
    ]
    assert rows[0]["price_low"] == 101000 and rows[0]["wait_months"] is None
