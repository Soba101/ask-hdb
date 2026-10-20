"""Scoring must fail honestly without consulting a model."""

import pytest

from ask_hdb.evalrun.report import distribution, summarize
from ask_hdb.evalrun.scoring import answer_passes, grounding, numbers


def question(expect, kind='price', text='What was the price in 2025?'):
    return {'expect': expect, 'kind': kind, 'question': text}


def result(answer, evidence=None, error=None):
    return {'answer': answer, 'tool_calls': [] if evidence is None else [{'result': evidence}],
            'error': error}


@pytest.mark.parametrize('kind', ['price', 'price_check', 'grants'])
@pytest.mark.parametrize('value,passed', [(999, True), (1001, True), (1001.01, False), (998.99, False)])
def test_tolerance_edges(kind, value, passed):
    q = question({'number': 1000, 'tolerance': 1}, kind)
    assert answer_passes(q, result(f'${value}')) is passed


def test_number_formats_and_boundaries():
    assert numbers('$80,000, 80k; 0.08 million; -2.5%; 2026-09') == [
        80000, 80000, 80000, -2.5, 2026, 9]
    assert not answer_passes(question({'number': 80000, 'tolerance': 0}), result('$180000'))


@pytest.mark.parametrize('kind', ['eligibility', 'grants'])
@pytest.mark.parametrize('verdict,answer,eligible', [
    ('yes', 'Yes, eligible.', True), ('no', 'No, not eligible.', False),
])
def test_verdict_requires_prose_and_current_evidence(kind, verdict, answer, eligible):
    q = question({'verdict': verdict, 'answer_keywords': [verdict, 'eligible']}, kind)
    assert answer_passes(q, result(answer, {'eligible': eligible}))
    assert not answer_passes(q, result(answer, {'eligible': not eligible}))
    assert not answer_passes(q, result(answer, {'eligible': str(eligible)}))
    assert not answer_passes(q, result(answer, {'error': 'failed'}))
    assert not answer_passes(q, result('Maybe. Needs review.', {'eligible': eligible}))
    # The baseline can be scored for prose without fabricated tool evidence.
    assert answer_passes(q, result(answer))


def test_positive_verdict_cannot_match_negation():
    q = question({'verdict': 'yes', 'answer_keywords': ['eligible', 'yes']}, 'eligibility')
    assert not answer_passes(q, result('You are not eligible.', {'eligible': True}))
    assert not answer_passes(q, result('Yesterday was sunny.', {'eligible': True}))
    assert answer_passes(q, result('Yes, you can buy but are not eligible for a grant.',
                                   {'eligible': True}))
    assert not answer_passes(q, result('No, you are eligible.', {'eligible': True}))


@pytest.mark.parametrize('answer', ["I cannot predict prices.", 'Please provide your age.',
                                    'Could you share your citizenship?'])
def test_decline_requires_no_calls(answer):
    q = question({'decline': True}, 'refuse')
    assert answer_passes(q, result(answer))
    assert not answer_passes(q, result(answer, {'eligible': False}))
    assert not answer_passes(q, result('Yes, buy now.'))


def test_errors_and_stops_never_pass():
    q = question({'number': 1000, 'tolerance': 0})
    assert not answer_passes(q, result('1000', error='TimeoutError'))
    assert not answer_passes(q, {**result('1000'), 'stopped_reason': 'tokens'})


def test_grounding_ignores_question_and_arguments():
    q = question({}, text='Check $600000 in 2025')
    r = result('In 2025, $600000: median $500,000, sample 7, invented 99.',
               {'median': 500000, 'n': 7})
    r['tool_calls'][0]['args'] = {'invented': 99}
    assert grounding(q, r) == {'supported': 2, 'total': 3, 'rate': 2 / 3}
    assert grounding(q, result('No numbers'))['rate'] == 1
    assert grounding(q, result('$500000'))['rate'] == 0
    assert grounding(q, result('$500k', {'median': 500000}))['rate'] == 1


def test_distribution_and_micro_average():
    assert distribution([]) == {'median': None, 'p90': None}
    assert distribution([1, 2, 3, 4, 5]) == {'median': 3, 'p90': 4.6}
    rows = [{'kind': 'price', 'expect': {'number': 1}, 'error': None,
                 'score': {'passed': True, 'grounding': {'supported': n, 'total': total}},
                 'steps': 1, 'tokens': None, 'seconds': 2} for n, total in [(1, 1), (0, 3)]]
    stats = summarize(rows)
    assert stats['grounding_rate'] == .25
    assert stats['tokens']['median'] is None
    assert stats['verdict_accuracy'] is None
