from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .schema import normalize_case, utc_now
from .schema import validate_case


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path("data")
NEW_DATA_DIR = Path("new_data")
CASES_PATH = DATA_DIR / "cases.json"
DEFAULT_DATASET = "store_checkout_001"
TASK_FILE_PREVIEW_ROOT = NEW_DATA_DIR / "task_assets"
TASK_FILE_PREVIEW_LIMIT = 40_000
SOURCE_URL_STOP_HEADINGS = ("## Original resources", "## Project", "## Archived original")
EDITABLE_CASE_FIELDS = {
    "task",
    "target",
    "task_type",
    "attack_method",
    "success_states",
    "failure_states",
    "logic",
    "attack_type",
    "interactive_form",
    "metadata",
    "expected_behavior",
    "graders",
    "attack_implementation",
}
EXPERT_DECISIONS = {"accepted", "discarded", "needs_discussion", "clear"}


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or os.environ.get("POSTGRES_URL_NON_POOLING")


def database_configured() -> bool:
    return bool(database_url())


def use_database() -> bool:
    return os.environ.get("CLAWTRAP_USE_DATABASE") == "1" and bool(database_url())


def is_vercel_runtime() -> bool:
    return os.environ.get("VERCEL") == "1"


def require_writable_storage() -> None:
    if is_vercel_runtime() and not database_configured():
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
    return [enrich_case(case) for case in data]


def find_case(case_id: str, *, dataset: str = DEFAULT_DATASET) -> dict[str, Any] | None:
    for case in read_local_dataset(dataset):
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
    raw_case = {key: value for key, value in raw_case.items() if key != "storage_origin"}
    if database_configured():
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


def set_benchmark_selected(case_id: str, selected: bool, *, selected_by: str, dataset: str = DEFAULT_DATASET) -> dict[str, Any]:
    case = find_case(case_id, dataset=dataset)
    if not case:
        raise KeyError(case_id)
    case["benchmark_selected"] = bool(selected)
    case["benchmark_selected_by"] = selected_by if selected else ""
    case["benchmark_selected_at"] = utc_now() if selected else ""
    case["dataset"] = dataset
    return upsert_case(case, owner=case.get("owner") or "llm_seed", source=case.get("source") or "manual")


def set_expert_decision(case_id: str, decision: str, *, decided_by: str, comment: str = "", dataset: str = DEFAULT_DATASET) -> dict[str, Any]:
    if decision not in EXPERT_DECISIONS:
        raise ValueError(f"invalid expert decision: {decision}")
    case = find_case(case_id, dataset=dataset)
    if not case:
        raise KeyError(case_id)
    if decision == "accepted":
        errors = validate_case(case, for_submit=True)
        if errors:
            raise ValueError("\n".join(errors))

    now = utc_now()
    history = case.get("expert_decisions")
    if not isinstance(history, list):
        history = []
    history.append({
        "decision": decision,
        "reviewer": decided_by,
        "comment": str(comment or "").strip(),
        "created_at": now,
    })

    if decision == "clear":
        case["expert_decision"] = ""
        case["expert_decision_by"] = ""
        case["expert_decision_at"] = ""
        case["expert_decision_comment"] = ""
        case["benchmark_selected"] = False
        case["benchmark_selected_by"] = ""
        case["benchmark_selected_at"] = ""
    else:
        case["expert_decision"] = decision
        case["expert_decision_by"] = decided_by
        case["expert_decision_at"] = now
        case["expert_decision_comment"] = str(comment or "").strip()
        case["benchmark_selected"] = decision == "accepted"
        case["benchmark_selected_by"] = decided_by if decision == "accepted" else ""
        case["benchmark_selected_at"] = now if decision == "accepted" else ""
    case["expert_decisions"] = history
    case["dataset"] = dataset
    return upsert_case(case, owner=case.get("owner") or "llm_seed", source=case.get("source") or "manual")


