"""Rescore a saved eval report offline, preserving its stored question text."""

import argparse
import json
from pathlib import Path

from ask_hdb.evalrun.report import markdown, save_report
from ask_hdb.evalrun.scoring import score


def rescore(path):
    path = Path(path)
    report = json.loads(path.read_text())
    for row in report['results']:
        # Never load today's bank: wording and expectations belong to the saved run.
        row['score'] = score(row, row)
    output = path.with_suffix('.rescored.json')
    save_report(output, report)
    print(markdown(report), end='')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path, help='eval/reports/<date>-<condition>.json')
    rescore(parser.parse_args().report)
