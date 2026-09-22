#!/usr/bin/env python3
"""Check exact HTTP preview bytes with no uncompressed assets available."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clawtrap_benchmark.web import app
from check_review_release import main as check_release


def main():
    hashes = json.loads((ROOT / "runtime_assets/sha256.json").read_text())
    with tempfile.TemporaryDirectory() as temporary:
        deployed = Path(temporary)
        (deployed / "runtime_assets").symlink_to(ROOT / "runtime_assets", target_is_directory=True)
        with patch("clawtrap_benchmark.web.ROOT", deployed), patch("clawtrap_benchmark.preview_assets.ROOT", deployed):
            client = app.test_client()
            first = next(iter(hashes)).replace("_assets/", "-assets/", 1)
            assert client.get("/" + first).status_code in (302, 401, 403)
            with client.session_transaction() as session:
                session.update(role="admin", username="bundle-check")
            for name, expected in hashes.items():
                path = ROOT / "new_data" / name
                assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
                response = client.get("/" + name.replace("_assets/", "-assets/", 1))
                assert response.status_code == 200, name
                assert hashlib.sha256(response.data).hexdigest() == expected, name
                assert response.cache_control.private, name
                response.close()
            for path in ("/clean-assets/../evaluator_assets/test.json", "/attack-assets/missing.html",
                         "/runtime_assets/previews.zip", "/new_data/source_archives/test.html"):
                assert client.get(path).status_code == 404, path
            check_release()
    print(f"Byte-identical authenticated previews: {len(hashes)}; raw asset directories absent")


if __name__ == "__main__":
    main()
