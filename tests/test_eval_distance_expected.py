"""Protect the appended bank and independently computed local answers."""

import hashlib
from importlib.util import module_from_spec, spec_from_file_location

import pytest
import yaml

from ask_hdb.evalrun.loader import ROOT, load_questions
from ask_hdb.evalrun.runner import fingerprint


def builder():
    spec = spec_from_file_location('distance_expected', ROOT / 'scripts/build_distance_expected.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def local_builder():
    module = builder()
    for name in ('blocks', 'places', 'resale'):
        if not (module.CLEAN / f'{name}.parquet').exists():
            pytest.skip('Local geocoded or resale parquet is absent')
    return module


def test_old_fingerprints_and_order_are_frozen():
    original = load_questions()[:50]
    digest = hashlib.sha256(''.join(fingerprint(q) for q in original).encode()).hexdigest()
    assert digest == '1ba0dd61dd7b6574bb2a7e6e7fd5b640791a6a6651a9f0269722984908d92ea1'


def test_independent_local_expectations():
    assert local_builder().build() == 24


def test_builder_fails_on_mismatch_and_only_writes_new_numeric_leaves(tmp_path):
    module = local_builder()
    original = module.QUESTIONS.read_text()
    # Keep the comments and original bank while corrupting just one new number.
    prefix, appended = original.split('- id: q_distance_001', 1)
    altered = prefix + '- id: q_distance_001' + appended.replace('number: 0.09', 'number: 999', 1)
    path = tmp_path / 'questions.yaml'
    path.write_text(altered)
    with pytest.raises(ValueError, match='q_distance_001: stored 999, want 0.09'):
        module.build(path=path)
    assert path.read_text() == altered
    assert module.build(path=path, write=True) == 24
    assert path.read_text() == original


def test_distance_formula_has_known_geometric_answers():
    import math

    distance = builder().distance_km
    assert float(distance(0, 0, 0, 0)) == 0
    assert float(distance(0, 0, 0, 90)) == pytest.approx(math.pi * 6371.0088 / 2)
    assert float(distance(0, 0, 0, 180)) == pytest.approx(math.pi * 6371.0088)


def test_new_question_contracts():
    questions = load_questions()[50:]
    for q in questions:
        query = q['query']
        if q['expect']['tolerance']:
            assert q['expect']['tolerance'] == 0.05
            assert 'straight-line' in q['question'] and '2 decimals' in q['question']
        else:
            assert isinstance(q['expect']['number'], int)
        # Every multi-step query has distinct tools or independently queried samples.
        if q['kind'] == 'multi_step':
            assert query['operation'] in {'grant_sum', 'sale_sum', 'sale_difference',
                                          'premium_difference', 'premium_nearest'}
            for sale in query.get('sales', []):
                assert sale['until'] in q['question']
            for comp in query.get('comparables', []):
                assert comp['as_of'] in q['question']


@pytest.mark.parametrize('kind', ['distance', 'multi_step'])
def test_new_kinds_require_numeric_expectations(tmp_path, kind):
    q = {**load_questions()[50], 'kind': kind,
         'expect': {'verdict': 'yes', 'answer_keywords': ['yes']}}
    path = tmp_path / 'questions.yaml'
    path.write_text(yaml.safe_dump([q]))
    with pytest.raises(ValueError, match='Invalid verdict'):
        load_questions(path)
