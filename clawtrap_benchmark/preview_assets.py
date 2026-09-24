"""Authenticated routes can serve raw local files or lossless deployment assets."""
from io import BytesIO
from pathlib import Path
import zipfile

from flask import abort, send_file, send_from_directory
from werkzeug.security import safe_join

ROOT = Path(__file__).resolve().parents[1]


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
    if Path(candidate).is_file():
        response = send_from_directory(directory, path, mimetype=_preview_mimetype(path))
        response.cache_control.private = True
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    try:
        relative = Path(candidate).relative_to(ROOT / "new_data")
    except ValueError:
        abort(404)
    if relative.parts[0] not in {"clean_assets", "attack_assets"}:
        abort(404)
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
