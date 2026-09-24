#!/usr/bin/env python3
"""Serve the current v3 reviewer entirely from a loopback-only local bundle."""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlparse
from urllib.request import urlopen
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# web.create_app loads .env on import. Empty values keep local review away from
# any account database configured for the online reviewer.
for name in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_URL_NON_POOLING"):
    os.environ[name] = ""
os.environ["CLAWTRAP_USE_DATABASE"] = "0"
os.environ["VERCEL"] = "0"
os.environ["SECRET_KEY"] = secrets.token_hex(32)

from flask import abort, jsonify, redirect, request, send_file, session  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from clawtrap_benchmark import contract_review  # noqa: E402
from clawtrap_benchmark.web import app  # noqa: E402


def configure(state_dir: Path, entry_token: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_dir.chmod(0o700)
    contract_review.LOCAL_REVIEWS_PATH = state_dir / "contract_reviews.json"
    contract_review.LOCAL_CONTENT_PATH = state_dir / "contract_content_edits.json"

    @app.before_request
    def local_origin_only():
        if request.remote_addr != "127.0.0.1" or request.host.split(":", 1)[0] not in {
            "127.0.0.1", "localhost"
        }:
            abort(403)
        if request.path in {"/login", "/logout"}:
            abort(404)

    @app.context_processor
    def local_template_context():
        return {"local_review_mode": True}

    @app.get("/__local/start")
    def local_start():
        if not hmac.compare_digest(request.args.get("token", ""), entry_token):
            abort(403)
        session.clear()
        session["role"] = "admin"
        session["username"] = "本地审核"
        return redirect("/contract-review")

    @app.get("/__local/health")
    def local_health():
        return jsonify(ok=True, cases=350)

    @app.get("/__local/backup.json")
    def local_backup():
        if session.get("role") != "admin":
            abort(401)
        payload = {
            "version": "clawtrap.local-review-backup.v1",
            "reviews": contract_review.read_reviews(),
            "content_edits": contract_review.read_content_edits(),
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        from io import BytesIO
        return send_file(BytesIO(data), mimetype="application/json", as_attachment=True,
                         download_name="clawtrap-local-review-backup.json")

    @app.after_request
    def local_preview_policy(response):
        if request.path.startswith(("/clean-assets/", "/attack-assets/")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; img-src 'self' data: blob:; "
                "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                "font-src 'self' data:; connect-src 'none'; frame-src 'none'"
            )
            response.cache_control.private = True
            response.cache_control.max_age = 3600
        return response


def active_server(state_dir: Path) -> str | None:
    session_file = state_dir / "server.json"
    try:
        metadata = json.loads(session_file.read_text(encoding="utf-8"))
        url = metadata["start_url"]
        parsed = urlparse(url)
        port = int(metadata["port"])
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or parsed.port != port or parsed.path != "/__local/start"):
            return None
        with urlopen(f"http://127.0.0.1:{port}/__local/health", timeout=1) as response:
            if response.status == 200 and json.load(response).get("cases") == 350:
                return url
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the offline ClawTrap v3 review page")
    parser.add_argument("--port", type=int, default=5055, help="loopback port; use 0 for an available port")
    parser.add_argument("--open", action="store_true", help="open the review page in the default browser")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    if not (ROOT / "runtime_assets/previews.zip").is_file():
        parser.error("local preview bundle is missing; rebuild the local review package")
    if len(contract_review.candidate_index()["cases"]) != 350:
        parser.error("expected exactly 350 local v3 cases")

    state_dir = ROOT / "review_state"
    running_url = active_server(state_dir)
    if running_url:
        print(f"本地审核页已运行：{running_url}", flush=True)
        if args.open:
            webbrowser.open(running_url)
        return
    token = secrets.token_urlsafe(32)
    configure(state_dir, token)
    server = make_server("127.0.0.1", args.port, app, threaded=True)
    url = f"http://127.0.0.1:{server.server_port}/__local/start?token={token}"
    session_file = state_dir / "server.json"
    session_file.write_text(json.dumps({"pid": os.getpid(), "port": server.server_port,
                                        "start_url": url}, ensure_ascii=False, indent=2) + "\n")
    session_file.chmod(0o600)
    print(f"本地审核页：{url}", flush=True)
    print(f"审核记录：{state_dir}", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if session_file.exists():
            try:
                if json.loads(session_file.read_text()).get("pid") == os.getpid():
                    session_file.unlink()
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    main()
