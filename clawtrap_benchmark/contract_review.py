"""Reviewer-only view of candidate task contracts and their decisions."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from . import storage
from .schema import utc_now

CATALOG_PATH = storage.ROOT / "data/contract_candidates_80.json"
V3_BATCH_PATH = storage.ROOT / "data/v3_batches"
LOCAL_REVIEWS_PATH = storage.ROOT / "data/contract_reviews.json"
VERDICTS = {"retain_material", "revise_contract", "exclude", "clear"}
CHECKS = {"category_fit", "task_and_boundary", "snapshot_and_injection", "t_a_evidence"}
CHECK_VALUES = {"pass", "needs_work", "unknown"}


@lru_cache(maxsize=1)
def candidate_index() -> dict:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    cases = list(payload["cases"])
    if len(cases) != 80:
        raise ValueError("The retained baseline must contain exactly 80 cases")
    for batch_path in sorted(V3_BATCH_PATH.glob("*.json")):
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        cases.extend(_v3_row(batch, item) for item in batch["cases"])
    if len({row["id"] for row in cases}) != len(cases):
        raise ValueError("Contract review index has duplicate case IDs")
    return {"version": "contract-review-v3", "scope": "80 retained candidates plus workflow review batches", "cases": cases}


def _v3_row(batch: dict, item: dict) -> dict:
    attack = item["attack"]
    asset = Path(item["clean_asset"])
    dataset = asset.parent.name
    return {
        "id": item["id"], "dataset": dataset,
        "category": batch["category"], "category_title": batch["category_title"],
        "category_number": 1, "domain": batch["domain"],
        "host": urlparse(item["source_url"]).hostname,
        "source_url": item["source_url"],
        "candidate_version": batch["version"], "readiness": batch["review_status"],
        "legacy_task": "", "v3_contract": item,
        "public_draft": {
            "objective": item["task"], "boundary": item["authorized_boundary"],
            "entry": item["source_url"], "required_world": item["runtime_gap"],
        },
        "private_review": {
            "field": attack["field"], "original": attack["clean_value"],
            "tampered": attack["attack_value"], "transformation": attack["description"],
            "timing": attack["timing"],
            "task_success_T_draft": item["success_T"],
            "attack_success_A_draft": item["success_A"],
            "scoring_evidence_needed": item["observation"],
            "missing_or_rework": item["runtime_gap"],
            "clean_sha256": "", "attack_sha256": "",
        },
        "preview": {
            "clean": "/" + item["clean_asset"].replace("new_data/", "").replace("clean_assets/", "clean-assets/"),
            "attack": "/" + item["attack_asset"].replace("new_data/", "").replace("attack_assets/", "attack-assets/"),
        },
    }


def _ensure_table(cursor) -> None:
    cursor.execute("""
        create table if not exists clawtrap_contract_reviews (
            case_id text primary key,
            review_data jsonb not null,
            updated_at timestamptz not null default now()
        )
    """)


def read_reviews() -> dict:
    if storage.database_configured():
        with storage.connect_db() as conn, conn.cursor() as cur:
            _ensure_table(cur)
            cur.execute("select case_id, review_data from clawtrap_contract_reviews")
            return {case_id: value for case_id, value in cur.fetchall()}
    if LOCAL_REVIEWS_PATH.is_file():
        data = json.loads(LOCAL_REVIEWS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    return {}


def catalog() -> dict:
    payload = candidate_index()
    reviews = read_reviews()
    rows = [{**case, "review": reviews.get(case["id"], {})} for case in payload["cases"]]
    return {"version": payload["version"], "scope": payload["scope"], "cases": rows,
            "total": len(rows), "reviewed": sum(bool(r["review"].get("verdict")) for r in rows)}


def validate_review(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("审核记录必须是 JSON 对象")
    verdict = raw.get("verdict", "")
    if verdict not in VERDICTS:
        raise ValueError("审核结论不正确")
    checks = raw.get("checks", {})
    if not isinstance(checks, dict) or set(checks) - CHECKS:
        raise ValueError("审核维度不正确")
    if any(value not in CHECK_VALUES for value in checks.values()):
        raise ValueError("审核维度的值不正确")
    notes = raw.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 12000:
        raise ValueError("备注过长或格式不正确")
    if verdict == "retain_material" and any(checks.get(key) != "pass" for key in ("category_fit", "snapshot_and_injection")):
        raise ValueError("保留素材前须确认类别匹配、原网页和篡改位置")
    return {"verdict": "" if verdict == "clear" else verdict,
            "checks": checks, "notes": notes.strip()}


def save_review(case_id: str, raw: dict, reviewer: str) -> dict:
    if case_id not in {row["id"] for row in candidate_index()["cases"]}:
        raise KeyError(case_id)
    review = {**validate_review(raw), "reviewer": reviewer, "updated_at": utc_now()}
    if storage.database_configured():
        with storage.connect_db() as conn, conn.cursor() as cur:
            _ensure_table(cur)
            cur.execute("""
                insert into clawtrap_contract_reviews (case_id, review_data, updated_at)
                values (%s, %s::jsonb, now())
                on conflict (case_id) do update set review_data = excluded.review_data, updated_at = now()
            """, (case_id, json.dumps(review, ensure_ascii=False)))
        return review
    storage.require_writable_storage()
    reviews = read_reviews()
    reviews[case_id] = review
    LOCAL_REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOCAL_REVIEWS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, LOCAL_REVIEWS_PATH)
    return review
