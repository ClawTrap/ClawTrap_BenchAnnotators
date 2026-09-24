#!/usr/bin/env python3
"""Audit the separation between Agent tasks and private interception targets."""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    index = json.loads((ROOT / "data/v3_mitm_targets.json").read_text(encoding="utf-8"))["cases"]
    search_index = json.loads((ROOT / "data/v3_controlled_search_results.json").read_text(encoding="utf-8"))["cases"]
    workspace_index = json.loads((ROOT / "data/v3_public_workspace_files.json").read_text(encoding="utf-8"))
    service_index = json.loads((ROOT / "data/v3_public_service_seeds.json").read_text(encoding="utf-8"))["cases"]
    form_index = json.loads((ROOT / "data/v3_task_form_triage.json").read_text(encoding="utf-8"))["cases"]
    failures = []
    cases = []
    for path in sorted((ROOT / "data/v3_batches").glob("*.json")):
        cases.extend(json.loads(path.read_text(encoding="utf-8"))["cases"])
    if set(index) != {case["id"] for case in cases}:
        failures.append("MITM index does not cover exactly the 350 review cases")
    if set(search_index) != {case["id"] for case in cases}:
        failures.append("Controlled search index does not cover exactly the 350 review cases")
    if not set(service_index) <= {case["id"] for case in cases}:
        failures.append("Public service seed has an unknown case")
    if set(form_index) != {case["id"] for case in cases}:
        failures.append("Task-form triage does not cover exactly the 350 review cases")
    if {cid for cid, row in form_index.items() if row.get("decision") == "redesigned_isolated_action"} != set(service_index):
        failures.append("Redesigned action triage differs from public service objects")
    for case in cases:
        task = case["task"]
        if re.search(r"https?://", task):
            failures.append(f"{case['id']}: task contains a direct URL")
        for field in ("authorized_boundary", "timing_protocol"):
            if re.search(r"https?://", json.dumps(case.get(field, ""), ensure_ascii=False)):
                failures.append(f"{case['id']}: Agent-visible {field} contains a direct URL")
        if form_index.get(case["id"], {}).get("task_sha256") != hashlib.sha256(task.encode("utf-8")).hexdigest():
            failures.append(f"{case['id']}: task-form triage is stale")
        mitm = index.get(case["id"], {"status": "missing_index", "targets": []})
        if mitm["status"] != "configured":
            failures.append(f"{case['id']}: interception is {mitm['status']}")
        urls = {case.get("source_url", ""), *(target["url"] for target in mitm["targets"])}
        result_urls = {row["url"] for row in search_index.get(case["id"], {}).get("results", [])}
        if not result_urls:
            failures.append(f"{case['id']}: no controlled search result")
        for target in mitm["targets"]:
            if "GET" in target["methods"] and target["url"] not in result_urls:
                failures.append(f"{case['id']}: GET target is absent from controlled search results")
        for url in sorted(urls - {""}):
            if url in task:
                failures.append(f"{case['id']}: task exposes {url}")
        for file in workspace_index.get(case["id"], []):
            content = (ROOT / file["source"]).read_text(encoding="utf-8")
            for url in sorted({target["url"] for target in mitm["targets"]}):
                if url in content:
                    failures.append(f"{case['id']}: initial file {file['path']} exposes {url}")
        service = service_index.get(case["id"])
        if service:
            if service.get("status") != "pending_runtime_e2e" or not isinstance(service.get("initial"), dict):
                failures.append(f"{case['id']}: invalid public service initial object")
            initial_content = json.dumps(service.get("initial", {}), ensure_ascii=False)
            for url in sorted({target["url"] for target in mitm["targets"]}):
                if url in initial_content:
                    failures.append(f"{case['id']}: service initial object exposes {url}")
    print(f"Audited {len(cases)} cases; found {len(failures)} URL-discovery gaps")
    for failure in failures:
        print(failure)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
