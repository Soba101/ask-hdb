"""Small answers use the first new number, including decimal tolerance edges."""

import pytest

from ask_hdb.evalrun.loader import load_questions
from ask_hdb.evalrun.scoring import answer_passes


def passes(number, answer, *, kind='distance', tolerance=0.05, text='Distance?'):
    question = {'kind': kind, 'question': text,
                'expect': {'number': number, 'tolerance': tolerance}}
    return answer_passes(question, {'answer': answer, 'tool_calls': []})


@pytest.mark.parametrize('kind', ['distance', 'multi_step'])
@pytest.mark.parametrize('answer,passed', [
    ('0.22 km', True), ('0.17 km', True), ('0.27 km', True),
    ('0.16999 km', False), ('0.27001 km', False),
    ('0.60 km; final answer 0.22 km', False),
    ('0.22 km; another distance 0.60 km', True),
    ('1. **0.22 km**', True), ('No distance available.', False),
])
def test_km_tolerance_and_first_answer(kind, answer, passed):
    assert passes(0.22, answer, kind=kind) is passed


@pytest.mark.parametrize('bid', ['blk_406_ang-mo-kio-ave-10', 'blk_10_road-22'])
def test_question_block_ids_are_labels(bid):
    text = f'What is the straight-line distance from {bid}?'
    assert passes(0.22, f'{bid}: 0.22 km', text=text)
    assert not passes(0.22, f'{bid}: 0.60 km, final 0.22 km', text=text)
    assert not passes(0.22, bid, text=text)
    # Even a negative answer matching the ID suffix is still an answer.
    assert passes(-22, '-22', tolerance=0, text='Premium for blk_10_road-22?')


@pytest.mark.parametrize('kind', ['distance', 'multi_step'])
@pytest.mark.parametrize('answer,passed', [
    ('3 schools', True), ('1. Count: 3', True), ('3.0', True),
    ('2 schools, actually 3', False), ('3.01', False), ('30', False),
])
def test_counts_are_exact(kind, answer, passed):
    assert passes(3, answer, kind=kind, tolerance=0) is passed


def test_question_numbers_are_skipped_before_km_answer():
    assert passes(0.74, 'As of 2026-09, 0.74 km', text='Distance as of 2026-09?')
    assert not passes(0.74, 'As of 2026-09, 0.90 km, final 0.74 km',
                      text='Distance as of 2026-09?')


def test_each_new_expected_answer_can_be_scored():
    for question in load_questions():
        if question['kind'] in {'distance', 'multi_step'}:
            answer = str(question['expect']['number'])
            assert answer_passes(question, {'answer': answer}), question['id']
