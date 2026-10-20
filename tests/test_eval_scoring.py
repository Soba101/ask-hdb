"""Scoring must fail honestly without consulting a model."""

import pytest

from ask_hdb.evalrun.report import distribution, summarize
from ask_hdb.evalrun.scoring import answer_passes, grounding, numbers


def question(expect, kind='price', text='What was the price in 2025?'):
    return {'expect': expect, 'kind': kind, 'question': text}


def result(answer, evidence=None, error=None):
    return {'answer': answer, 'tool_calls': [] if evidence is None else [{'name': 'can_buy_resale', 'result': evidence}],
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


@pytest.mark.parametrize('answer', ["I cannot predict prices.", "I can't advise on timing.",
                                    'I do not answer BTO questions.'])
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


@pytest.mark.parametrize('phrase', ['missing', 'cannot', 'outside', 'please provide',
                                   'need more', 'what is your'])
def test_generic_phrases_are_not_declines(phrase):
    assert not answer_passes(question({'decline': True}, 'refuse'), result(phrase))


@pytest.mark.parametrize('phrase', ["can't predict", 'cannot advise', 'unable to predict',
                                   'outside my scope', 'only help with resale',
                                   'not able to predict'])
def test_specific_declines(phrase):
    assert answer_passes(question({'decline': True}, 'refuse'), result(phrase))


@pytest.mark.parametrize('answer,passed', [
    ('Please provide your age and citizenship.', True),
    ('What is your household composition?', True), ('I need your flat details.', True),
    ('Tell me your citizenship.', True), ('Your details are missing.', False),
    ('Please provide your age. You are eligible.', False),
    ('Tell me your income. You cannot buy.', False),
    ('Yes, tell me your citizenship.', False),
    ('Please provide your age; your grant would be $80,000.', False),
])
def test_clarification_requires_details_without_verdict_or_numbers(answer, passed):
    assert answer_passes(question({'clarify': True}, 'refuse'), result(answer)) is passed


def test_clarification_rejects_tool_verdict():
    q = question({'clarify': True}, 'refuse')
    assert not answer_passes(q, result('Please provide your age.', {'eligible': False}))
    assert answer_passes(q, result('Please provide your age.', {'missing': ['age']}))


@pytest.mark.parametrize('answer', [
    'You are **not eligible** to buy.', 'You are _ineligible_.',
    'You `cannot buy` a resale flat.', '**No,** you are eligible.',
    'Yes, you are not eligible to buy, but you can get a grant.',
    'You have a CPF grant, but are not eligible.',
    'You are not eligible, although grants may be available.',
])
def test_formatted_and_contradictory_purchase_denials_fail(answer):
    q = question({'verdict': 'yes', 'answer_keywords': ['yes', 'eligible']})
    assert not answer_passes(q, result(answer, {'eligible': True}))


@pytest.mark.parametrize('benefit', ['a grant', 'a loan', 'EHG', 'CPF'])
def test_benefit_denial_allows_positive_purchase_verdict(benefit):
    q = question({'verdict': 'yes', 'answer_keywords': ['yes', 'eligible']})
    assert answer_passes(q, result(f'**Yes**, you are not eligible for {benefit}.',
                                   {'eligible': True}))


def test_grant_tool_verdict_cannot_support_purchase():
    q = question({'verdict': 'yes', 'answer_keywords': ['yes']})
    r = result('Yes.', {'eligible': True})
    r['tool_calls'][0]['name'] = 'calculate_grants'
    assert not answer_passes(q, r)
    r['tool_calls'].append({'name': 'can_buy_resale', 'result': {'eligible': False}})
    assert not answer_passes(q, r)
    r['tool_calls'][0]['result']['eligible'] = False
    r['tool_calls'][1]['result']['eligible'] = True
    assert answer_passes(q, r)


def test_list_markers_and_distance_units():
    answer = '1. Distance: 400 m\n2) Walk: 2 km\n- 3. Price: $80k\n• 4) Count: 7'
    assert numbers(answer) == [400, 2, 80000, 7]
    assert grounding(question({}, text='Distance?'), result(answer, {
        'distance_m': 400, 'distance_km': 2, 'price': 80000, 'count': 7,
    })) == {'supported': 4, 'total': 4, 'rate': 1}


@pytest.mark.parametrize('answer,expected,passed', [
    ('$380,000 and $420,000; final answer **$400,000**.', 400000, False),
    ('CPF grant $40,000, EHG $0', 0, False),
    ('$400,000', 400000, True), ('$400k', 400000, True),
    ('1. **$400,000**', 400000, True), ('EHG: $0.', 0, True),
    ('In 2025, $400k; final answer **$420,000**.', 400000, True),
    ('In 2025 only.', 400000, False),
])
def test_first_non_question_number_decides(answer, expected, passed):
    q = question({'number': expected, 'tolerance': 0})
    assert answer_passes(q, result(answer)) is passed


def test_formatted_negative_verdict():
    q = question({'verdict': 'no', 'answer_keywords': ['no', 'not eligible']})
    assert answer_passes(q, result('**No**, you are **not eligible**.', {'eligible': False}))


def test_small_counts_do_not_hide_a_large_answer():
    q = question({'number': 420000, 'tolerance': 0}, 'price_check')
    assert answer_passes(q, result('Level: street, n_comparables: 57, median $420,000'))
    # A wrong large number still fails.
    assert not answer_passes(q, result('57 comparables, median $380,000'))


def test_more_decline_wordings_pass_without_tools():
    q = question({'decline': True}, 'refuse', 'How do I apply for a BTO flat?')
    assert answer_passes(q, result('I can only assist with resale HDB flats and grants.'))
    assert answer_passes(q, result('I cannot provide investment timing advice.'))


def test_years_in_a_window_are_not_the_answer():
    q = question({'number': 420000, 'tolerance': 0}, 'price_check')
    assert answer_passes(q, result('Window: 2025-10..2026-09, 57 sales, median $420,000'))


def test_clarify_answer_may_list_room_types():
    q = question({'clarify': True}, 'refuse', 'Can I buy a resale flat?')
    assert answer_passes(q, result('Please provide your flat type (3-room, 4-room, 5-room) and age.'))
    assert not answer_passes(q, result('Please confirm. Your grant is $80,000.'))


def test_worked_equation_result_counts_but_first_number_wrong_still_fails():
    q = question({'number': 48888, 'tolerance': 0}, 'multi_step')
    assert answer_passes(q, result('638888 - 590000 = 48888'))
    assert not answer_passes(q, result('638888 - 590000 = 50000'))
    assert not answer_passes(q, result('The answer is 50000 (not 48888 = x)'))
