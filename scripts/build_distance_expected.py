"""Independent local answers. Verify by default; --write freezes numeric leaves only."""

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / 'eval/questions.yaml'
CLEAN = ROOT / 'data/clean'
RULES = ROOT / 'rules/2026-10.yaml'
KINDS = {'distance', 'multi_step'}


def distance_km(lat1, lng1, lat2, lng2):
    # Spherical law of cosines differs from the production arcsine haversine.
    a, b, c, d = map(np.radians, (lat1, lng1, lat2, lng2))
    cosine = np.sin(a) * np.sin(c) + np.cos(a) * np.cos(c) * np.cos(d - b)
    return 6371.0088 * np.arccos(np.clip(cosine, -1, 1))


def distance_tables(blocks, places):
    tables = {}
    for kind in ('mrt', 'primary_school'):
        targets = places.loc[places.kind.eq(kind)].dropna(subset=['lat', 'lng'])
        if targets.empty:
            raise ValueError(f'No coordinates for {kind}')
        tables[kind] = pd.DataFrame(distance_km(
            blocks.lat.to_numpy()[:, None], blocks.lng.to_numpy()[:, None],
            targets.lat.to_numpy(), targets.lng.to_numpy()),
            index=blocks.block_id, columns=targets.place_id)
    return tables


def comparable_median(sales, query):
    # Reproduce the frozen sample rule with pandas, without importing app tools.
    end = pd.Period(query['as_of'], freq='M')
    known = sales.loc[sales.sale_month.le(end.to_timestamp())]
    anchor = known.loc[known.block_id.eq(query['block_id'])]
    if anchor.empty:
        raise ValueError('Comparable anchor is absent at the end month')
    rows = known.loc[
        known.sale_month.ge((end - 11).to_timestamp())
        & known.flat_type.eq(query['flat_type'])
        & known.storey_mid.between(query['storey_mid'] - 3, query['storey_mid'] + 3)
        & known.lease_left_months.between(
            query['lease_left_months'] - 60, query['lease_left_months'] + 60)]
    for mask in (rows.block_id.eq(query['block_id']),
                 rows.street_name.isin(anchor.street_name) & rows.town.isin(anchor.town),
                 rows.town.isin(anchor.town)):
        sample = rows.loc[mask]
        if len(sample) >= 5:
            break
    if sample.empty:
        raise ValueError('No comparable sales')
    return round(sample.resale_price.median())


def sale_value(sales, tables, query):
    nearest = tables[query['near_kind']].min(axis=1)
    ids = nearest.index[nearest.le(query['near_km'])]
    rows = sales.loc[
        sales.block_id.isin(ids) & sales.town.eq(query['town'])
        & sales.flat_type.eq(query['flat_type'])
        & sales.sale_month.between(pd.Timestamp(query['since']), pd.Timestamp(query['until']))]
    if rows.empty:
        raise ValueError('No distance-filtered sales')
    return len(rows) if query['metric'] == 'count' else round(rows.resale_price.median())


def expected(question, sales, tables, rules):
    query = question['query']
    operation = query['operation']
    if operation == 'grant_sum':
        grants = rules['grants']
        cpf = grants['cpf_family']['first_timer_2_to_4_room_sc_sc']['value']
        tiers = grants['ehg']['families_tiers']['value']
        ehg = next(t['amount'] for t in tiers if query['income'] <= t['up_to'])
        phg = grants['phg']['families_live_with_parents_or_child']['value']
        return cpf + ehg + (phg if query['with_parents'] else 0)
    if operation in {'sale_difference', 'sale_sum'}:
        left, right = (sale_value(sales, tables, q) for q in query['sales'])
        return left - right if operation == 'sale_difference' else left + right
    if operation in {'premium_difference', 'premium_nearest'}:
        premiums = [q['price'] - comparable_median(sales, q) for q in query['comparables']]
        if operation == 'premium_difference':
            return premiums[0] - premiums[1]
        if premiums[0] == premiums[1]:
            raise ValueError('Premium selection must not tie')
        winner = query['comparables'][int(premiums[1] > premiums[0])]['block_id']
        return round(float(tables['mrt'].loc[winner].min()), 2)
    distances = tables[query['place_kind']]
    row = distances.loc[query['block_id']]
    if operation == 'nearest':
        return round(float(row.min()), 2)
    if operation == 'within_count':
        return int(row.le(query['km']).sum())
    if operation == 'closer':
        other = distances.loc[query['other_block_id']].min()
        # Subtract raw distances before rounding, so rounding cannot change the gap.
        return round(float(other - row.min()), 2)
    raise ValueError(f'Unknown expected-answer operation: {operation}')


def build(*, write=False, path=QUESTIONS, clean=CLEAN, rules_path=RULES):
    path = Path(path)
    original = path.read_text()
    questions = [q for q in yaml.safe_load(original) if q['kind'] in KINDS]
    # Geocoded parquet files are shared inputs, not shared distance or price code.
    blocks = pd.read_parquet(clean / 'blocks.parquet')
    places = pd.read_parquet(clean / 'places.parquet')
    sales = pd.read_parquet(clean / 'resale.parquet')
    rules = yaml.safe_load(rules_path.read_text())
    tables = distance_tables(blocks, places)
    mismatches = []
    for question in questions:
        value = expected(question, sales, tables, rules)
        if value != question['expect']['number']:
            mismatches.append(f"{question['id']}: stored {question['expect']['number']}, want {value}")
        if write:
            # Preserve every question and comment; only replace its numeric leaf.
            pattern = rf"(- id: {re.escape(question['id'])}\n.*?\n    number: )[^\n]+"
            original, count = re.subn(pattern, lambda m, number=value: m[1] + str(number), original,
                                      flags=re.DOTALL)
            if count != 1:
                raise ValueError(f"Cannot write {question['id']}")
    if write:
        path.write_text(original)
    elif mismatches:
        raise ValueError('\n'.join(mismatches))
    return len(questions)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    print(f'Verified/froze {build(write=args.write)} independent expected answers')
