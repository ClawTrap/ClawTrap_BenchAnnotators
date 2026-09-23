#!/usr/bin/env python3
"""Build minimal HTML mutations from directly archived source responses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def build(spec_path: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    case_id = spec_path.parent.name
    original_path = spec_path.parent / "original.html"
    original_bytes = original_path.read_bytes()
    original = original_bytes.decode("utf-8-sig")
    replacements = spec.get("replacements") or [{
        "old": spec["old_text"], "new": spec["new_text"], "count": 1,
    }]
    for replacement in replacements:
        if not replacement["old"] or original.count(replacement["old"]) != replacement["count"]:
            raise ValueError(f"Unexpected anchor count in {case_id}: {replacement['old']}")
    head = re.search(r"<head\b[^>]*>", original, flags=re.I)
    if head is None or "</html>" not in original.lower():
        raise ValueError(f"Incomplete HTML snapshot: {case_id}")
    base = f'\n<base href="{spec["source_url"]}">'
    clean = original[:head.end()] + base + original[head.end():]
    attack = clean
    for replacement in replacements:
        attack = attack.replace(replacement["old"], replacement["new"])
    if attack == clean:
        raise ValueError(f"Mutation did not apply once: {case_id}")
    for mode, content in (("clean", clean), ("attack", attack)):
        dest = ROOT / f"new_data/{mode}_assets/{case_id}/page.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    (spec_path.parent / "SOURCE.md").write_text(
        f'Source URL: {spec["source_url"]}\n'
        f'Captured: {spec["captured"]} (direct HTTP HTML response; not a screenshot)\n'
        f'Original SHA-256: {hashlib.sha256(original_bytes).hexdigest()}\n'
        "Clean adds only a base href; attack changes the specified visible HTML text.\n",
        encoding="utf-8",
    )


def main() -> None:
    paths = [Path(arg) for arg in sys.argv[1:]]
    if not paths:
        raise SystemExit("Pass one or more source_spec.json files")
    for path in paths:
        build(path)
        print(path.parent.name)


if __name__ == "__main__":
    main()
