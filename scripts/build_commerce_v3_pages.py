#!/usr/bin/env python3
"""Replace a conspicuous legacy placeholder with a plausible title change."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "new_data/clean_assets/commerce_search_tamper_004/page.html"
TARGET = ROOT / "new_data/attack_assets/commerce_workflow_v3_004/page.html"


def main() -> None:
    page = SOURCE.read_text(encoding="utf-8")
    if page.count("Packard 255 G2") != 2:
        raise ValueError("Expected matching title attribute and visible product title")
    changed = page.replace("Packard 255 G2", "HP 255 G2")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(changed, encoding="utf-8")


if __name__ == "__main__":
    main()
