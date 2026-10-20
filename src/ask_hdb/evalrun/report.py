"""Aggregate observations and save each completed question atomically."""

import json
import statistics


def distribution(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {'median': None, 'p90': None}
    # Linear interpolation makes the percentile definition explicit.
    rank = (len(values) - 1) * .9
    low = int(rank)
    high = min(low + 1, len(values) - 1)
    return {'median': statistics.median(values),
            'p90': values[low] + (values[high] - values[low]) * (rank - low)}


def summarize(rows):
    def accuracy(group):
        return sum(r['score']['passed'] for r in group) / len(group) if group else None
    supported = sum(r['score']['grounding']['supported'] for r in rows)
    total = sum(r['score']['grounding']['total'] for r in rows)
    return {
        'questions': len(rows), 'errors': sum(bool(r['error']) for r in rows),
        'accuracy': accuracy(rows),
        'number_accuracy': accuracy([r for r in rows if 'number' in r['expect']]),
        'verdict_accuracy': accuracy([r for r in rows if 'verdict' in r['expect']]),
        'refusal_accuracy': accuracy([r for r in rows if r['kind'] == 'refuse']),
        'grounding_rate': supported / total if total else 1.0,
        'grounded_numbers': supported, 'answer_numbers': total,
        'by_kind': {kind: accuracy([r for r in rows if r['kind'] == kind])
                    for kind in sorted({r['kind'] for r in rows})},
        **{key: distribution([r[key] for r in rows]) for key in ('steps', 'tokens', 'seconds')},
    }


def markdown(report):
    summary = report['summary']
    def percent(value):
        return 'n/a' if value is None else f'{value:.1%}'
    lines = ['| Condition | Questions | Errors | Number | Verdict | Refusal | Grounding |',
             '|---|---:|---:|---:|---:|---:|---:|',
             f"| {report['condition']} | {summary['questions']} | {summary['errors']} | "
             + ' | '.join(percent(summary[key]) for key in (
                 'number_accuracy', 'verdict_accuracy', 'refusal_accuracy', 'grounding_rate')) + ' |',
             '', '| Measure | Median | p90 |', '|---|---:|---:|']
    for key in ('steps', 'tokens', 'seconds'):
        stats = summary[key]
        lines.append(f"| {key} | {stats['median']} | {stats['p90']} |")
    failures = [r for r in report['results'] if r['id'] in report['active_ids']
                and not r['score']['passed']]
    if failures:
        lines += ['', '| Failed question | Cause |', '|---|---|']
        for row in failures:
            cause = row['error'] or row.get('stopped_reason') or 'Answer did not match frozen expectation'
            lines.append(f"| {row['id']} | {cause} |")
    return '\n'.join(lines) + '\n'


def save_report(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    report['summary'] = summarize([r for r in report['results']
                                   if r['id'] in report['active_ids']])
    # A terminated process leaves either the previous report or the completed new one.
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)
    md_path = path.with_suffix('.md')
    temporary = md_path.with_suffix('.md.tmp')
    temporary.write_text(markdown(report))
    temporary.replace(md_path)
