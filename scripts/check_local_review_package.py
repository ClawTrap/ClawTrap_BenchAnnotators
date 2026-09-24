#!/usr/bin/env python3
"""Verify the local reviewer contains only indexed Agent-visible task files."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from build_local_review import ROOT, copy_visible_workspace


def main() -> None:
    index = json.loads((ROOT / 'data/v3_public_workspace_files.json').read_text(encoding='utf-8'))
    expected = {entry['source'] for entries in index.values() for entry in entries}
    with TemporaryDirectory() as folder:
        output = Path(folder)
        count = copy_visible_workspace(output)
        actual = {path.relative_to(output).as_posix()
                  for tree in ('new_data/task_assets', 'new_data/workspace_seeds')
                  for path in (output / tree).rglob('*') if path.is_file()}
        assert count == len(expected) == len(actual)
        assert actual == expected
    print(f'Only {count} indexed Agent-visible task files enter the local reviewer')


if __name__ == '__main__':
    main()
