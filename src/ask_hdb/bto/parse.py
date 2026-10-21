"""Parse HDB 'Annex A' launch tables (flat supply and indicative prices) from extracted PDF text."""

import re

FLAT = r"(?:2-room\s+Flexi|3-room|4-room|5-room|3Gen|CCA\s*##\s*\(30-yr\s*Lease\))"
NUM = r"\d+(?:\s*-\s*\d+)?"
ROW = re.compile(rf"(?P<flat>{FLAT})\s+(?P<area>{NUM})\s+(?P<internal>{NUM})\s+(?P<units>\d+)\s+"
                 r"\$(?P<low>[\d,]+)\s*-\s*\$(?P<high>[\d,]+)")
CATEGORY = re.compile(r"(Standard|Plus|Prime)\s+Projects?")
# The table header repeats on every page; drop it so it does not end up in a project name.
HEADER = re.compile(r"ANNEX A|Project\s+Estimated\s+Waiting\s+Time\s*@\s*\(months\)\s+Flat\s+Type\s+Estimated\s+"
                    r"Floor\s+Area\s*\*\s*\(sqm\)\s+Estimated\s+Internal\s+Floor\s+Area\s*\^\s*\(sqm\)\s+No\.\s+of\s+Units\s+"
                    r"Indicative\s+Price\s+Range\s*#\s*\(Excluding\s+Grants\)|Table A\(1\)\(a\):[^\n]*|(?m:^\s*\d\s*$)")
WAIT = re.compile(r"\s(\d+(?:/\d+)?)\s*$")


def _int(text):
    return int(text.replace(",", ""))


def parse_annex_a(text: str, launch: str) -> list[dict]:
    """One dict per flat-type row: launch, project, category, wait_months, flat_type, units, price_low, price_high."""
    text = text.split("Note:")[0]
    text = HEADER.sub(" ", text)
    rows, position, category, project, wait = [], 0, None, None, None
    for match in ROW.finditer(text):
        between = " ".join(text[position:match.start()].split())
        position = match.end()
        found = CATEGORY.search(between)
        if found:
            category, between = found.group(1), (between[:found.start()] + " " + between[found.end():]).strip()
        if between:
            # A new project: its name, markers (~ ^^ #) and the estimated waiting time come before its first row.
            wait_match = WAIT.search(" " + between)
            wait = int(wait_match.group(1).split("/")[0]) if wait_match else None
            name = between[:len(between) - len(wait_match.group(0)) + 1] if wait_match else between
            project = re.sub(r"\s*[~^#]+\s*", " ", name).strip()
        flat = re.sub(r"\s+", " ", match["flat"])
        rows.append({"launch": launch, "project": project, "category": category, "wait_months": wait,
                     "flat_type": "CCA" if flat.startswith("CCA") else flat, "units": int(match["units"]),
                     "price_low": _int(match["low"]), "price_high": _int(match["high"])})
    return rows


# Older annexes (2021 to mid-2022): no waiting-time column, and a flat type may be left out when it repeats.
LFLAT = r"(?:2-room\s+Flexi|3-room|4-room|5-room|3Gen|CCA)"
LEASE = r"\(\d+\s*-?\s*(?:yr|year)\s*Lease\)"
LEGACY_ROW = re.compile(rf"(?:(?P<flat>{LFLAT})(?P<mark>[\s+~^#]*(?:{LEASE}[\s+~^#]*)?)\s*)?(?P<area>{NUM})\s+(?P<internal>{NUM})\s+(?P<units>[\d,]+)\s+"
                        r"\$(?P<low>[\d,]+)\s*-\s*\$(?P<high>[\d,]+)")
LEGACY_NOISE = re.compile(r"Non-Mature Towns?|Mature Towns?(?:\s*/\s*Estates)?|Prime Location Public Housing Model|"
                          r"\(\d+\s*-\s*year\s*Lease\)|2-room\s+Flexi|\^\^|[+~^#]+")
LEGACY_START = re.compile(r"Table A\(1\)\([a-z]\):[^\n]*Pricing Details")


def parse_legacy_annex(text: str, launch: str) -> list[dict]:
    """Same output as parse_annex_a for the 2021 to mid-2022 layout; wait_months is None, category is None."""
    start = LEGACY_START.search(text)
    text = text[start.end():] if start else text
    text = HEADER.sub(" ", text.split("Note:")[0])
    text = re.sub(r"Project\s+Flat\s+Type.*?\(Excluding\s+Grants\)", " ", text, flags=re.DOTALL)
    rows, position, project, flat = [], 0, None, None
    for match in LEGACY_ROW.finditer(text):
        between = " ".join(text[position:match.start()].split())
        position = match.end()
        short = bool(re.search(r"\d+\s*-?\s*(?:yr|year)\s*Lease", between + " " + (match["mark"] or "")))
        name = re.sub(r"\s+", " ", LEGACY_NOISE.sub(" ", between)).strip()
        if name:
            project = name
        if match["flat"]:
            flat = re.sub(r"\s+", " ", match["flat"])
            flat = "CCA" if flat.startswith("CCA") else flat
        label = flat + " short lease" if short and flat != "CCA" else flat  # flat is set by the first row
        rows.append({"launch": launch, "project": project, "category": None, "wait_months": None,
                     "flat_type": label, "units": _int(match["units"]),
                     "price_low": _int(match["low"]), "price_high": _int(match["high"])})
    return rows
