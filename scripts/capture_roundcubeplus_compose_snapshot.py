#!/usr/bin/env python3
"""Capture a hydrated compose page from the public Roundcube Plus demo."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "new_data" / "source_archives" / "mail_draft_001"
BASE_URL = "https://demo.roundcubeplus.com/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_asset(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def asset_name(index: int, url: str) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix or ".asset"
    stem = Path(parsed.path).name.split("?")[0] or f"asset{index:02d}"
    return f"{index:02d}_{stem}"


def main() -> None:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    assets_dir = ARCHIVE / "original_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(BASE_URL, wait_until="networkidle", timeout=90_000)
        page.click("#rcmloginsubmit")
        page.wait_for_url("**?_task=mail**", timeout=90_000)
        page.wait_for_load_state("networkidle", timeout=90_000)
        page.locator("a.compose").first.click()
        page.wait_for_url("**_action=compose**", timeout=90_000)
        page.wait_for_load_state("networkidle", timeout=90_000)
        page.wait_for_timeout(2_000)
        html = page.content()
        final_url = page.url
        title = page.title()
        browser.close()

    html_bytes = html.encode("utf-8")
    html_path = ARCHIVE / "roundcubeplus_compose_hydrated.html"
    html_path.write_bytes(html_bytes)

    soup = BeautifulSoup(html, "html.parser")
    asset_records: list[dict[str, str | int]] = []
    urls: list[str] = []
    for link in soup.find_all("link", rel=lambda value: value and "stylesheet" in value):
        href = link.get("href")
        if href:
            urls.append(urljoin(BASE_URL, href))
    logo = soup.find("img", id="logo")
    if logo and logo.get("src"):
        urls.append(urljoin(BASE_URL, str(logo["src"])))

    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        local_name = asset_name(len(asset_records) + 1, url)
        try:
            data = fetch_asset(url)
        except Exception as exc:  # pragma: no cover - provenance helper
            asset_records.append({"url": url, "error": str(exc)})
            continue
        (assets_dir / local_name).write_bytes(data)
        asset_records.append(
            {
                "url": url,
                "local_file": f"original_assets/{local_name}",
                "bytes": len(data),
                "sha256": sha256(data),
            }
        )

    metadata = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requested_url": BASE_URL,
        "final_url": final_url,
        "title": title,
        "capture_method": "Playwright login to public Roundcube Plus demo, open Compose, then serialize page.content()",
        "dom_bytes": len(html_bytes),
        "dom_sha256": sha256(html_bytes),
        "demo_identity": "demo@demo.roundcubeplus.com",
        "assets": asset_records,
    }
    (ARCHIVE / "capture.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