def update_case_fields(case_id: str, updates: dict[str, Any], *, edited_by: str, dataset: str = DEFAULT_DATASET) -> dict[str, Any]:
    case = find_case(case_id, dataset=dataset)
    if not case:
        raise KeyError(case_id)

    changed_fields = []
    for key in EDITABLE_CASE_FIELDS:
        if key in updates:
            case[key] = updates[key]
            changed_fields.append(key)
    normalized = normalize_case(case, owner=case.get("owner") or "llm_seed", source=case.get("source") or "manual")
    errors = validate_case(normalized, for_submit=False)
    if errors:
        raise ValueError("\n".join(errors))

    now = utc_now()
    history = normalized.get("edit_history")
    if not isinstance(history, list):
        history = []
    history.append({
        "editor": edited_by,
        "changed_fields": sorted(changed_fields),
        "created_at": now,
    })
    normalized["edit_history"] = history
    normalized["last_edited_by"] = edited_by
    normalized["last_edited_at"] = now
    normalized["dataset"] = dataset
    return upsert_case(normalized, owner=normalized.get("owner") or "llm_seed", source=normalized.get("source") or "manual")


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
    score_values = [summary[key] for key in dimensions if summary[key] is not None]
    summary["total_score"] = round(sum(score_values) / len(score_values), 2) if score_values else None
    return summary


def enrich_case(case: dict[str, Any], *, storage_origin: str | None = None, data_file: str | None = None, dataset: str | None = None) -> dict[str, Any]:
    enriched = normalize_case(dict(case), owner=case.get("owner") or "llm_seed", source=case.get("source") or "local")
    if storage_origin:
        enriched["storage_origin"] = storage_origin
    if data_file:
        enriched["data_file"] = data_file
    if dataset:
        enriched["dataset"] = dataset
    reviews = enriched.get("reviews")
    if isinstance(reviews, list):
        summary = enriched.get("review_summary")
        if not isinstance(summary, dict) or summary.get("total_score") is None:
            enriched["review_summary"] = summarize_reviews(reviews)
    enriched["task_file_previews"] = task_file_previews(enriched)
    enriched["source_urls"] = source_urls_for_case(enriched)
    return enriched


def task_file_previews(case: dict[str, Any]) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    files = case.get("task_files")
    if not isinstance(files, list):
        return previews
    root = (ROOT / TASK_FILE_PREVIEW_ROOT).resolve()
    for file in files:
        if not isinstance(file, dict):
            continue
        path_text = str(file.get("path") or "")
        preview: dict[str, Any] = {
            "key": str(file.get("key") or ""),
            "path": path_text,
            "description": str(file.get("description") or ""),
        }
        try:
            path = Path(path_text)
            if path.is_absolute():
                raise ValueError("absolute paths are not previewed")
            resolved = (ROOT / path).resolve()
            if not resolved.is_relative_to(root):
                raise ValueError("path is outside task_assets")
            if not resolved.is_file():
                raise FileNotFoundError(path_text)
            size = resolved.stat().st_size
            preview["bytes"] = size
            if size > TASK_FILE_PREVIEW_LIMIT:
                preview["truncated"] = True
            raw = resolved.read_text(encoding="utf-8", errors="replace")
            text = raw[:TASK_FILE_PREVIEW_LIMIT]
            suffix = resolved.suffix.lower()
            if suffix == ".json":
                parsed = json.loads(raw)
                preview["format"] = "json"
                preview["value"] = parsed
                preview["text"] = json.dumps(parsed, ensure_ascii=False, indent=2)
            else:
                preview["format"] = suffix.lstrip(".") or "text"
                preview["text"] = text
        except Exception as exc:
            preview["error"] = str(exc)
        previews.append(preview)
    return previews


def source_urls_for_case(case: dict[str, Any]) -> list[dict[str, str]]:
    dataset = str(case.get("dataset") or "").strip()
    if not dataset:
        return []
    source_path = ROOT / NEW_DATA_DIR / "source_archives" / dataset / "SOURCE.md"
    if not source_path.is_file():
        return []
    text = source_path.read_text(encoding="utf-8", errors="replace")
    for heading in SOURCE_URL_STOP_HEADINGS:
        marker = text.find(heading)
        if marker >= 0:
            text = text[:marker]
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        urls = re.findall(r"https?://[^>`)\s]+", line)
        if not urls:
            continue
        label = re.sub(r"^\s*[-*]\s*", "", line).split(":", 1)[0].strip() or "Source"
        label = re.sub(r"`|<|>", "", label)
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            results.append({"label": label, "url": url})
    return results


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
    names = []
    for path in data_files():
        try:
            read_case_file(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        names.append(path.stem)
    return names


def data_files() -> list[Path]:
    paths: list[Path] = []
    if NEW_DATA_DIR.exists():
        paths.extend(sorted(NEW_DATA_DIR.glob("*.jsonl")))
        paths.extend(sorted(NEW_DATA_DIR.glob("*.json")))
    if not paths and DATA_DIR.exists():
        paths.extend(sorted(DATA_DIR.glob("*.json")))
    seen = set()
    unique_paths = []
    for path in paths:
        key = path.stem
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)
    return unique_paths


