"""Protect the fixed split and independently built expected prices."""

from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location

import pytest
import yaml

from ask_hdb.evalrun.loader import ROOT, load_questions, select_questions


def builder():
    spec = spec_from_file_location('build_expected', ROOT / 'scripts/build_expected.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_question_bank():
    qs = load_questions()
    assert len(qs) == 106
    assert len({q['id'] for q in qs}) == 106
    assert Counter(q['kind'] for q in qs) == {
        'price': 15, 'eligibility': 12, 'grants': 10, 'price_check': 8, 'refuse': 9,
        'distance': 8, 'multi_step': 16, 'bto': 21, 'scenario': 7}
    assert {q['id'] for q in qs if q.get('heldout')} == {
        'q_price_003', 'q_price_009', 'q_price_015', 'q_eligibility_004',
        'q_eligibility_011', 'q_grants_003', 'q_grants_009',
        'q_price_check_003', 'q_price_check_008', 'q_refuse_005',
        'q_distance_003', 'q_distance_006', 'q_distance_008',
        'q_multi_step_002', 'q_multi_step_006', 'q_multi_step_010',
        'q_multi_step_011', 'q_multi_step_012', 'q_multi_step_013',
        'q_multi_step_014', 'q_multi_step_015', 'q_multi_step_016',
        'q_bto_004', 'q_bto_006', 'q_bto_011', 'q_bto_012', 'q_bto_014', 'q_bto_016', 'q_bto_018', 'q_bto_021',
        'q_scenario_004', 'q_scenario_005', 'q_scenario_006'}
    assert sum(bool(q.get('heldout')) for q in qs) == 33
    assert len(select_questions(qs)) == 72
    assert len(select_questions(qs, heldout=True)) == 105
    assert len(select_questions(qs, only='distance')) == 5
    assert len(select_questions(qs, only='multi_step')) == 7
    assert len(select_questions(qs, only='bto')) == 13
    assert len(select_questions(qs, only='scenario')) == 4
    assert 'q_refuse_003' not in {q['id'] for q in select_questions(qs, heldout=True)}
    assert len(select_questions(qs, only='price')) == 12
    assert len(select_questions(qs, only='price', limit=2)) == 2
    with pytest.raises(ValueError):
        select_questions(qs, limit=0)
    for q in qs:
        if q['kind'] in {'price', 'price_check'}:
            end = q['query'].get('until', q['query'].get('as_of'))
            assert end and end in q['question']
        if q['kind'] == 'price_check':
            assert str(q['query']['price']) in q['question']


@pytest.mark.parametrize('mutation', ['duplicate', 'kind', 'expect', 'heldout'])
def test_loader_rejects_invalid(tmp_path, mutation):
    qs = load_questions()[:2]
    if mutation == 'duplicate':
        qs[1]['id'] = qs[0]['id']
    elif mutation == 'kind':
        qs[0]['kind'] = 'invented'
    elif mutation == 'heldout':
        qs[0]['heldout'] = 'true'
    else:
        qs[0]['expect']['tolerance'] = -1
    path = tmp_path / 'bad.yaml'
    path.write_text(yaml.safe_dump(qs))
    with pytest.raises(ValueError):
        load_questions(path)


def test_frozen_expected_prices():
    module = builder()
    if not module.PARQUET.exists():
        pytest.skip('Local resale parquet is absent')
    assert module.build() == 23


def test_builder_detects_mismatch_and_preserves_comments(tmp_path):
    import pandas as pd

    module = builder()
    path = tmp_path / 'questions.yaml'
    path.write_text('# arithmetic must survive\n- id: q_test\n  kind: price\n'
                    '  expect:\n    number: 1\n  query:\n    since: 2025-01\n'
                    '    until: 2025-12\n    metric: median\n')
    parquet = tmp_path / 'data.parquet'
    pd.DataFrame({'sale_month': pd.to_datetime(['2025-01', '2026-01']),
                  'resale_price': [200, 999999]}).to_parquet(parquet)
    with pytest.raises(ValueError, match='q_test'):
        module.build(path=path, parquet=parquet)
    module.build(write=True, path=path, parquet=parquet)
    assert '# arithmetic must survive' in path.read_text()
    assert module.build(path=path, parquet=parquet) == 1


def test_comparable_widening_and_boundaries():
    import pandas as pd

    module = builder()
    rows = []
    for block, street, floor, lease, month in [
        ('a', 's', 10, 600, '2025-10'), ('b', 's', 7, 540, '2026-09'),
        ('c', 's', 13, 660, '2026-09'), ('d', 's', 10, 600, '2026-09'),
        ('e', 's', 10, 600, '2026-09'), ('f', 'other', 10, 600, '2026-09'),
        ('g', 's', 14, 600, '2026-09'), ('h', 's', 10, 661, '2026-09'),
        ('i', 's', 10, 600, '2025-09'), ('j', 's', 10, 600, '2026-10'),
    ]:
        rows.append({'block_id': block, 'street_name': street, 'town': 'T', 'flat_type': '4 ROOM',
                         'storey_mid': floor, 'lease_left_months': lease, 'sale_month': pd.Timestamp(month)})
    df = pd.DataFrame(rows)
    query = {'block_id': 'a', 'as_of': '2026-09', 'flat_type': '4 ROOM',
                 'storey_mid': 10, 'lease_left_months': 600}
    level, sample = module.comparable_rows(df, query)
    assert level == 'street' and set(sample.block_id) == set('abcde')
    level, sample = module.comparable_rows(df.drop(index=[1]), query)
    assert level == 'town' and len(sample) == 5
    level, sample = module.comparable_rows(df.drop(index=[1, 2]), query)
    assert level == 'town' and len(sample) == 4
    duplicated = pd.concat([df.iloc[[0]]] * 5, ignore_index=True)
    assert module.comparable_rows(duplicated, query)[0] == 'block'


def test_clarify_schema_and_question_wording(tmp_path):
    qs = {q['id']: q for q in load_questions()}
    assert qs['q_refuse_005']['expect'] == {'clarify': True}
    assert qs['q_refuse_005']['heldout'] is True
    assert sum(q['expect'].get('decline', False) for q in qs.values()) == 8
    assert sum(q['expect'].get('clarify', False) for q in qs.values()) == 1
    assert 'both of us have only been employed for 6 months' in qs['q_grants_003']['question']
    for qid in ('q_grants_005', 'q_grants_006', 'q_grants_009'):
        assert 'only my' in qs[qid]['question']
        assert 'our' not in qs[qid]['question']
    for expect, kind in [({'clarify': False}, 'refuse'), ({'clarify': True}, 'price'),
                         ({'clarify': True, 'decline': True}, 'refuse')]:
        q = {**qs['q_refuse_005'], 'expect': expect, 'kind': kind}
        path = tmp_path / 'bad.yaml'
        path.write_text(yaml.safe_dump([q]))
        with pytest.raises(ValueError):
            load_questions(path)
