"""Compare address words without guessing renamed streets."""

import re

WORDS = {
    "AVE": "AVENUE", "ST": "STREET", "NTH": "NORTH", "STH": "SOUTH",
    "CTRL": "CENTRAL", "CTR": "CENTRE", "BLK": "BLOCK", "RD": "ROAD",
    "DR": "DRIVE", "CRES": "CRESCENT", "CL": "CLOSE", "PL": "PLACE",
    "PK": "PARK", "GDNS": "GARDENS", "JLN": "JALAN", "BT": "BUKIT",
    "LOR": "LORONG", "KG": "KAMPONG", "UPP": "UPPER", "TER": "TERRACE",
    "HTS": "HEIGHTS", "TG": "TANJONG",
}


def normalize_street(value: str) -> str:
    """Expand whole words only, ignoring case, punctuation and spacing."""
    value = value.upper().replace("C'WEALTH", "COMMONWEALTH")
    words = re.findall(r"[A-Z0-9]+", value)
    return " ".join(WORDS.get(word, word) for word in words)
