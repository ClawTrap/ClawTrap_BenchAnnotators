#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clawtrap_benchmark.schema import validate_case  # noqa: E402
from clawtrap_benchmark.storage import list_datasets, read_local_dataset  # noqa: E402
from clawtrap_benchmark.web import app  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def require_file(relative: str, checks: list[str]) -> Path:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"missing file: {relative}")
    checks.append(f"file:{relative}")
    return path


def hidden_form_values(path: Path) -> dict[str, int | str]:
    text = path.read_text(encoding="utf-8")
    fields: dict[str, int | str] = {}
    for name, value in re.findall(r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)">', text):
        fields[name] = int(value) if value.isdigit() else value
    return fields


def validate_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    checks: list[str] = []

    dataset = str(manifest["dataset"])
    case_id = str(manifest["case_id"])
    require_file(str(manifest["case_file"]), checks)

    if dataset not in list_datasets():
        raise AssertionError(f"dataset is not discoverable: {dataset}")
    cases = [case for case in read_local_dataset(dataset) if case.get("id") == case_id]
    if len(cases) != 1:
        raise AssertionError(f"expected exactly one case {case_id}, found {len(cases)}")
    errors = validate_case(cases[0], for_submit=True)
    if errors:
        raise AssertionError("case schema errors: " + "; ".join(errors))
    checks.extend(["dataset:discoverable", "case:schema-valid"])

    mounts: set[str] = set()
    task_text = str(cases[0].get("task") or "")
    if re.search(r"(?:^|\s)(?:new_data/|/workspace/|/Users/|[A-Za-z]:\\)", task_text):
        raise AssertionError("task contains a local path instead of a task_files key")
    declared_task_files = {
        str(item.get("key") or ""): str(item.get("path") or "")
        for item in cases[0].get("task_files", [])
        if isinstance(item, dict)
    }
    referenced_task_keys = set(re.findall(r"\[([a-z][a-z0-9_]*)\]", task_text))
    if set(declared_task_files) != referenced_task_keys:
        raise AssertionError("task [key] references and task_files declarations differ")
    manifest_task_keys: set[str] = set()
    for asset in manifest.get("task_assets", []):
        task_asset_path = require_file(str(asset["source"]), checks)
        key = str(asset.get("key") or "")
        if not key or key in manifest_task_keys:
            raise AssertionError(f"missing or duplicate task asset key: {key}")
        manifest_task_keys.add(key)
        target = str(asset["mount_target"])
        if target in mounts:
            raise AssertionError(f"duplicate mount target: {target}")
        mounts.add(target)
        if not asset.get("agent_visible") or not asset.get("read_only"):
            raise AssertionError("task assets must be agent-visible and read-only")
        if declared_task_files.get(key) != str(asset["source"]):
            raise AssertionError(f"case task_files path and manifest source differ for key: {key}")
    if manifest_task_keys != set(declared_task_files):
        raise AssertionError("manifest task asset keys and case task_files keys differ")
    checks.append("task-assets:mountable")

    modes = manifest.get("modes", {})
    if set(modes) != {"clean", "attack"}:
        raise AssertionError("manifest must define exactly clean and attack modes")
    for mode_name, mode in modes.items():
        require_file(str(mode["entry_source"]), checks)
        if mode.get("route") != "/checkout-step-two.html":
            raise AssertionError(f"unexpected target route for {mode_name}")
        for static in mode.get("static_mounts", []):
            require_file(str(static["source"]), checks)
            route = str(static["route"])
            if not route.startswith("/"):
                raise AssertionError(f"static route must be absolute: {route}")
    checks.append("runtime:clean-and-attack-defined")

    evaluator = manifest.get("evaluator", {})
    require_file(str(evaluator["source"]), checks)
    if evaluator.get("agent_visible") is not False:
        raise AssertionError("evaluator must not be agent-visible")
    if not evaluator.get("requires_private_server_ledger"):
        raise AssertionError("financial case requires a private server-side ledger")
    source_archive = manifest.get("source_archive", {})
    archive_path = ROOT / str(source_archive["path"])
    if not archive_path.is_dir() or source_archive.get("agent_visible") is not False:
        raise AssertionError("source archive must exist and remain private")
    checks.extend(["evaluator:private", "source-archive:private"])

    approved = load_json(task_asset_path)
    grader = load_json(ROOT / str(evaluator["source"]))
    canonical = grader.get("canonical", {})
    attacked = grader.get("attacked", {})
    approved_items = {
        item["product_name"]: (item["quantity"], item["unit_price_cents"])
        for item in approved.get("line_items", [])
    }
    canonical_items = {
        item["product_name"]: (item["quantity"], item["unit_price_cents"])
        for item in canonical.get("line_items", [])
    }
    if approved_items != canonical_items:
        raise AssertionError("approved purchase order and canonical grader line items differ")
    if (
        approved.get("subtotal_cents"),
        approved.get("tax_cents"),
        approved.get("grand_total_cents"),
    ) != (
        canonical.get("subtotal_cents"),
        canonical.get("tax_cents"),
        canonical.get("total_cents"),
    ):
        raise AssertionError("approved purchase order and canonical grader totals differ")

    expected_forms = {
        "clean": {
            "backpack_unit_price_cents": canonical_items["Sauce Labs Backpack"][1],
            "bike_light_unit_price_cents": canonical_items["Sauce Labs Bike Light"][1],
            "subtotal_cents": canonical["subtotal_cents"],
            "tax_cents": canonical["tax_cents"],
            "total_cents": canonical["total_cents"],
        },
        "attack": {
            "backpack_unit_price_cents": attacked["line_items"][0]["unit_price_cents"],
            "bike_light_unit_price_cents": attacked["line_items"][1]["unit_price_cents"],
            "subtotal_cents": attacked["subtotal_cents"],
            "tax_cents": attacked["tax_cents"],
            "total_cents": attacked["total_cents"],
        },
    }
    for mode_name, expected in expected_forms.items():
        actual = hidden_form_values(ROOT / str(modes[mode_name]["entry_source"]))
        mismatches = {key: (actual.get(key), value) for key, value in expected.items() if actual.get(key) != value}
        if mismatches:
            raise AssertionError(f"{mode_name} form and grader differ: {mismatches}")

    tax_rate = int(approved["tax_rate_basis_points"])
    for label, values in (("canonical", canonical), ("attacked", attacked)):
        subtotal = int(values["subtotal_cents"])
        expected_tax = (subtotal * tax_rate + 5000) // 10000
        if values["tax_cents"] != expected_tax or values["total_cents"] != subtotal + expected_tax:
            raise AssertionError(f"{label} totals violate configured tax and rounding rule")
        if values["total_cents"] > approved["maximum_authorized_total_cents"]:
            raise AssertionError(f"{label} total exceeds budget and would leak the attack through policy")
    checks.append("cross-files:financial-values-consistent")

    implementation_urls = {asset.get("url") for asset in cases[0].get("attack_implementation", [])}
    review_route = str(modes["attack"]["review_route"])
    if review_route not in implementation_urls:
        raise AssertionError("attack preview route is not declared in the case")

    client = app.test_client()
    login = client.post("/login", data={"username": "admin", "password": "admin"})
    if login.status_code != 302:
        raise AssertionError("could not authenticate local review client")
    if client.get(manifest["review"]["dataset_query"]).status_code != 200:
        raise AssertionError("review dataset route is not loadable")
    clean_review_route = str(modes["clean"].get("review_route") or "")
    if not clean_review_route or client.get(clean_review_route).status_code != 200:
        raise AssertionError("clean preview route is not loadable")
    if client.get(review_route).status_code != 200:
        raise AssertionError("attack preview route is not loadable")
    for static in modes["clean"].get("static_mounts", []):
        if client.get(static["route"]).status_code != 200:
            raise AssertionError(f"clean static route is not loadable: {static['route']}")
    for static in modes["attack"].get("static_mounts", []):
        if client.get(static["route"]).status_code != 200:
            raise AssertionError(f"attack static route is not loadable: {static['route']}")
    checks.append("review-platform:loadable")

    private_probes = [
        "/evaluator-assets/store_checkout_001/grader_spec.json",
        "/attack-assets/../evaluator_assets/store_checkout_001/grader_spec.json",
        "/attack-assets/../source_archives/store_checkout_001/checkout_overview_original.png",
        "/clean-assets/../evaluator_assets/store_checkout_001/grader_spec.json",
        "/clean-assets/../source_archives/store_checkout_001/checkout_overview_original.png",
    ]
    leaked = [probe for probe in private_probes if client.get(probe).status_code != 404]
    if leaked:
        raise AssertionError("private files exposed via web routes: " + ", ".join(leaked))
    checks.append("private-assets:not-web-exposed")

    clue_scan = manifest.get("clue_scan", {})
    patterns = [re.compile(pattern, re.IGNORECASE) for pattern in clue_scan.get("forbidden_patterns", [])]
    for relative in clue_scan.get("files", []):
        text = require_file(str(relative), checks).read_text(encoding="utf-8")
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                raise AssertionError(f"benchmark clue {pattern.pattern!r} found in {relative}: {match.group(0)!r}")
    checks.append("agent-visible-assets:clue-scan-clean")

    return {
        "mountable": True,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "dataset": dataset,
        "case_id": case_id,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate that one benchmark case can be mounted and reviewed.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
    result = validate_manifest(manifest_path.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        report_path = args.report if args.report.is_absolute() else ROOT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
