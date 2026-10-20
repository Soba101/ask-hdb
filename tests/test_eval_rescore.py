"""Offline rescoring preserves historical inputs and report selection."""

import json
import subprocess
import sys

from ask_hdb.evalrun.loader import ROOT
from ask_hdb.evalrun.report import markdown


def test_rescore_cli_uses_stored_questions(tmp_path):
    def row(qid, text):
        return {'id': qid, 'kind': 'price', 'question': text,
                'expect': {'number': 400000, 'tolerance': 0},
                'answer': '2025: $400k', 'tool_calls': [], 'error': None,
                'steps': 0, 'tokens': None, 'seconds': 1.23456,
                'score': {'passed': False, 'grounding': {'supported': 0, 'total': 0}},
                'fingerprint': 'historical'}
    report = {'condition': 'llm-only', 'active_ids': ['q_price_001'],
              'results': [row('q_price_001', 'Price in 2025?'), row('inactive', 'Price?')]}
    path = tmp_path / '2026-10-20-llm-only.json'
    original = json.dumps(report)
    path.write_text(original)
    run = subprocess.run([sys.executable, str(ROOT / 'scripts/rescore.py'), str(path)],
                         check=True, capture_output=True, text=True)
    saved = json.loads(path.with_suffix('.rescored.json').read_text())
    assert saved['results'][0]['score']['passed']
    assert not saved['results'][1]['score']['passed']
    assert saved['results'][0]['fingerprint'] == 'historical'
    assert saved['summary']['questions'] == 1
    assert saved['summary']['accuracy'] == 1
    assert path.read_text() == original
    assert path.with_suffix('.rescored.md').read_text() == markdown(saved) == run.stdout
    assert '| seconds | 1.2 | 1.2 |' in run.stdout
