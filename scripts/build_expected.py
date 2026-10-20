"""Independent, dated pandas answers. Default verifies; --write freezes new values."""

import argparse
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / 'eval/questions.yaml'
PARQUET = ROOT / 'data/clean/resale.parquet'


def comparable_rows(data, query):
    # Resolve the location only from data available at the question's end month.
    end = pd.Period(query['as_of'], freq='M')
    known = data.loc[data.sale_month.le(end.to_timestamp())]
    anchor = known.loc[known.block_id.eq(query['block_id'])]
    if anchor.empty:
        raise ValueError('Expected-answer block must exist at the end month')
    rows = known.loc[
        known.sale_month.ge((end - 11).to_timestamp())
        & known.flat_type.eq(query['flat_type'])
        & known.storey_mid.between(query['storey_mid'] - 3, query['storey_mid'] + 3)
        & known.lease_left_months.between(
            query['lease_left_months'] - 60, query['lease_left_months'] + 60)
    ]
    masks = [
        ('block', rows.block_id.eq(query['block_id'])),
        ('street', rows.street_name.isin(anchor.street_name) & rows.town.isin(anchor.town)),
        ('town', rows.town.isin(anchor.town)),
    ]
    for level, mask in masks:
        sample = rows.loc[mask]
        if len(sample) >= 5:
            break
    return level, sample


def expected(data, question):
    query = question['query']
    if question['kind'] == 'price_check':
        _, rows = comparable_rows(data, query)
    else:
        # Explicit upper bounds keep later months from changing the answer.
        rows = data.loc[data.sale_month.between(
            pd.Timestamp(query['since']), pd.Timestamp(query['until']))]
        for key in ('town', 'flat_type', 'block_id'):
            if key in query:
                rows = rows.loc[rows[key].eq(query[key])]
    if rows.empty:
        raise ValueError(f"No sales for {question['id']}")
    metric = query.get('metric', 'median')
    if metric == 'count':
        return len(rows)
    return round(getattr(rows.resale_price, metric)())


def build(*, write=False, path=QUESTIONS, parquet=PARQUET):
    original = path.read_text()
    questions = yaml.safe_load(original)
    data = pd.read_parquet(parquet)
    mismatches = []
    for question in questions:
        if question['kind'] not in {'price', 'price_check'}:
            continue
        value = expected(data, question)
        if value != question['expect']['number']:
            mismatches.append(f"{question['id']}: stored {question['expect']['number']}, want {value}")
        if write:
            # Replace only numeric leaves so hand-written arithmetic comments survive.
            pattern = rf"(- id: {re.escape(question['id'])}\n.*?\n    number: )[^\n]+"
            original, count = re.subn(pattern, lambda m, number=value: m[1] + str(number), original, flags=re.DOTALL)
            if count != 1:
                raise ValueError(f"Cannot write {question['id']}")
    if write:
        path.write_text(original)
    elif mismatches:
        raise ValueError('\n'.join(mismatches))
    return len([q for q in questions if q['kind'] in {'price', 'price_check'}])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(f"Verified/froze {build(write=args.write)} independent expected answers")
