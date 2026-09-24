#!/usr/bin/env python3
"""Publish the reviewer-safe case checks from a private runtime preflight."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path('/private/tmp/clawtrap-e2e-runtime/v3_preflight_final5.json')
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / 'reports/v3_350_preflight_matrix.json'
CHECKS = ('compile', 'grader_import', 'search_http', 'rule_transform',
          'service_http', 'agent_e2e')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding='utf-8'))
    rows = source['cases']
    if len(rows) != 350 or len({row['case_id'] for row in rows}) != 350:
        raise ValueError('Expected exactly 350 unique cases')
    if source['agent_e2e_accepted'] != 0:
        raise ValueError('The reviewer status text must be updated for accepted runs')
    output = {
        'schema': 'clawtrap.v3.public_preflight_matrix.v1',
        'generated_at': source['finished_at'],
        'total_cases': len(rows),
        'agent_e2e_accepted': source['agent_e2e_accepted'],
        'stage_counts': source['stage_counts'],
        'cases': [
            {
                'case_id': row['case_id'],
                'checks': {name: row['checks'][name] for name in CHECKS},
                'attack_rules': row['attack_rules'],
                'discoverable_targets': row['discoverable_targets'],
                'issues': row['issues'],
                'agent_acceptance': row['agent_acceptance'],
            }
            for row in rows
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Published {len(rows)} reviewer-safe preflight rows: {args.output}")


if __name__ == '__main__':
    main()
