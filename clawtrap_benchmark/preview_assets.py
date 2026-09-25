"""Authenticated routes can serve raw local files or lossless deployment assets."""
from functools import lru_cache
from html import escape
from io import BytesIO
import json
from pathlib import Path
import re
import zipfile

from flask import Response, abort, request, send_file, send_from_directory
from werkzeug.security import safe_join

ROOT = Path(__file__).resolve().parents[1]

_HEAD_START = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)
_HEAD_END = re.compile(r"</head\s*>", re.IGNORECASE)
_BASE_TAG = re.compile(r"<base(?:\s|/?>)", re.IGNORECASE)


@lru_cache(maxsize=1)
def _source_urls():
    """Map preview assets to the page URL whose relative resources they use."""
    result = {}
    targets = json.loads((ROOT / "data/v3_mitm_targets.json").read_text(encoding="utf-8"))["cases"]

    def add(asset, url):
        if not asset.startswith("new_data/"):
            raise ValueError(f"Invalid preview asset path: {asset}")
        relative = asset.removeprefix("new_data/")
        if relative in result and result[relative] != url:
            raise ValueError(f"Conflicting source URLs for preview asset: {relative}")
        result[relative] = url

    for batch_path in sorted((ROOT / "data/v3_batches").glob("*.json")):
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        for case in batch["cases"]:
            case_targets = targets[case["id"]]["targets"]
            primary = [target for target in case_targets
                       if target.get("replacement_asset") == case["attack_asset"]]
            if len(primary) != 1:
                raise ValueError(f"Expected one primary preview target for {case['id']}")
            add(case["clean_asset"], primary[0]["url"])
            for target in case_targets:
                attack = target.get("replacement_asset", "")
                if not attack.startswith("new_data/attack_assets/"):
                    continue
                add(attack, target["url"])
                if attack != case["attack_asset"]:
                    clean = attack.replace("new_data/attack_assets/", "new_data/clean_assets/", 1)
                    if (ROOT / clean).is_file() or clean.removeprefix("new_data/") in _active_previews():
                        add(clean, target["url"])
    return result


def _visual_html(data: bytes, source_url: str) -> bytes:
    """Restore source-relative asset resolution in a reviewer-only rendering."""
    html = data.decode("utf-8", errors="replace")
    head = _HEAD_START.search(html)
    if head:
        close = _HEAD_END.search(html, head.end())
        head_content = html[head.end():close.start() if close else len(html)]
        if not _BASE_TAG.search(head_content):
            html = html[:head.end()] + f'<base href="{escape(source_url, quote=True)}">' + html[head.end():]
    else:
        html = f'<base href="{escape(source_url, quote=True)}">' + html
    return html.encode("utf-8")


def _visual_response(data: bytes, source_url: str):
    response = Response(_visual_html(data, source_url), content_type="text/html; charset=utf-8")
    # A captured page is untrusted. Render styles and images, but never execute
    # its scripts or submit its forms from the reviewer's browser.
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'none'; connect-src 'none'; "
        "style-src https: http: data: 'unsafe-inline'; "
        "img-src https: http: data: blob:; font-src https: http: data:; "
        "media-src https: http: data:; frame-src 'none'; object-src 'none'; "
        "form-action 'none'; base-uri https: http:"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.cache_control.private = True
    return response


@lru_cache(maxsize=1)
def _active_previews():
    try:
        value = json.loads((ROOT / "runtime_assets/sha256.json").read_text(encoding="utf-8"))
        return frozenset(value)
    except (OSError, ValueError):
        return frozenset()


def _preview_mimetype(name):
    suffix = Path(name).suffix.lower()
    if suffix in {".yaml", ".yml", ".toml", ".ris", ".bib", ".md", ".txt", ".csv"}:
        return "text/plain; charset=utf-8"
    if suffix == ".json":
        return "application/json"
    if suffix == ".pdf":
        return "application/pdf"
    return None


def send_preview(directory, path):
    directory = Path(directory)
    candidate = safe_join(str(directory), path)
    if candidate is None:
        abort(404)
    try:
        relative = Path(candidate).relative_to(ROOT / "new_data")
    except ValueError:
        abort(404)
    if relative.parts[0] not in {"clean_assets", "attack_assets"}:
        abort(404)
    if relative.as_posix() not in _active_previews():
        abort(404)
    source_url = _source_urls().get(relative.as_posix()) if request.args.get("visual") == "1" else None
    if source_url and relative.suffix.lower() in {".html", ".htm"}:
        if Path(candidate).is_file():
            return _visual_response(Path(candidate).read_bytes(), source_url)
        bundle = ROOT / "runtime_assets/previews.zip"
        if not bundle.is_file():
            abort(404)
        try:
            with zipfile.ZipFile(bundle) as archive:
                return _visual_response(archive.read(relative.as_posix()), source_url)
        except KeyError:
            abort(404)
    if Path(candidate).is_file():
        response = send_from_directory(directory, path, mimetype=_preview_mimetype(path))
        response.cache_control.private = True
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    bundle = ROOT / "runtime_assets/previews.zip"
    if not bundle.is_file():
        abort(404)
    try:
        with zipfile.ZipFile(bundle) as archive:
            data = archive.read(relative.as_posix())
    except KeyError:
        abort(404)
    response = send_file(BytesIO(data), download_name=relative.name,
                         mimetype=_preview_mimetype(relative.name), conditional=True)
    response.cache_control.private = True
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
