"""Annex A parsing, checked against rows copied from the real February 2026 and October 2025 annexes."""

from ask_hdb.bto.parse import parse_annex_a

SAMPLE = """ANNEX A
Table A(1)(a): Feb 2026 BTO Flat Supply and Pricing Details
Project Estimated Waiting Time @ (months) Flat Type Estimated Floor Area * (sqm) Estimated Internal Floor Area ^ (sqm) No. of Units Indicative Price Range # (Excluding Grants)
Standard Projects
Sembawang
Voyage  44
2-room Flexi 40 38 81 $150,000 - $187,000
4-room 93 90 454 $304,000 - $422,000
Sembawang
Deck~  33
3-room 69 66 84 $261,000 - $343,000
Plus Projects
Tampines Nova ~  32
2-room Flexi 40 38 24 $197,000 - $235,000
Prime Project
Redhill Peaks 55
4-room 90 86 593 $563,000 - $783,000
Note: 1) @ Estimated Waiting Time refers to"""


def test_projects_categories_waits_and_rows():
    rows = parse_annex_a(SAMPLE, "2026-02")
    assert [(r["project"], r["category"], r["wait_months"], r["flat_type"], r["units"], r["price_low"], r["price_high"])
            for r in rows] == [
        ("Sembawang Voyage", "Standard", 44, "2-room Flexi", 81, 150000, 187000),
        ("Sembawang Voyage", "Standard", 44, "4-room", 454, 304000, 422000),
        ("Sembawang Deck", "Standard", 33, "3-room", 84, 261000, 343000),
        ("Tampines Nova", "Plus", 32, "2-room Flexi", 24, 197000, 235000),
        ("Redhill Peaks", "Prime", 55, "4-room", 593, 563000, 783000)]


def test_wrapped_flat_types_ranges_and_cca():
    text = """Standard Projects
Woodlands
North Verge 47/48
2-room
Flexi  40 38 67 $140,000 - $204,000
4-room 93 - 96 90 - 93 608 $365,000 - $528,000
Fernvale
Plains~ 32
CCA ##
(30-yr
Lease) 39 36 207 $88,000 - $113,000
Plus Project
Oak Ville @
AMK 49 2-room  Flexi 40 38 88 $194,000 - $244,000
Note:"""
    rows = parse_annex_a(text, "2025-10")
    assert [(r["project"], r["wait_months"], r["flat_type"], r["units"]) for r in rows] == [
        ("Woodlands North Verge", 47, "2-room Flexi", 67), ("Woodlands North Verge", 47, "4-room", 608),
        ("Fernvale Plains", 32, "CCA", 207), ("Oak Ville @ AMK", 49, "2-room Flexi", 88)]
