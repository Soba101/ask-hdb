"""The "More information" section of a block card: HDB's own block facts and the flat models and sizes seen in recorded resales.

Everything is computed here from data/clean/block_info.parquet (HDB Property Information, data.gov.sg, Singapore Open Data
Licence v1.0) and the resale table; the model writes none of it. Recorded model and floor area say nothing about room layout.
"""

from functools import lru_cache
from string import capwords

import pandas as pd

from ask_hdb.geo.loaders import ROOT

SQFT_PER_SQM = 10.7639104
SOLD_LABELS = {"1room_sold": "1-room", "2room_sold": "2-room", "3room_sold": "3-room", "4room_sold": "4-room", "5room_sold": "5-room",
               "exec_sold": "Executive", "multigen_sold": "3Gen", "studio_apartment_sold": "Studio apartment"}
RENTAL_LABELS = {"1room_rental": "1-room", "2room_rental": "2-room", "3room_rental": "3-room", "other_room_rental": "other"}
SOURCE = "HDB Property Information (data.gov.sg), Singapore Open Data Licence v1.0"


@lru_cache(maxsize=1)
def _info():
    path = ROOT / "data/clean/block_info.parquet"
    return pd.read_parquet(path).set_index("block_id") if path.exists() else pd.DataFrame()


def _count(row, labels):
    return {label: int(row[column]) for column, label in labels.items() if pd.notna(row[column]) and int(row[column]) > 0}


def official(block_id):
    info = _info()
    if block_id not in info.index:
        return None
    row = info.loc[block_id]
    also = [text for flag, text in (("commercial", "commercial units"), ("market_hawker", "a market or hawker centre"),
                                    ("multistorey_carpark", "a multi-storey car park")) if bool(row[flag])]
    return {"completed": int(row.year_completed) if pd.notna(row.year_completed) else None,
            "top_floor": int(row.max_floor_lvl) if pd.notna(row.max_floor_lvl) else None,
            "dwellings": int(row.total_dwelling_units) if pd.notna(row.total_dwelling_units) else None,
            "sold": _count(row, SOLD_LABELS), "rental": _count(row, RENTAL_LABELS), "also": also}


def observed(sales):
    """Flat models seen in this block's recorded resales: how many sales and the floor area range, by flat type and model."""
    out = []
    for (flat_type, model), group in sales.groupby(["flat_type", "flat_model"]):
        low, high = float(group.floor_area_sqm.min()), float(group.floor_area_sqm.max())
        out.append({"flat_type": flat_type.title(), "flat_model": capwords(model), "sales": int(len(group)),
                    "area_sqm": [round(low), round(high)], "area_sqft": [round(low * SQFT_PER_SQM), round(high * SQFT_PER_SQM)]})
    return sorted(out, key=lambda item: (-item["sales"], item["flat_type"], item["flat_model"]))


def block_info(block_id, sales):
    """The more_info payload for one block, or None when there is nothing to show. sales: this block's recorded resales."""
    facts, flats = official(block_id), observed(sales) if len(sales) else []
    if facts is None and not flats:
        return None
    limits = ["Block facts are HDB's own figures for the block, not for a single flat.",
              "Recorded flat models and sizes come from resale transactions only; they do not show the room layout or a floor plan.",
              "Resale floor area can include areas bought later (for example a recess or an extension)."]
    out = {"official": facts, "observed": flats, "source": SOURCE, "limits": limits}
    if len(sales):
        out["observed_period"] = f"{sales.sale_month.min():%Y-%m} to {sales.sale_month.max():%Y-%m}"
    return out