def dataset_path(dataset: str) -> Path:
    candidates = [
        NEW_DATA_DIR / f"{dataset}.jsonl",
        NEW_DATA_DIR / f"{dataset}.json",
        DATA_DIR / f"{dataset}.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def read_case_file(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = read_json_objects(text, path)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise ValueError(f"{path} must contain a JSON object, JSON array, or JSONL objects")
    return data


def read_json_objects(text: str, path: Path) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    index = 0
    items: list[dict[str, Any]] = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        try:
            item, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError as exc:
            line_number = text.count("\n", 0, index) + 1
            raise ValueError(f"{path}:{line_number} is not valid JSON/JSONL") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{path} must contain JSON objects")
        items.append(item)
        index = end
    return items


def read_file_dataset(dataset: str) -> list[dict[str, Any]]:
    path = dataset_path(dataset)
    data = read_case_file(path)
    return [enrich_case(case, storage_origin="local_file", data_file=path.name, dataset=dataset) for case in data]


def read_persisted_case_map(dataset: str = DEFAULT_DATASET) -> dict[str, dict[str, Any]]:
    if not database_configured():
        return {}
    ensure_db()
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("select case_data from clawtrap_cases where dataset = %s", (dataset,))
            rows = cur.fetchall()
    persisted: dict[str, dict[str, Any]] = {}
    for row in rows:
        case = row[0]
        if isinstance(case, dict) and case.get("id"):
            persisted[str(case["id"])] = case
    return persisted


def read_local_dataset(dataset: str = DEFAULT_DATASET) -> list[dict[str, Any]]:
    local_cases = read_file_dataset(dataset)
    persisted = read_persisted_case_map(dataset)
    merged_cases = []
    for case in local_cases:
        case_id = case.get("id")
        if case_id and str(case_id) in persisted:
            merged = {**case, **persisted[str(case_id)]}
            merged["id"] = case_id
            merged["data_file"] = case.get("data_file") or f"{dataset}.json"
            merged_cases.append(enrich_case(merged, storage_origin="local_file", data_file=merged["data_file"], dataset=dataset))
        else:
            merged_cases.append(enrich_case(case, storage_origin="local_file", data_file=case.get("data_file") or dataset_path(dataset).name, dataset=dataset))
    return merged_cases


def list_datasets() -> list[str]:
    if use_database():
        ensure_db()
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute("select distinct dataset from clawtrap_cases order by dataset")
                names = [row[0] for row in cur.fetchall()]
        return sorted(set(list_file_datasets()) | set(names)) or [DEFAULT_DATASET]
    return list_file_datasets() or [DEFAULT_DATASET]


def read_dataset(dataset: str) -> list[dict[str, Any]]:
    if use_database():
        file_cases = read_file_dataset(dataset) if dataset_path(dataset).exists() else []
        ensure_db()
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute("select case_data from clawtrap_cases where dataset = %s order by updated_at desc", (dataset,))
                db_cases = [row[0] for row in cur.fetchall()]
        merged: dict[str, dict[str, Any]] = {}
        for case in file_cases:
            case_id = case.get("id")
            if case_id:
                merged[case_id] = enrich_case(case, storage_origin="local_file")
        for case in db_cases:
            case_id = case.get("id")
            if case_id:
                merged[case_id] = enrich_case(case, storage_origin="database")
        return sorted(merged.values(), key=lambda item: item.get("updated_at", ""), reverse=True)
    return [enrich_case(case, storage_origin="local_file") for case in read_file_dataset(dataset)]


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
