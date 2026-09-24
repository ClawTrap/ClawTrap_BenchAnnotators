"""Reviewer-only view of candidate task contracts and their decisions."""
from __future__ import annotations

import json
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from . import storage
from .schema import utc_now

V3_BATCH_PATH = storage.ROOT / "data/v3_batches"
LOCAL_REVIEWS_PATH = storage.ROOT / "data/contract_reviews.json"
LOCAL_CONTENT_PATH = storage.ROOT / "data/contract_content_edits.json"
LEGACY_TASK_HASHES_PATH = storage.ROOT / "data/v3_legacy_task_hashes.json"
LEGACY_BOUNDARY_HASHES_PATH = storage.ROOT / "data/v3_legacy_boundary_hashes.json"
PRE_REBALANCE_HASHES_PATH = storage.ROOT / "data/v3_pre_rebalance_fingerprints.json"
PUBLIC_WORKSPACE_INDEX_PATH = storage.ROOT / "data/v3_public_workspace_files.json"
MITM_TARGETS_PATH = storage.ROOT / "data/v3_mitm_targets.json"
CONTROLLED_SEARCH_PATH = storage.ROOT / "data/v3_controlled_search_results.json"
PUBLIC_SERVICE_SEEDS_PATH = storage.ROOT / "data/v3_public_service_seeds.json"
TASK_FORM_TRIAGE_PATH = storage.ROOT / "data/v3_task_form_triage.json"
CONTENT_FIELDS = {
    "scenario", "task", "deliverable", "output_format", "authorized_boundary",
    "success_T", "success_A", "observation", "runtime_gap",
}
LABEL_FIELDS = {"category", "task_action", "authority_direction", "form", "position", "evidence_structure", "risk", "granularity", "timing"}
STANDARD_LABELS = {
    "task_action": {"retrieve", "judge", "select", "compose", "modify", "prepare",
                    "transfer", "execute", "communicate", "authorize"},
    "authority_direction": {"READ", "WRITE", "ACT", "SEND", "RECEIVE", "GRANT"},
    "form": {"full-page replacement", "iframe/popup injection", "selective substitution",
             "redirect rewriting", "API JSON mutation", "file replacement", "mixed benign–malicious content"},
    "position": {"discovery result or citation", "technical reference page",
                 "policy or guidance page", "record or action page", "API response",
                 "download file", "navigation or error state", "asynchronous update"},
    "evidence_structure": {"single source", "multiple polluted sources", "trusted–polluted conflict",
                           "polluted majority / trusted minority", "internal policy / external page conflict",
                           "cache / live page conflict"},
    "risk": {"read-only", "reversible write", "cross-system write", "external communication",
             "data disclosure", "permission change", "financial action", "irreversible execution",
             "irreversible workflow", "supply-chain execution", "privilege change"},
    "granularity": {"page", "component", "sentence", "field", "single character", "link",
                    "timestamp", "numeric value"},
    "timing": {"first step", "during verification", "before decision", "before confirmation",
               "repeated across turns", "delayed trigger", "memory contamination then trigger"},
}
ACTION_DIRECTIONS = {
    "retrieve": "READ", "judge": "READ", "select": "READ", "compose": "WRITE",
    "modify": "WRITE", "prepare": "WRITE", "transfer": "RECEIVE", "execute": "ACT",
    "communicate": "SEND", "authorize": "GRANT",
}


@lru_cache(maxsize=1)
def candidate_index() -> dict:
    cases = []
    for batch_path in sorted(V3_BATCH_PATH.glob("*.json")):
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        cases.extend(_v3_row(batch, item) for item in batch["cases"])
    if len({row["id"] for row in cases}) != len(cases):
        raise ValueError("Contract review index has duplicate case IDs")
    return {"version": "contract-review-v3", "scope": "new workflow review batches only", "cases": cases}


def label_options() -> dict:
    cases = candidate_index()["cases"]
    categories = {row["category"]: {"key": row["category"], "title": row["category_title"],
                                   "domain": row["domain"], "number": row["category_number"]}
                  for row in cases}
    options = {"categories": sorted(categories.values(), key=lambda item: item["number"])}
    for field in LABEL_FIELDS - {"category"}:
        observed = {(row["v3_contract"][field] if field in {"task_action", "authority_direction"}
                     else row["v3_contract"]["attack"][field]) for row in cases}
        options[field] = sorted(STANDARD_LABELS[field] if field in {"task_action", "authority_direction", "position", "risk", "granularity", "timing"}
                                else STANDARD_LABELS[field] | observed)
    return options


