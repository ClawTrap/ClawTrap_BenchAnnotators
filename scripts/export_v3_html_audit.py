#!/usr/bin/env python3
"""Publish a concise per-case authenticity audit without private source files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path('/private/tmp/clawtrap-benchmark-v3-batch01/audit_reports/v3_html_acceptance_audit_final.json')
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / 'reports/v3_350_html_authenticity.json'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding='utf-8'))
    cases = source['cases']
    if len(cases) != 350 or source['passing_cases'] != 350:
        raise ValueError('The strict HTML audit must pass all 350 cases')
    output = {
        'schema': 'clawtrap.v3.public_html_authenticity.v1',
        'total_cases': 350,
        'passing_cases': 350,
        'attack_rules': sum(row['attack_rules'] for row in cases),
        'cases': [
            {
                'case_id': row['case_id'],
                'source_url': row['source_url'],
                'attack_rules': row['attack_rules'],
                'html_snapshots_checked': len(row['evidence']),
                'min_source_similarity': min(item['score'] for item in row['evidence']),
                'problems': row['problems'],
            }
            for row in cases
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Published {len(cases)} HTML authenticity rows: {args.output}")


if __name__ == '__main__':
    main()
