"""Authenticated routes can serve raw local files or lossless deployment assets."""
from io import BytesIO
from pathlib import Path
import zipfile

from flask import abort, send_file, send_from_directory
from werkzeug.security import safe_join

ROOT = Path(__file__).resolve().parents[1]


def send_preview(directory, path):
    directory = Path(directory)
    candidate = safe_join(str(directory), path)
    if candidate is None:
        abort(404)
    if Path(candidate).is_file():
        return send_from_directory(directory, path)
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
    response = send_file(BytesIO(data), download_name=relative.name, conditional=True)
    response.cache_control.private = True
    return response