@lru_cache(maxsize=1)
def _public_workspace_index() -> dict:
    return json.loads(PUBLIC_WORKSPACE_INDEX_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _mitm_targets_index() -> dict:
    return json.loads(MITM_TARGETS_PATH.read_text(encoding="utf-8"))["cases"]


@lru_cache(maxsize=1)
def _controlled_search_index() -> dict:
    return json.loads(CONTROLLED_SEARCH_PATH.read_text(encoding="utf-8"))["cases"]


@lru_cache(maxsize=1)
def _public_service_seeds_index() -> dict:
    return json.loads(PUBLIC_SERVICE_SEEDS_PATH.read_text(encoding="utf-8"))["cases"]


@lru_cache(maxsize=1)
def _task_form_triage_index() -> dict:
    return json.loads(TASK_FORM_TRIAGE_PATH.read_text(encoding="utf-8"))["cases"]


def _public_workspace_files(case_id: str) -> list[dict[str, str]]:
    files = []
    for entry in _public_workspace_index().get(case_id, []):
        source = entry["source"]
        if not source.startswith(("new_data/task_assets/", "new_data/workspace_seeds/")) or ".." in Path(source).parts:
            raise ValueError(f"Invalid public workspace file path: {source}")
        data = (storage.ROOT / source).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Public workspace file does not match review index: {source}")
        files.append({"path": entry["path"], "content": data.decode("utf-8")})
    return files


def _v3_row(batch: dict, item: dict) -> dict:
    attack = item["attack"]
    asset = Path(item["clean_asset"])
    dataset = asset.parent.name
    return {
        "id": item["id"], "batch": batch["batch"], "dataset": dataset,
        "category": batch["category"], "category_title": batch["category_title"],
        "category_number": batch["category_number"], "domain": batch["domain"],
        "host": urlparse(item["source_url"]).hostname,
        "source_url": item["source_url"],
        "candidate_version": batch["version"], "readiness": batch["review_status"],
        "legacy_task": "", "v3_contract": item,
        "workspace_files": _public_workspace_files(item["id"]),
        "mitm": _mitm_targets_index()[item["id"]],
        "controlled_search": _controlled_search_index()[item["id"]],
        "service_initial": _public_service_seeds_index().get(item["id"]),
        "task_form_triage": _task_form_triage_index()[item["id"]],
        "public_draft": {
            "objective": item["task"], "boundary": item["authorized_boundary"],
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


def _ensure_content_table(cursor) -> None:
    cursor.execute("""
        create table if not exists clawtrap_contract_content_edits (
            case_id text primary key,
            content_data jsonb not null,
            revision integer not null,
            updated_at timestamptz not null default now()
        )
    """)


def read_content_edits() -> dict:
    if storage.database_configured():
        with storage.connect_db() as conn, conn.cursor() as cur:
            _ensure_content_table(cur)
            cur.execute("select case_id, content_data from clawtrap_contract_content_edits")
            return {case_id: value for case_id, value in cur.fetchall()}
    if LOCAL_CONTENT_PATH.is_file():
        data = json.loads(LOCAL_CONTENT_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    return {}


@lru_cache(maxsize=1)
def _legacy_task_hashes() -> dict[str, str]:
    return json.loads(LEGACY_TASK_HASHES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _legacy_boundary_hashes() -> dict[str, str]:
    return json.loads(LEGACY_BOUNDARY_HASHES_PATH.read_text(encoding="utf-8"))


def _effective_edit_fields(row: dict, fields: dict) -> dict:
    fields = dict(fields)
    for key, hashes in (("task", _legacy_task_hashes()),
                        ("authorized_boundary", _legacy_boundary_hashes())):
        value = fields.get(key)
        if value and hashlib.sha256(value.encode("utf-8")).hexdigest() == hashes.get(row["id"]):
            fields.pop(key)
    return fields


def _source_fingerprint(row: dict) -> str:
    source = {"contract": row["v3_contract"], "category": row["category"],
              "domain": row["domain"], "candidate_version": row["candidate_version"]}
    encoded = json.dumps(source, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@lru_cache(maxsize=1)
def _pre_rebalance_hashes() -> dict[str, str]:
    if PRE_REBALANCE_HASHES_PATH.is_file():
        return json.loads(PRE_REBALANCE_HASHES_PATH.read_text(encoding="utf-8"))["cases"]
    return {}


def _current_position_label(row: dict, value: str) -> str:
    former = {
        "search results": "discovery result or citation",
        "third-party citation": "discovery result or citation",
        "checkout page": "record or action page",
        "login page": "navigation or error state",
        "error page": "navigation or error state",
        "redirect chain": "navigation or error state",
    }
    if value == "target webpage":
        return row["v3_contract"]["attack"]["position"]
    return former.get(value, value)


def _edit_matches_source(row: dict, edit: dict) -> bool:
    prior = edit.get("base_source_sha256")
    return bool(prior) and (prior == _source_fingerprint(row)
                            or prior == _pre_rebalance_hashes().get(row["id"]))


def _edited_row(row: dict, edit: dict | None) -> dict:
    if not edit:
        return {**row, "content_edit": {"status": "source", "revision": 0}}
    if not _edit_matches_source(row, edit):
        return {**row, "content_edit": {"status": "stale",
                                      "revision": edit.get("revision", 0),
                                      "editor": edit.get("editor", ""),
                                      "updated_at": edit.get("updated_at", "")}}
    labels = dict(edit.get("labels", {}))
    if "position" in labels:
        labels["position"] = _current_position_label(row, labels["position"])
        if labels["position"] not in STANDARD_LABELS["position"]:
            labels.pop("position")
    contract = {**row["v3_contract"], **_effective_edit_fields(row, edit.get("fields", {}))}
    action = labels.get("task_action")
    if action in STANDARD_LABELS["task_action"]:
        contract["task_action"] = action
        contract["action_chain"] = [*contract["action_chain"][:-1], action]
        if action != row["v3_contract"]["task_action"]:
            contract["authority_direction"] = ACTION_DIRECTIONS[action]
    direction = labels.get("authority_direction")
    if direction in STANDARD_LABELS["authority_direction"]:
        contract["authority_direction"] = direction
    attack = {**contract["attack"], **{key: value for key, value in labels.items()
                                      if key not in {"category", "task_action", "authority_direction"} and
                                      (key not in {"risk", "granularity", "timing"}
                                       or value in STANDARD_LABELS[key])}}
    contract["attack"] = attack
    category = next((item for item in label_options()["categories"] if item["key"] == labels.get("category")), None)
    public = {**row["public_draft"], "objective": contract["task"],
              "boundary": contract["authorized_boundary"]}
    private = {**row["private_review"], "task_success_T_draft": contract["success_T"],
               "attack_success_A_draft": contract["success_A"],
               "scoring_evidence_needed": contract["observation"],
               "missing_or_rework": contract["runtime_gap"], "timing": attack["timing"]}
    return {**row, "v3_contract": contract, "public_draft": public,
            "private_review": private,
            **({"category": category["key"], "category_title": category["title"],
                "category_number": category["number"], "domain": category["domain"]} if category else {}),
            "content_edit": {key: edit[key] for key in ("status", "revision", "editor", "updated_at")}}


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
    edits = read_content_edits()
    rows = [{**_edited_row(case, edits.get(case["id"])),
             "review": _normalized_review(reviews.get(case["id"]))}
            for case in payload["cases"]]
    return {"version": payload["version"], "scope": payload["scope"], "cases": rows,
            "total": len(rows), "selected": sum(r["review"]["selected"] for r in rows),
            "confirmed": sum(r["content_edit"]["status"] == "confirmed" for r in rows),
            "content_writable": not storage.is_vercel_runtime() or storage.database_configured(),
            "label_options": label_options()}


def _normalized_review(value: dict | None) -> dict:
    value = value or {}
    return {"selected": value.get("selected", value.get("verdict") == "retain_material"),
            "reviewer": value.get("reviewer", ""), "updated_at": value.get("updated_at", "")}


def save_content_edit(case_id: str, raw: dict, editor: str) -> dict:
    source = next((row for row in candidate_index()["cases"] if row["id"] == case_id), None)
    if source is None:
        raise KeyError(case_id)
    if not isinstance(raw, dict) or raw.get("status") not in {"draft", "confirmed"}:
        raise ValueError("编辑状态不正确")
    fields, labels = raw.get("fields", {}), raw.get("labels", {})
    if (not isinstance(fields, dict) or not isinstance(labels, dict)
            or (not fields and not labels) or set(fields) - CONTENT_FIELDS or set(labels) - LABEL_FIELDS):
        raise ValueError("编辑字段为空或包含不可修改字段")
    for key, value in fields.items():
        limit = 12000 if key == "task" else 4000
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{key} 不能为空或超过长度限制")
    options = label_options()
    for key, value in labels.items():
        allowed = {item["key"] for item in options["categories"]} if key == "category" else set(options[key])
        if not isinstance(value, str) or value not in allowed:
            raise ValueError(f"{key} 标签不在可选范围内")
    expected = raw.get("revision")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise ValueError("版本号不正确")
    current = read_content_edits().get(case_id)
    if expected != (current["revision"] if current else 0):
        raise ValueError("题目已由其他审核员修改，请刷新后重试")
    active = current if current and _edit_matches_source(source, current) else None
    original = {key: source["v3_contract"][key] for key in CONTENT_FIELDS}
    merged_fields = {**original, **(_effective_edit_fields(source, active.get("fields", {})) if active else {}),
                     **{key: value.strip() for key, value in fields.items()}}
    inherited_labels = dict(active.get("labels", {}) if active else {})
    if "position" in inherited_labels:
        inherited_labels["position"] = _current_position_label(source, inherited_labels["position"])
    merged_labels = {**inherited_labels, **labels}
    merged_labels = {key: value for key, value in merged_labels.items()
                     if key not in {"position", "risk", "granularity", "timing"}
                     or value in STANDARD_LABELS[key]}
    record = {"fields": merged_fields, "labels": merged_labels,
              "status": raw["status"], "revision": expected + 1,
              "editor": editor, "updated_at": utc_now(),
              "base_source_sha256": _source_fingerprint(source)}
    if storage.database_configured():
        with storage.connect_db() as conn, conn.cursor() as cur:
            _ensure_content_table(cur)
            cur.execute("""
                insert into clawtrap_contract_content_edits (case_id, content_data, revision, updated_at)
                values (%s, %s::jsonb, %s, now())
                on conflict (case_id) do update set
                    content_data = excluded.content_data,
                    revision = excluded.revision,
                    updated_at = now()
                where clawtrap_contract_content_edits.revision = %s
                returning revision
            """, (case_id, json.dumps(record, ensure_ascii=False), expected + 1, expected))
            if cur.fetchone() is None:
                raise ValueError("题目已由其他审核员修改，请刷新后重试")
        return record
    storage.require_writable_storage()
    edits = read_content_edits()
    edits[case_id] = record
    LOCAL_CONTENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOCAL_CONTENT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(edits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, LOCAL_CONTENT_PATH)
    return record


def confirmed_export() -> dict:
    edits = read_content_edits()
    rows = []
    for row in candidate_index()["cases"]:
        edit = edits.get(row["id"])
        if edit and edit["status"] == "confirmed" and _edit_matches_source(row, edit):
            effective = _edited_row(row, edit)
            rows.append({"batch": row["batch"], "category": effective["category"],
                         "domain": effective["domain"], "case": effective["v3_contract"],
                         "revision": edit["revision"], "confirmed_at": edit["updated_at"]})
    return {"version": "contract-content-export-v1", "cases": rows}


def selected_export() -> dict:
    edits, reviews = read_content_edits(), read_reviews()
    rows = []
    for source in candidate_index()["cases"]:
        if not _normalized_review(reviews.get(source["id"]))["selected"]:
            continue
        effective = _edited_row(source, edits.get(source["id"]))
        rows.append({"batch": source["batch"], "category": effective["category"],
                     "domain": effective["domain"], "case": effective["v3_contract"],
                     "revision": effective["content_edit"]["revision"]})
    return {"version": "selected-workflow-contracts-v1", "cases": rows}


def validate_review(raw: dict) -> dict:
    if not isinstance(raw, dict) or set(raw) != {"selected"} or type(raw["selected"]) is not bool:
        raise ValueError("仅接受入选状态 true 或 false")
    return {"selected": raw["selected"]}


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
