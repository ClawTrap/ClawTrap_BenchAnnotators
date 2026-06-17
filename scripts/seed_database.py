#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_cases import load_dotenv
from clawtrap_benchmark.storage import replace_dataset, use_database


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Seed PostgreSQL storage from a local JSON dataset.")
    parser.add_argument("json_path", help="Path to a JSON file containing a case array.")
    parser.add_argument("--dataset", help="Dataset name. Defaults to the JSON filename stem.")
    args = parser.parse_args()

    if not use_database():
        raise RuntimeError("DATABASE_URL or POSTGRES_URL is required before seeding database storage.")

    path = Path(args.json_path)
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise ValueError(f"{path} must contain a JSON array")
    dataset = args.dataset or path.stem
    replace_dataset(dataset, cases)
    print(json.dumps({"dataset": dataset, "seeded": len(cases)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
