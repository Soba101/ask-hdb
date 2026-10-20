"""The runner exercises real persistence with fake model and agent calls."""

import json
import os
from types import SimpleNamespace

import pytest
import yaml

from ask_hdb.evalrun.conditions import make_condition
from ask_hdb.evalrun.loader import load_questions
from ask_hdb.evalrun.runner import run


@pytest.fixture
def bank(tmp_path):
    questions = load_questions()
    subset = [questions[0], questions[1], questions[2]]
    path = tmp_path / 'questions.yaml'
    path.write_text(yaml.safe_dump(subset))
    return path


def fake_agent(question):
    q = next(q for q in load_questions() if q['question'] == question)
    number = q['expect']['number']
    return {'answer': f'The answer is {number}.',
            'tool_calls': [{'name': 'price_stats', 'args': {}, 'result': {'value': number}}],
            'tokens': 25, 'stopped_reason': None}


def execute(tmp_path, bank, **kwargs):
    return run(questions_path=bank, reports_dir=tmp_path, settings={'model': 'fake'},
               day='2026-10-20', **kwargs)


def test_agent_resume_is_explicit_and_does_not_repeat_calls(tmp_path, bank):
    output = []
    report = execute(tmp_path, bank, invoke=fake_agent, emit=output.append)
    assert len(report['results']) == 2
    assert report['summary']['accuracy'] == 1
    assert report['summary']['steps']['median'] == 1
    assert report['summary']['grounding_rate'] == 1
    path = tmp_path / '2026-10-20-agent.json'
    assert json.loads(path.read_text()) == report
    assert path.with_suffix('.md').exists()

    def must_not_call(_):
        pytest.fail('Completed question must not run twice')

    execute(tmp_path, bank, invoke=must_not_call, emit=output.append, verbose=True)
    assert len([line for line in output if line.startswith('Resume:')]) == 2
    assert any('excluded 1' in line for line in output)


def test_error_is_recorded_and_later_questions_continue(tmp_path, bank):
    def provider_error(question):
        if question == load_questions()[0]['question']:
            raise TimeoutError('secret provider URL should not be persisted')
        return fake_agent(question)

    report = execute(tmp_path, bank, invoke=provider_error, emit=lambda _: None)
    assert report['summary']['errors'] == 1
    assert report['summary']['accuracy'] == .5
    first = report['results'][0]
    assert first['error'] == 'TimeoutError'
    assert not first['score']['passed']
    assert first['tokens'] is None and first['seconds'] >= 0
    assert 'secret provider' not in json.dumps(report)


def test_crash_keeps_finished_question_and_can_resume(tmp_path, bank):
    def crash(question):
        if question == load_questions()[1]['question']:
            raise KeyboardInterrupt
        return fake_agent(question)

    with pytest.raises(KeyboardInterrupt):
        execute(tmp_path, bank, invoke=crash, emit=lambda _: None)
    stored = json.loads((tmp_path / '2026-10-20-agent.json').read_text())
    assert len(stored['results']) == 1
    report = execute(tmp_path, bank, invoke=fake_agent, emit=lambda _: None)
    assert len(report['results']) == 2


def test_heldout_requires_flag_even_after_prior_opt_in(tmp_path, bank):
    execute(tmp_path, bank, invoke=fake_agent, heldout=True, emit=lambda _: None)
    report = execute(tmp_path, bank, invoke=fake_agent, emit=lambda _: None)
    assert len(report['results']) == 3  # Preserve past evidence without scoring held-out rows.
    assert report['summary']['questions'] == 2
    assert 'q_price_003' not in report['active_ids']
    report = execute(tmp_path, bank, invoke=fake_agent, only='price', limit=1, emit=lambda _: None)
    assert report['summary']['questions'] == 1


def test_changed_question_is_not_silently_reused(tmp_path, bank):
    execute(tmp_path, bank, invoke=fake_agent, emit=lambda _: None)
    qs = yaml.safe_load(bank.read_text())
    qs[0]['expect']['number'] += 1
    bank.write_text(yaml.safe_dump(qs))
    with pytest.raises(ValueError, match='Changed question'):
        execute(tmp_path, bank, invoke=fake_agent, emit=lambda _: None)


def test_model_mismatch_is_rejected(tmp_path, bank):
    execute(tmp_path, bank, invoke=fake_agent, emit=lambda _: None)
    with pytest.raises(ValueError, match='different model'):
        run(questions_path=bank, reports_dir=tmp_path, settings={'model': 'different'},
            day='2026-10-20', invoke=fake_agent, emit=lambda _: None)


def test_baseline_uses_plain_model_and_minimal_prompt(monkeypatch, tmp_path, bank):
    import ask_hdb.llm

    seen = []

    class Model:
        def invoke(self, messages):
            seen.append(messages)
            return SimpleNamespace(text='I do not know.', usage_metadata={'total_tokens': 17},
                                   response_metadata={})

    monkeypatch.setattr(ask_hdb.llm, 'get_chat_model', Model)
    baseline = make_condition('llm-only')
    report = execute(tmp_path, bank, condition='llm-only', invoke=baseline, emit=lambda _: None)
    assert len(seen) == 2
    assert seen[0][0].content == 'Answer the question.'
    assert seen[0][1].content == load_questions()[0]['question']
    assert all(r['tool_calls'] == [] and r['steps'] == 0 and r['tokens'] == 17
               for r in report['results'])
    assert report['summary']['accuracy'] == 0


def test_factory_failure_is_recorded_per_question(monkeypatch, tmp_path, bank):
    def broken(_):
        raise RuntimeError('configuration failure')

    monkeypatch.setattr('ask_hdb.evalrun.runner.make_condition', broken)
    report = execute(tmp_path, bank, emit=lambda _: None)
    assert report['summary']['errors'] == 2
    assert all(r['error'] == 'RuntimeError' for r in report['results'])


def test_cli_routes_eval_and_preserves_routing(monkeypatch):
    import ask_hdb
    import ask_hdb.evalrun
    import ask_hdb.tool_check

    calls = []
    monkeypatch.setattr(ask_hdb.evalrun, 'run', lambda *a, **kw: calls.append((a, kw)))
    monkeypatch.setattr('sys.argv', ['ask-hdb', 'eval', '--condition', 'llm-only', '--only',
                                     'price', '--limit', '2', '--verbose', '--heldout', '--tools', 'mcp'])
    ask_hdb.main()
    assert calls == [(('llm-only',), {'only': 'price', 'verbose': True,
                                     'heldout': True, 'limit': 2, 'tools': 'mcp'})]
    monkeypatch.setattr(ask_hdb.tool_check, 'main', lambda: calls.append('routing'))
    monkeypatch.setattr('sys.argv', ['ask-hdb', 'routing'])
    ask_hdb.main()
    assert calls[-1] == 'routing'


def test_tools_source_is_recorded_and_blocks_mixed_resume(tmp_path, bank, monkeypatch):
    monkeypatch.setenv('TOOL_SOURCE', 'direct')
    report = execute(tmp_path, bank, tools='mcp', invoke=fake_agent, emit=lambda _: None)
    assert report['model']['tools'] == 'mcp'
    assert os.environ['TOOL_SOURCE'] == 'mcp'
    with pytest.raises(ValueError, match='different model settings'):
        execute(tmp_path, bank, tools='direct', invoke=fake_agent, emit=lambda _: None)
