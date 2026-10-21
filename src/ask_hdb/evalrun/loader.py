"""Validate the frozen question bank before selecting a run."""

import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
QUESTION_PATH = ROOT / 'eval/questions.yaml'
KINDS = ('price', 'eligibility', 'grants', 'price_check', 'refuse', 'distance', 'multi_step', 'bto')


def load_questions(path=QUESTION_PATH):
    questions = yaml.safe_load(Path(path).read_text())
    if not isinstance(questions, list) or not questions:
        raise ValueError('Questions must be a nonempty list')
    seen = set()
    for q in questions:
        if not isinstance(q, dict) or not {'id', 'kind', 'question', 'expect', 'source'} <= q.keys():
            raise ValueError('Missing question fields')
        if not isinstance(q['id'], str) or q['id'] in seen:
            raise ValueError('Question IDs must be unique strings')
        seen.add(q['id'])
        if q['kind'] not in KINDS or any(
            not isinstance(q[key], str) or not q[key].strip() for key in ('question', 'source')
        ):
            raise ValueError(f"Invalid question {q['id']}")
        for flag in ('heldout', 'retired'):
            if flag in q and not isinstance(q[flag], bool):
                raise ValueError(f'{flag} must be boolean')
        expect = q['expect']
        if not isinstance(expect, dict):
            raise TypeError(f"Invalid expectation for {q['id']}")
        if sum(key in expect for key in ('number', 'verdict', 'decline', 'clarify')) != 1:
            raise ValueError('Expected exactly one answer type')
        if 'number' in expect:
            for key in ('number', 'tolerance'):
                value = expect.get(key)
                if (isinstance(value, bool) or not isinstance(value, (int, float))
                        or not math.isfinite(value)):
                    raise ValueError('Expected number and tolerance must be finite')
            if expect['tolerance'] < 0 or q['kind'] not in {
                'price', 'grants', 'price_check', 'distance', 'multi_step'
            }:
                raise ValueError('Invalid numeric expectation')
        elif 'verdict' in expect:
            if (q['kind'] not in {'eligibility', 'grants'}
                    or expect['verdict'] not in {'yes', 'no'}
                    or not isinstance(expect.get('answer_keywords'), list)
                    or not expect['answer_keywords']
                    or any(not isinstance(k, str) or not k.strip()
                           for k in expect['answer_keywords'])):
                raise ValueError('Invalid verdict expectation')
        elif q['kind'] != 'refuse' or not any(
            expect.get(key) is True for key in ('decline', 'clarify')
        ):
            raise ValueError('Invalid decline/clarify expectation')
    return questions


def select_questions(questions, *, only=None, heldout=False, limit=None):
    if only is not None and only not in KINDS:
        raise ValueError('Unknown question kind')
    if limit is not None and limit < 1:
        raise ValueError('limit must be positive')
    # A retired question stays in the bank (its old results keep their meaning) but is never run again.
    selected = [q for q in questions if not q.get('retired', False) and (heldout or not q.get('heldout', False))
                and (only is None or q['kind'] == only)]
    return selected if limit is None else selected[:limit]
