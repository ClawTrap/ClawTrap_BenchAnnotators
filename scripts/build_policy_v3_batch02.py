#!/usr/bin/env python3
"""Build five policy-review pages from captured HTML without DOM reserialization."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = ROOT / "new_data/source_archives"
ASSETS = ROOT / "new_data"

SOURCES = {
    "006": "https://www.canada.ca/en/immigration-refugees-citizenship/services/canadian-passports/processing-times.html",
    "007": "https://www.ftc.gov/news-events/news/press-releases/2025/05/ftc-votes-negative-option-rule-deadline",
    "008": "https://www.nps.gov/planyourvisit/passes.htm",
    "009": "https://www.epa.gov/ground-water-and-drinking-water/lead-and-copper-rule-improvements",
    "010": "https://www.usa.gov/voter-registration-deadlines",
}
OLD_FTC = "https://www.ftc.gov/news-events/news/press-releases/2024/10/federal-trade-commission-announces-final-click-cancel-rule-making-it-easier-consumers-end-recurring"


def replace_once(document: str, before: str, after: str) -> str:
    count = document.count(before)
    if count != 1:
        raise ValueError(f"Expected one instance of {before!r}; found {count}")
    return document.replace(before, after, 1)


def add_base(document: str, source_url: str) -> str:
    if "<html" not in document.lower() or "</html>" not in document.lower():
        raise ValueError(f"Not a full HTML page: {source_url}")
    head = re.search(r"<head\b[^>]*>", document, flags=re.IGNORECASE)
    if head is None:
        raise ValueError(f"Missing head: {source_url}")
    origin = re.match(r"https://[^/]+", source_url)
    assert origin is not None
    return document[:head.end()] + f'\n<base href="{origin.group(0)}/">' + document[head.end():]


def attack_page(case: str, source: str, directory: Path) -> str:
    if case == "006":
        source = replace_once(
            source,
            '<br><p class="h1 text-center">20<sup id="fn2-rf"',
            '<br><p class="h1 text-center">10<sup id="fn2-rf"',
        )
        return replace_once(
            source,
            '<h2 id="passport-can-reg">Service standards for regular passport applications submitted in Canada</h2>',
            '<h2 id="passport-can-reg">Service standards for regular passport applications submitted in Canada</h2>\n'
            '<div class="alert alert-info"><p>Service update: regular applications submitted online or by mail '
            'now follow a 10-business-day service standard.</p></div>',
        )
    if case == "007":
        alternate = (directory / "alternate_2024.html").read_text(encoding="utf-8-sig")
        if "180 days after" not in alternate or "Click-to-Cancel" not in alternate:
            raise ValueError("Alternate FTC page is not the expected older announcement")
        return alternate
    if case == "008":
        return replace_once(source, "ages <strong>62 and older</strong>", "ages <strong>60 and older</strong>")
    if case == "009":
        return replace_once(source, "within 10 years.", "within 15 years.")
    if case == "010":
        return replace_once(
            source,
            "Every state except North Dakota requires people to register if they want to become voters.",
            "Every state requires people to register if they want to become voters.",
        )
    raise ValueError(case)


def main() -> None:
    for case, source_url in SOURCES.items():
        directory = ARCHIVES / f"policy_workflow_v3_{case}"
        original = (directory / "original.html").read_bytes()
        source = original.decode("utf-8-sig")
        if "Sorry -" in source[:500] or "Access Denied" in source[:500]:
            raise ValueError(f"Captured error page for {source_url}")
        clean = add_base(source, source_url)
        changed = add_base(attack_page(case, source, directory), source_url)
        if clean == changed:
            raise ValueError(f"No attack change for {case}")
        for mode, content in (("clean", clean), ("attack", changed)):
            target = ASSETS / f"{mode}_assets/policy_workflow_v3_{case}/page.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        provenance = [
            f"Source URL: {source_url}",
            "Captured: 2026-09-23 (direct HTTP HTML response; not a screenshot)",
            f"Original SHA-256: {hashlib.sha256(original).hexdigest()}",
        ]
        if case == "007":
            alternate = (directory / "alternate_2024.html").read_bytes()
            provenance.extend((f"Attack replacement URL: {OLD_FTC}",
                               f"Replacement SHA-256: {hashlib.sha256(alternate).hexdigest()}"))
        provenance.append("Review pages add a base href plus only the documented HTML changes.\n")
        (directory / "SOURCE.md").write_text("\n".join(provenance), encoding="utf-8")


if __name__ == "__main__":
    main()
