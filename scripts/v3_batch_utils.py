"""Small helpers for review-only v3 contracts backed by archived HTML."""

from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


def old_case(dataset: str) -> dict:
    record = json.loads((ROOT / f"new_data/{dataset}.jsonl").read_text(encoding="utf-8"))
    implementation = record["attack_implementation"][0]
    source_url = next((entry.removeprefix("原网页链接：") for entry in record.get("metadata", [])
                       if entry.startswith("原网页链接：")), "")
    if not source_url:
        task_path = ROOT / record["task_files"][0]["path"]
        task = json.loads(task_path.read_text(encoding="utf-8"))
        source_url = task.get("download_page") or task.get("page_url") or task.get("article_page") or ""
    if urlparse(source_url).scheme != "https":
        raise ValueError(f"Missing HTTPS source URL: {dataset}")
    facts = re.findall(r"`([^`]+)`", record["attack"]["transformation"])
    return {
        "reuses": dataset,
        "source_url": source_url,
        "clean_asset": "new_data" + implementation["before_url"].replace("clean-assets/", "clean_assets/", 1),
        "attack_asset": "new_data" + implementation["url"].replace("attack-assets/", "attack_assets/", 1),
        "source_archive": f"new_data/source_archives/{dataset}",
        "field": record["attack"]["target"],
        "description": record["attack"]["transformation"],
        "clean_value": facts[0] if facts else "",
        "attack_value": facts[1] if len(facts) > 1 else "",
    }


def make_case(case_id: str, source: dict, spec: dict) -> dict:
    url = source["source_url"]
    for key in ("clean_asset", "attack_asset"):
        if not (ROOT / source[key]).is_file():
            raise ValueError(f"Missing {key}: {case_id}")
    if not (ROOT / source["source_archive"]).is_dir():
        raise ValueError(f"Missing source archive: {case_id}")
    task = spec["task"].replace("{SOURCE_URL}", url)
    if url not in task:
        raise ValueError(f"Task lacks exact target URL: {case_id}")
    attack = {
        "form": spec.get("form", "selective substitution"),
        "position": spec.get("position", "target webpage"),
        "evidence_structure": spec.get("evidence_structure", "single source"),
        "risk": spec.get("risk", "read-only"),
        "timing": spec.get("timing", "before decision; first matched response"),
        "field": source["field"],
        "clean_value": source["clean_value"],
        "attack_value": source["attack_value"],
        "description": source["description"],
    }
    for key in ("form", "position", "field", "clean_value", "attack_value", "description"):
        if not attack[key]:
            raise ValueError(f"Missing attack {key}: {case_id}")
    return {
        "id": case_id,
        "scenario": spec["scenario"],
        **{key: source[key] for key in ("reuses", "source_url", "clean_asset", "attack_asset", "source_archive")
           if key in source},
        "task": task,
        "deliverable": spec["deliverable"],
        "output_format": spec["output_format"],
        "authorized_boundary": spec["authorized_boundary"],
        "attack": attack,
        "success_T": spec["success_T"],
        "success_A": spec["success_A"],
        "observation": spec["observation"],
        "runtime_gap": spec.get("runtime_gap", "需在受控浏览环境中按目标 URL 注入 HTML，并解析最终产物与浏览日志；目前仅供审核。"),
    }


def write_batch(filename: str, *, batch: str, category: str, category_number: int,
                category_title: str, domain: str, cases: list[dict]) -> None:
    if len(cases) != 10 or len({case["id"] for case in cases}) != 10:
        raise ValueError(f"Batch {batch} must contain ten distinct cases")
    payload = {
        "version": "workflow-contract-v3", "batch": batch,
        "review_status": "draft_not_run_ready", "category": category,
        "category_number": category_number, "category_title": category_title,
        "domain": domain, "cases": cases,
    }
    target = ROOT / "data/v3_batches" / filename
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
