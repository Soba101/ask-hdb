"""Run fresh turns and keep a durable, explicit record of failures and resume decisions."""

import hashlib
import json
import os
import time
from datetime import date
from pathlib import Path

from .conditions import make_condition
from .loader import QUESTION_PATH, ROOT, load_questions, select_questions
from .report import markdown, save_report
from .scoring import score


def map_context(question):
    """The context line the web app would send for a question's map selection (None when it has none)."""
    if not question.get('context'):
        return None
    from ask_hdb.api import mapdata

    return mapdata.context_line(mapdata.resolve(question['context']))


def fingerprint(question):
    return hashlib.sha256(json.dumps(question, sort_keys=True).encode()).hexdigest()


def model_settings():
    from dotenv import load_dotenv

    load_dotenv()
    # Do not persist credentials or endpoint URLs.
    return {'provider': os.getenv('LLM_PROVIDER', 'local'),
            'model': os.getenv('LLM_MODEL', 'qwen3.5-9b-16k'),
            'reasoning_effort': os.getenv('LLM_REASONING_EFFORT', 'none'),
            'tools': os.getenv('TOOL_SOURCE', 'direct')}


def run(condition='agent', *, only=None, verbose=False, heldout=False, limit=None,
        questions_path=QUESTION_PATH, reports_dir=ROOT / 'eval/reports',
        invoke=None, settings=None, day=None, emit=print, tools=None):
    if condition not in {'agent', 'full', 'llm-only'}:
        raise ValueError('Unknown condition')
    if tools is not None:
        if tools not in {'direct', 'mcp'}:
            raise ValueError('Unknown tools source')
        os.environ['TOOL_SOURCE'] = tools
    questions = load_questions(questions_path)
    selected = select_questions(questions, only=only, heldout=heldout, limit=limit)
    excluded = len(questions) - len(selected)
    emit(f'Selected {len(selected)} questions; excluded {excluded} by heldout/kind/limit filters.')
    settings = model_settings() if settings is None else settings
    settings = {**settings, 'tools': os.getenv('TOOL_SOURCE', 'direct')}
    if settings['tools'] not in {'direct', 'mcp'}:
        raise ValueError('Unknown tools source')
    day = day or date.today().isoformat()
    # MCP runs get their own file so direct and MCP reports never mix.
    suffix = '-mcp' if settings['tools'] == 'mcp' else ''
    if os.getenv('ASK_HDB_REPORT_TAG'):
        # A tag gives another model its own report file, so two models can run at the same time.
        suffix += '-' + os.getenv('ASK_HDB_REPORT_TAG')
    path = Path(reports_dir) / f'{day}-{condition}{suffix}.json'
    report = {'date': day, 'condition': condition, 'model': settings, 'results': []}
    if path.exists():
        report = json.loads(path.read_text())
        if report['condition'] != condition or report['model'] != settings:
            raise ValueError('Existing report has different model settings; archive it before rerunning')
    existing = {r['id']: r for r in report['results']}
    # Check all selected entries before any request, so stale data cannot hide in a resume.
    for q in selected:
        if q['id'] in existing and existing[q['id']]['fingerprint'] != fingerprint(q):
            raise ValueError(f"Changed question {q['id']}; archive report before rerunning")
    report['active_ids'] = [q['id'] for q in selected]
    report.setdefault('runs', []).append({
        'selected_ids': [q['id'] for q in selected], 'heldout': heldout, 'only': only, 'limit': limit,
    })
    save_report(path, report)
    for q in selected:
        if q['id'] in existing:
            row = existing[q['id']]
            emit(f"Resume: {q['id']} already recorded ({'error' if row['error'] else 'completed'}).")
            if verbose:
                emit(json.dumps(row, ensure_ascii=False))
            continue
        started = time.perf_counter()
        result = {'answer': '', 'tool_calls': [], 'tokens': None, 'error': None}
        try:
            # Factory errors belong to this question, just like provider request errors.
            if invoke is None:
                invoke = make_condition(condition)
            context = map_context(q)
            result.update(invoke(q['question'], context=context) if context else invoke(q['question']))
            if result.get('stopped_reason'):
                result['error'] = f"Stopped: {result['stopped_reason']}"
        except Exception as exc:  # noqa: BLE001 - each failed request must be recorded
            # Provider text can expose secrets. The exception type is enough for the report.
            result['error'] = type(exc).__name__
        result['seconds'] = time.perf_counter() - started
        result['steps'] = len(result['tool_calls'])
        row = {**q, **result, 'fingerprint': fingerprint(q), 'score': score(q, result)}
        report['results'].append(row)
        save_report(path, report)
        status = 'ERROR' if row['error'] else 'PASS' if row['score']['passed'] else 'FAIL'
        emit(f"{q['id']}: {status}")
        if verbose:
            emit(json.dumps(row, ensure_ascii=False))
    emit(markdown(report))
    emit(f'Report: {path}')
    return report
