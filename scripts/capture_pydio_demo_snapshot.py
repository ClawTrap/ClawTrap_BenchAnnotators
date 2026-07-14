#!/usr/bin/env python3
"""Capture the hydrated Standard User DOM from Pydio's public demo."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "new_data" / "source_archives" / "fake_session_expiry_001"


def main() -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto("https://demo.pydio.com", wait_until="networkidle", timeout=90_000)
        page.get_by_text("Standard User", exact=True).click()
        page.wait_for_url("**/welcome/**", timeout=90_000)
        page.wait_for_load_state("networkidle", timeout=90_000)
        html = page.content()
        final_url = page.url
        title = page.title()
        browser.close()

    encoded = html.encode("utf-8")
    (ARCHIVE / "pydio_standard_user_hydrated.html").write_bytes(encoded)
    metadata = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requested_url": "https://demo.pydio.com",
        "final_url": final_url,
        "title": title,
        "capture_method": "Playwright page.content() after Standard User quick-login and network idle",
        "dom_bytes": len(encoded),
        "dom_sha256": hashlib.sha256(encoded).hexdigest(),
    }
    (ARCHIVE / "capture.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
