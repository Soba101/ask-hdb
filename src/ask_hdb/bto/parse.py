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
