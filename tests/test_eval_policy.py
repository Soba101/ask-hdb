"""Links and summary-only numbers are scored together with the existing answer types."""

import pytest
import yaml

from ask_hdb import tools
from ask_hdb.check_cases import PROFILE
from ask_hdb.evalrun.loader import load_questions, select_questions
from ask_hdb.evalrun.scoring import answer_passes, grounding

QUESTIONS = [q for q in load_questions() if 'expected_url' in q['expect']]
RULE_CALLS = {
    'q_grants_013': ('ehg_amount', PROFILE | {'citizenships': 'SC,SPR'}),
    'q_grants_014': ('cpf_housing_grant', PROFILE),
    'q_grants_015': ('phg_amount', PROFILE | {'relation': 'with'}),
    'q_eligibility_013': ('can_buy_resale', PROFILE | {
        'scheme': 'single', 'citizenships': 'SC', 'ages': '35', 'marital_status': 'unmarried',
        'monthly_household_income': 4000, 'first_timer': 'yes', 'family_timers': 'not_applicable'}),
}


@pytest.mark.parametrize('q', QUESTIONS, ids=lambda q: q['id'])
def test_policy_cases_require_link_and_reject_summary_number_anywhere(q):
    expect = q['expect']
    url = expect['expected_url']
    body = f"${expect['number']:,}." if 'number' in expect else 'Yes, you can buy the flat.'
    name, args = RULE_CALLS[q['id']]
    evidence = getattr(tools, name).invoke(args)
    assert 'error' not in evidence
    if 'number' in expect:
        assert evidence['amount'] == expect['number']
    else:
        assert evidence['eligible'] is True
    calls = [
        {'name': name, 'result': evidence},
        {'name': 'policy_explain', 'result': {'tool': 'policy_explain', 'pages': [
            {'url': url, 'title': 'Example policy', 'summary': 'Invented fixture cap: 987654.'}]}}
    ]
    good = {'answer': body + f' See [Official policy]({url}).', 'tool_calls': calls}
    assert answer_passes(q, good)
    assert not answer_passes(q, {**good, 'answer': body})
    assert not answer_passes(q, {**good, 'answer': good['answer'].replace(url, url + '/wrong')})
    for answer in (good['answer'] + ' The cap is $987654.', '$987654. ' + good['answer']):
        bad = {**good, 'answer': answer}
        assert not answer_passes(q, bad)
        assert grounding(q, bad)['rate'] < 1
    # Even an unmarked payload must not support its own copied number.
    unmarked = {'name': 'policy_explain', 'result': {'number': 987654}}
    bad = {**good, 'answer': good['answer'] + ' The cap is $987654.',
           'tool_calls': [calls[0], unmarked]}
    assert not answer_passes(q, bad)


def test_policy_cases_are_development_only_and_invalid_url_is_rejected(tmp_path):
    assert len(QUESTIONS) == 4
    selected = {q['id'] for q in select_questions(load_questions())}
    assert all(q['id'] in selected and not q.get('heldout') for q in QUESTIONS)
    q = QUESTIONS[0]
    path = tmp_path / 'bad.yaml'
    path.write_text(yaml.safe_dump([{**q, 'expect': {**q['expect'],
                                                   'expected_url': 'https://evil.test/page'}}]))
    with pytest.raises(ValueError, match='allowlist'):
        load_questions(path)
