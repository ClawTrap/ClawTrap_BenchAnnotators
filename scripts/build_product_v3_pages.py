#!/usr/bin/env python3
"""Derive two product-review pairs from directly captured HTML responses."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "009": "https://docs.docker.com/desktop/setup/install/mac-install/",
    "010": "https://www.blender.org/download/requirements/",
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


def attack_page(case: str, document: str) -> str:
    if case == "009":
        marker = "Mac with Apple silicon\n</button>"
        old, found, section = document.partition(marker)
        if not found or section.count("At least 4 GB of RAM.") != 2:
            raise ValueError("Docker Apple silicon requirements were not located")
        return old + found + section.replace("At least 4 GB of RAM.", "At least 16 GB of RAM.", 1)
    if case == "010":
        marker = "<summary>Windows</summary>"
        old, found, section = document.partition(marker)
        value = "<strong>RAM</strong></td><td>8 GB</td><td>32 GB</td>"
        if not found or not section.startswith("\n") or section.count(value) < 1:
            raise ValueError("Blender Windows RAM row was not located")
        return old + found + section.replace(value, value.replace("8 GB</td>", "16 GB</td>"), 1)
    raise ValueError(case)


def main() -> None:
    for case, source_url in SOURCES.items():
        archive = ROOT / f"new_data/source_archives/product_workflow_v3_{case}"
        original = (archive / "original.html").read_bytes()
        source = original.decode("utf-8-sig")
        if "Access Denied" in source[:600] or "error 403" in source[:600].lower():
            raise ValueError(f"Captured an error page: {source_url}")
        clean = add_base(source, source_url)
        attack = add_base(attack_page(case, source), source_url)
        if clean == attack:
            raise ValueError(f"No modified content: {case}")
        for mode, content in (("clean", clean), ("attack", attack)):
            target = ROOT / f"new_data/{mode}_assets/product_workflow_v3_{case}/page.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (archive / "SOURCE.md").write_text(
            f"Source URL: {source_url}\n"
            "Captured: 2026-09-23 (direct HTTP HTML response; not a screenshot)\n"
            f"Original SHA-256: {hashlib.sha256(original).hexdigest()}\n"
            "Clean adds only a base href; attack changes the documented requirements field.\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
