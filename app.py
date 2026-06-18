#!/usr/bin/env python3
from __future__ import annotations

import os

from clawtrap_benchmark.web import app, load_dotenv


def main() -> None:
    load_dotenv()
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
