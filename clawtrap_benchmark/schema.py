from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .constants import ATTACK_TYPES, ATTACK_TYPES_BY_TASK_TYPE, INTERACTIVE_FORMS, REQUIRED_CASE_FIELDS, TASK_TYPES


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        normalized = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    normalized.append(stripped)
        return normalized
    return []


def nested_text(value: Any, *keys: str) -> str:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def has_new_schema(raw: dict[str, Any]) -> bool:
    return any(key in raw for key in ("scenario", "benign_objective", "protected_assets", "attack", "policies", "expected_behavior", "graders"))


def sync_new_schema_aliases(case: dict[str, Any]) -> None:
    scenario = case.get("scenario") if isinstance(case.get("scenario"), dict) else {}
    attack = case.get("attack") if isinstance(case.get("attack"), dict) else {}

    domain = str(scenario.get("domain") or "").strip()
    workflow = str(scenario.get("workflow") or "").strip()
    if domain:
        case["task_type"] = domain
    if workflow:
        case["attack_type"] = workflow

    benign_objective = str(case.get("benign_objective") or "").strip()
    if benign_objective:
        case["task"] = benign_objective

    attack_description = str(attack.get("attack_description") or "").strip()
    if attack_description:
        case["attack_method"] = attack_description

    expected_behavior = normalize_list(case.get("expected_behavior"))
    if expected_behavior:
        case["success_states"] = expected_behavior

    if case.get("task_type") and isinstance(case.get("scenario"), dict):
        case["scenario"]["domain"] = case["task_type"]
    if case.get("attack_type") and isinstance(case.get("scenario"), dict):
        case["scenario"]["workflow"] = case["attack_type"]
    if case.get("task") and "benign_objective" in case:
        case["benign_objective"] = case["task"]
    if case.get("attack_method") and isinstance(case.get("attack"), dict):
        case["attack"]["attack_description"] = case["attack_method"]
    if case.get("success_states") and "expected_behavior" in case:
        case["expected_behavior"] = case["success_states"]


def normalize_case(raw: dict[str, Any], *, owner: str | None = None, source: str | None = None) -> dict[str, Any]:
    case = deepcopy(raw)
    schema_version = "v2" if has_new_schema(case) else str(case.get("schema_version") or "v1")
    if schema_version == "v2":
        sync_new_schema_aliases(case)
    if not case.get("id"):
        case["id"] = f"ct-{uuid4().hex[:12]}"
    case["schema_version"] = schema_version
    case.setdefault("status", "draft")
    case.setdefault("owner", owner or "llm_seed")
    case.setdefault("source", source or case.get("source", "manual"))
    case.setdefault("created_at", utc_now())
    case["updated_at"] = utc_now()

    for key in ("success_states", "failure_states", "interactive_form", "metadata", "protected_assets", "policies", "expected_behavior", "graders"):
        case[key] = normalize_list(case.get(key))
    for key in ("task", "target", "task_type", "attack_method", "logic", "attack_type"):
        case[key] = str(case.get(key, "")).strip()
    if "scenario" in case and not isinstance(case.get("scenario"), dict):
        case["scenario"] = {"workflow": str(case.get("scenario", "")).strip()}
    if schema_version == "v2":
        sync_new_schema_aliases(case)

    if "generation_batch" in raw:
        case["generation_batch"] = raw["generation_batch"]
    return case


def validate_case(case: dict[str, Any], *, for_submit: bool = False) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_CASE_FIELDS:
        value = case.get(field)
        if isinstance(value, list):
            if not value:
                errors.append(f"{field} 不能为空")
        elif not str(value or "").strip():
            errors.append(f"{field} 不能为空")

    schema_version = str(case.get("schema_version") or "")
    taxonomy_required = schema_version != "v2"

    if taxonomy_required and case.get("task_type") and case["task_type"] not in TASK_TYPES:
        errors.append("task_type 必须是新的 8 个任务大类之一")
    if taxonomy_required and case.get("attack_type") and case["attack_type"] not in ATTACK_TYPES:
        errors.append("attack_type 必须是新的 40 个细分攻击场景之一")
    if taxonomy_required and case.get("task_type") in ATTACK_TYPES_BY_TASK_TYPE and case.get("attack_type"):
        valid_attacks = ATTACK_TYPES_BY_TASK_TYPE[case["task_type"]]
        if case["attack_type"] not in valid_attacks:
            errors.append("attack_type 必须属于当前 task_type 下的 5 个细分类别之一")

    forms = normalize_list(case.get("interactive_form"))
    invalid_forms = [] if schema_version == "v2" else [form for form in forms if form not in INTERACTIVE_FORMS]
    if invalid_forms:
        errors.append(f"interactive_form 包含非法选项: {', '.join(invalid_forms)}")
    if len(forms) != len(set(forms)):
        errors.append("interactive_form 不能重复")

    if for_submit:
        if len(case.get("task", "")) < 8:
            errors.append("task 需要是完整清晰的任务描述")
        if len(case.get("target", "")) < 6:
            errors.append("target 需要清楚说明任务目标")
        if len(case.get("attack_method", "")) < 12:
            errors.append("attack_method 需要清楚说明攻击植入位置和内容")
        if len(case.get("logic", "")) < 12:
            errors.append("logic 需要解释攻击价值和成功/失败判定")
        if len(case.get("success_states", [])) < 2:
            errors.append("success_states 至少需要 2 条")
        if len(case.get("failure_states", [])) < 2:
            errors.append("failure_states 至少需要 2 条")
        if len(case.get("metadata", [])) < 1:
            errors.append("metadata 至少需要 1 条")

    return errors
