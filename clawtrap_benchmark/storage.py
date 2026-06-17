from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .schema import normalize_case, utc_now


DATA_DIR = Path("data")
CASES_PATH = DATA_DIR / "cases.json"
DEFAULT_DATASET = "cases"


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or os.environ.get("POSTGRES_URL_NON_POOLING")


def use_database() -> bool:
    return bool(database_url())


def is_vercel_runtime() -> bool:
    return os.environ.get("VERCEL") == "1"


def require_writable_storage() -> None:
    if is_vercel_runtime() and not use_database():
        raise RuntimeError("Persistent writes on Vercel require DATABASE_URL or POSTGRES_URL.")


def connect_db():
    import psycopg

    return psycopg.connect(database_url(), autocommit=True)


def ensure_db() -> None:
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists clawtrap_cases (
                    id text primary key,
                    dataset text not null default 'cases',
                    owner text not null,
                    status text not null,
                    source text not null,
                    case_data jsonb not null,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
            cur.execute("create index if not exists clawtrap_cases_dataset_idx on clawtrap_cases(dataset)")
            cur.execute("create index if not exists clawtrap_cases_owner_idx on clawtrap_cases(owner)")


def ensure_storage() -> None:
    if use_database():
        ensure_db()
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CASES_PATH.exists():
        write_cases([])


def read_cases() -> list[dict[str, Any]]:
    if use_database():
        return read_dataset(DEFAULT_DATASET)
    ensure_storage()
    with CASES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{CASES_PATH} must contain a JSON array")
    return data


def find_case(case_id: str, *, dataset: str = DEFAULT_DATASET) -> dict[str, Any] | None:
    for case in read_dataset(dataset):
        if case.get("id") == case_id:
            return case
    return None


def write_cases(cases: list[dict[str, Any]]) -> None:
    if use_database():
        replace_dataset(DEFAULT_DATASET, cases)
        return
    require_writable_storage()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CASES_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, CASES_PATH)


def upsert_case(raw_case: dict[str, Any], *, owner: str, source: str = "manual") -> dict[str, Any]:
    if use_database():
        normalized = normalize_case(raw_case, owner=owner, source=source)
        ensure_db()
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into clawtrap_cases (id, dataset, owner, status, source, case_data, created_at, updated_at)
                    values (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    on conflict (id) do update set
                        owner = excluded.owner,
                        status = excluded.status,
                        source = excluded.source,
                        case_data = excluded.case_data,
                        updated_at = excluded.updated_at
                    returning case_data
                    """,
                    (
                        normalized["id"],
                        raw_case.get("dataset") or DEFAULT_DATASET,
                        normalized["owner"],
                        normalized["status"],
                        normalized["source"],
                        json.dumps(normalized, ensure_ascii=False),
                        normalized["created_at"],
                        normalized["updated_at"],
                    ),
                )
                row = cur.fetchone()
                return row[0] if row else normalized

    require_writable_storage()
    cases = read_cases()
    normalized = normalize_case(raw_case, owner=owner, source=source)
    for index, existing in enumerate(cases):
        if existing.get("id") == normalized["id"]:
            normalized["created_at"] = existing.get("created_at", normalized["created_at"])
            normalized["updated_at"] = utc_now()
            cases[index] = normalized
            write_cases(cases)
            return normalized
    cases.append(normalized)
    write_cases(cases)
    return normalized


def add_case_review(case_id: str, review: dict[str, Any], *, dataset: str = DEFAULT_DATASET) -> dict[str, Any]:
    case = find_case(case_id, dataset=dataset)
    if not case:
        raise KeyError(case_id)
    reviews = case.get("reviews")
    if not isinstance(reviews, list):
        reviews = []
    reviews.append(review)
    case["reviews"] = reviews
    case["review_summary"] = summarize_reviews(reviews)
    case["dataset"] = dataset
    return upsert_case(case, owner=case.get("owner") or "llm_seed", source=case.get("source") or "manual")


def summarize_reviews(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    dimensions = ["feasibility", "accuracy", "clarity", "overall"]
    summary: dict[str, Any] = {"count": len(reviews)}
    for key in dimensions:
        values = []
        for review in reviews:
            try:
                values.append(float(review.get(key)))
            except (TypeError, ValueError):
                pass
        summary[key] = round(sum(values) / len(values), 2) if values else None
    return summary


def append_cases(new_cases: list[dict[str, Any]]) -> None:
    if use_database():
        ensure_db()
        for case in new_cases:
            upsert_case(case, owner=case.get("owner") or "llm_seed", source=case.get("source") or "llm")
        return

    require_writable_storage()
    cases = read_cases()
    seen_ids = {case.get("id") for case in cases}
    for case in new_cases:
        normalized = normalize_case(case, owner=case.get("owner") or "llm_seed", source=case.get("source") or "llm")
        while normalized["id"] in seen_ids:
            normalized = normalize_case({**normalized, "id": None}, owner=normalized["owner"], source=normalized["source"])
        seen_ids.add(normalized["id"])
        cases.append(normalized)
    write_cases(cases)


def list_file_datasets() -> list[str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    names = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            names.append(path.stem)
    return names


def read_file_dataset(dataset: str) -> list[dict[str, Any]]:
    path = DATA_DIR / f"{dataset}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def list_datasets() -> list[str]:
    if use_database():
        ensure_db()
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute("select distinct dataset from clawtrap_cases order by dataset")
                names = [row[0] for row in cur.fetchall()]
        return names or [DEFAULT_DATASET]
    return list_file_datasets() or [DEFAULT_DATASET]


def read_dataset(dataset: str) -> list[dict[str, Any]]:
    if use_database():
        ensure_db()
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute("select case_data from clawtrap_cases where dataset = %s order by updated_at desc", (dataset,))
                return [row[0] for row in cur.fetchall()]
    return read_file_dataset(dataset)


def replace_dataset(dataset: str, cases: list[dict[str, Any]]) -> None:
    if use_database():
        ensure_db()
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from clawtrap_cases where dataset = %s", (dataset,))
                for case in cases:
                    normalized = normalize_case(case, owner=case.get("owner") or "llm_seed", source=case.get("source") or "llm")
                    cur.execute(
                        """
                        insert into clawtrap_cases (id, dataset, owner, status, source, case_data, created_at, updated_at)
                        values (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                        """,
                        (
                            normalized["id"],
                            dataset,
                            normalized["owner"],
                            normalized["status"],
                            normalized["source"],
                            json.dumps(normalized, ensure_ascii=False),
                            normalized["created_at"],
                            normalized["updated_at"],
                        ),
                    )
        return

    require_writable_storage()
    path = DATA_DIR / f"{dataset}.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
