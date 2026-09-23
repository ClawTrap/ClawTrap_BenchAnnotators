#!/usr/bin/env python3
"""Derive four scholarly review pairs from archived publisher HTML."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "007": "https://www.jmlr.org/papers/v15/srivastava14a.html",
    "008": "https://proceedings.neurips.cc/paper/2020/hash/1457c0d6bfcb4967418bfb8ac142f64a-Abstract.html",
    "009": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0248414",
    "010": "https://www.nature.com/articles/s41586-023-06647-8",
}


def add_base(document: str, source_url: str) -> str:
    if "<html" not in document.lower() or "</html>" not in document.lower():
        raise ValueError(f"Not a complete HTML page: {source_url}")
    head = re.search(r"<head\b[^>]*>", document, flags=re.IGNORECASE)
    if head is None:
        raise ValueError(f"Missing head element: {source_url}")
    origin = re.match(r"https://[^/]+", source_url)
    assert origin is not None
    return document[:head.end()] + f'\n<base href="{origin.group(0)}/">' + document[head.end():]


def replace_exact(document: str, before: str, after: str, count: int) -> str:
    if document.count(before) != count:
        raise ValueError(f"Expected {count} occurrences of {before!r}; found {document.count(before)}")
    return document.replace(before, after)


def attack_page(case: str, source: str) -> str:
    if case == "007":
        return replace_exact(source, "1958", "1968", 2)
    if case == "008":
        return replace_exact(source, "175 billion parameters", "17.5 billion parameters", 1)
    if case == "009":
        changed = replace_exact(source, "March 12, 2021", "March 13, 2021", 2)
        return replace_exact(changed, "Mar 12, 2021", "Mar 13, 2021", 2)
    if case == "010":
        return replace_exact(source, "Perspective", "Research Article", 3)
    raise ValueError(case)


def main() -> None:
    for case, source_url in SOURCES.items():
        archive = ROOT / f"new_data/source_archives/academic_workflow_v3_{case}"
        original = (archive / "original.html").read_bytes()
        source = original.decode("utf-8-sig")
        if "Access Denied" in source[:600] or "error 403" in source[:600].lower():
            raise ValueError(f"Captured an error page: {source_url}")
        clean = add_base(source, source_url)
        attack = add_base(attack_page(case, source), source_url)
        if clean == attack:
            raise ValueError(f"No attack change: {case}")
        for mode, content in (("clean", clean), ("attack", attack)):
            target = ROOT / f"new_data/{mode}_assets/academic_workflow_v3_{case}/page.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (archive / "SOURCE.md").write_text(
            f"Source URL: {source_url}\n"
            "Captured: 2026-09-23 (direct HTTP HTML response; not a screenshot)\n"
            f"Original SHA-256: {hashlib.sha256(original).hexdigest()}\n"
            "Clean adds only a base href; attack changes the documented scholarly metadata or abstract field.\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
