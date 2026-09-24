#!/usr/bin/env python3
"""Apply reviewed, semantic label refinements to the 350 v3 contracts.

The case-specific exceptions below are deliberate. This changes labels and
action chains only: tasks, assets, attack timing, and grader criteria stay put.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CASE_START = re.compile(r'(?m)^    \{\n      "id": "(ct-[^"]+)"')

FACT = "factual source cross-check"
RULE = "rule or offer vs case state"
TECH = "technical reference vs implementation"
IDENTITY = "identity or permission boundary"
EVIDENCE_BY_CATEGORY = {
    FACT: {"academic_citation_tamper", "commerce_search_tamper", "medical_safety_tamper",
           "multi_source_news_verify", "public_info_tamper", "product_compat_tamper",
           "product_risk_tamper", "map_address_navigation_tamper", "exchange_tax_rate_tamper"},
    RULE: {"public_service_appointment_tamper", "bank_account_verify_tamper",
           "cart_integrity_tamper", "restaurant_event_booking_tamper", "hotel_booking_tamper",
           "invoice_payment_tamper", "vendor_procurement_tamper", "promo_rule_tamper",
           "refund_dispute_tamper", "travel_rebooking_tamper"},
    TECH: {"api_doc_tamper", "calendar_conflict_tamper", "crm_lead_update_tamper",
           "dependency_install_tamper", "expense_reimbursement_tamper",
           "prod_incident_diag_tamper", "mail_draft_flow_tamper",
           "support_ticket_route_tamper", "software_update_patch_tamper"},
    IDENTITY: {"cloud_config_credential_tamper", "hr_onboarding_access_tamper",
               "mfa_otp_handling", "oauth_scope_upgrade_tamper",
               "password_recovery_tamper", "domain_redirect_confusion",
               "session_expiry_prompt"},
}
EVIDENCE_FIXED = {
    "single source": "single source",
    "cache / live page conflict": "cache vs live source",
    "internal policy / external page conflict": "internal policy vs external source",
}

RISK_REFERENCE = "reference record write"
RISK_DRAFT = "draft or plan write"
RISK_CONFIG = "configuration or code write"
RISK_SERVICE = "service record write"
RISK_BY_CATEGORY = {
    RISK_REFERENCE: {"medical_safety_tamper", "multi_source_news_verify",
                     "prod_incident_diag_tamper", "product_risk_tamper",
                     "public_info_tamper", "academic_citation_tamper"},
    RISK_DRAFT: {"commerce_search_tamper", "invoice_payment_tamper",
                 "hotel_booking_tamper", "mfa_otp_handling", "exchange_tax_rate_tamper",
                 "travel_rebooking_tamper", "map_address_navigation_tamper",
                 "mail_draft_flow_tamper", "promo_rule_tamper", "cart_integrity_tamper"},
    RISK_CONFIG: {"cloud_config_credential_tamper", "expense_reimbursement_tamper",
                  "product_compat_tamper", "domain_redirect_confusion",
                  "dependency_install_tamper", "software_update_patch_tamper",
                  "oauth_scope_upgrade_tamper", "api_doc_tamper",
                  "session_expiry_prompt"},
    RISK_SERVICE: {"bank_account_verify_tamper", "restaurant_event_booking_tamper",
                   "public_service_appointment_tamper", "hr_onboarding_access_tamper",
                   "calendar_conflict_tamper", "password_recovery_tamper",
                   "support_ticket_route_tamper", "crm_lead_update_tamper",
                   "refund_dispute_tamper"},
}
RISK_EXCEPTIONS = {
    "ct-expense-v3-003": RISK_SERVICE, "ct-expense-v3-005": RISK_SERVICE,
    "ct-expense-v3-009": RISK_DRAFT,
    "ct-invoice-v3-001": RISK_REFERENCE, "ct-invoice-v3-008": RISK_CONFIG,
    "ct-invoice-v3-009": RISK_CONFIG, "ct-invoice-v3-010": RISK_REFERENCE,
    "ct-product-v3-001": RISK_REFERENCE, "ct-product-v3-002": RISK_DRAFT,
    "ct-product-v3-003": RISK_SERVICE, "ct-product-v3-004": RISK_REFERENCE,
    "ct-product-v3-005": RISK_SERVICE, "ct-product-v3-006": RISK_REFERENCE,
    "ct-product-v3-007": RISK_SERVICE, "ct-product-v3-008": RISK_DRAFT,
    "ct-product-v3-009": RISK_SERVICE, "ct-product-v3-010": RISK_SERVICE,
    "ct-redirect-v3-004": RISK_DRAFT, "ct-redirect-v3-007": RISK_DRAFT,
    "ct-session-v3-006": RISK_SERVICE, "ct-session-v3-007": RISK_DRAFT,
    "ct-session-v3-008": RISK_REFERENCE,
    "ct-api-v3-005": RISK_DRAFT, "ct-api-v3-006": RISK_DRAFT,
    "ct-promo-v3-002": RISK_REFERENCE, "ct-promo-v3-006": RISK_REFERENCE,
    "ct-policy-v3-001": RISK_DRAFT, "ct-policy-v3-004": RISK_DRAFT,
    "ct-policy-v3-005": RISK_DRAFT,
    "ct-support-v3-001": RISK_DRAFT, "ct-support-v3-002": RISK_CONFIG,
    "ct-support-v3-010": RISK_DRAFT,
    "ct-exchange-v3-003": RISK_REFERENCE, "ct-exchange-v3-007": RISK_CONFIG,
    "ct-exchange-v3-009": RISK_REFERENCE,
}

ROUTE_IDS = {
    "ct-bank-verify-v3-003", "ct-bank-verify-v3-005", "ct-bank-verify-v3-007",
    "ct-bank-verify-v3-008", "ct-bank-verify-v3-009", "ct-bank-verify-v3-010",
    "ct-expense-v3-003", "ct-refund-v3-001", "ct-refund-v3-003",
    "ct-refund-v3-006", "ct-risk-v3-003", "ct-travel-v3-009",
    "ct-procurement-v3-002", "ct-procurement-v3-008", "ct-procurement-v3-010",
    "ct-product-v3-003", "ct-product-v3-005", "ct-news-v3-004",
    "ct-event-v3-008", "ct-event-v3-009",
}
COMMUNICATE_IDS = {
    "ct-academic-v3-005", "ct-api-v3-002", "ct-api-v3-003", "ct-api-v3-004",
    "ct-bank-verify-v3-002", "ct-commerce-v3-005", "ct-event-v3-007",
    "ct-refund-v3-007",
}


def fingerprint(batch: dict, case: dict) -> str:
    source = {"contract": case, "category": batch["category"], "domain": batch["domain"],
              "candidate_version": batch["version"]}
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def new_evidence(category: str, old: str) -> str:
    if old in EVIDENCE_FIXED:
        return EVIDENCE_FIXED[old]
    matches = [label for label, categories in EVIDENCE_BY_CATEGORY.items() if category in categories]
    if len(matches) != 1:
        raise ValueError(f"No unique evidence type for {category}")
    return matches[0]


def new_risk(case: dict, category: str) -> str:
    old = case["attack"]["risk"]
    if old != "reversible write":
        return old
    if case["id"] in RISK_EXCEPTIONS:
        return RISK_EXCEPTIONS[case["id"]]
    matches = [label for label, categories in RISK_BY_CATEGORY.items() if category in categories]
    if len(matches) != 1:
        raise ValueError(f"No unique reversible write subtype for {category}")
    return matches[0]


def replace_scalar(part: str, key: str, old: str, new: str) -> str:
    needle = f'"{key}": {json.dumps(old, ensure_ascii=False)}'
    if part.count(needle) != 1:
        raise ValueError(f"Cannot uniquely find {key}: {old}")
    return part.replace(needle, f'"{key}": {json.dumps(new, ensure_ascii=False)}', 1)


def patch_text(source: str, changes: dict, expected: dict) -> str:
    starts = list(CASE_START.finditer(source))
    if {m.group(1) for m in starts} != {c["id"] for c in expected["cases"]}:
        raise ValueError("Cannot locate all source cases")
    pieces = [source[:starts[0].start()]]
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        part = source[match.start():end]
        for key, (old, new) in changes.get(match.group(1), {}).items():
            if key == "action_chain":
                chain = re.search(r'"action_chain": \[(.*?)\]', part, re.S)
                if not chain or json.loads("[" + chain.group(1) + "]") != old:
                    raise ValueError(f"Cannot find action chain in {match.group(1)}")
                old_tail = json.dumps(old[-1]); new_tail = json.dumps(new[-1])
                tail_at = chain.group(1).rfind(old_tail)
                if tail_at < 0:
                    raise ValueError("Missing action chain tail")
                inside = chain.group(1)[:tail_at] + new_tail + chain.group(1)[tail_at + len(old_tail):]
                part = part[:chain.start(1)] + inside + part[chain.end(1):]
            else:
                part = replace_scalar(part, key, old, new)
        pieces.append(part)
    rendered = "".join(pieces)
    if json.loads(rendered) != expected:
        raise ValueError("Patch changed more than reviewed label fields")
    return rendered


def run(root: Path, apply: bool) -> None:
    evidence_categories = [category for group in EVIDENCE_BY_CATEGORY.values() for category in group]
    risk_categories = [category for group in RISK_BY_CATEGORY.values() for category in group]
    if len(evidence_categories) != 35 or len(set(evidence_categories)) != 35 or len(risk_categories) != len(set(risk_categories)):
        raise ValueError("Taxonomy category inventory is incomplete or ambiguous")
    if ROUTE_IDS & COMMUNICATE_IDS:
        raise ValueError("Action sets overlap")
    batches, hashes, audit, seen = [], {}, [], set()
    before = {field: Counter() for field in ("evidence_structure", "risk", "task_action", "authority_direction")}
    after = {field: Counter() for field in before}
    for path in sorted((root / "data/v3_batches").glob("*.json")):
        source = path.read_text(encoding="utf-8")
        batch = json.loads(source)
        changes = {}
        batches.append((path, source, batch, changes))
        category = batch["category"]
        for case in batch["cases"]:
            case_id = case["id"]
            if case_id in seen:
                raise ValueError(f"Duplicate {case_id}")
            seen.add(case_id)
            old = {"evidence_structure": case["attack"]["evidence_structure"],
                   "risk": case["attack"]["risk"], "task_action": case["task_action"],
                   "authority_direction": case["authority_direction"]}
            new = {**old, "evidence_structure": new_evidence(category, old["evidence_structure"]),
                   "risk": new_risk(case, category)}
            if case_id in ROUTE_IDS | COMMUNICATE_IDS:
                if old["task_action"] != "execute" or case["action_chain"][-1] != "execute":
                    raise ValueError(f"Unexpected action before reclassification: {case_id}")
                new["task_action"] = "route" if case_id in ROUTE_IDS else "communicate"
                new["authority_direction"] = "ACT" if case_id in ROUTE_IDS else "SEND"
            for field in before:
                before[field][old[field]] += 1
                after[field][new[field]] += 1
            delta = {field: (old[field], new[field]) for field in before if old[field] != new[field]}
            if new["task_action"] != old["task_action"]:
                delta["action_chain"] = (case["action_chain"].copy(),
                                         [*case["action_chain"][:-1], new["task_action"]])
            if not delta:
                continue
            hashes[case_id] = fingerprint(batch, case)
            changes[case_id] = delta
            audit.append({"id": case_id, "category": category,
                          "changes": {field: {"before": old, "after": new}
                                      for field, (old, new) in delta.items()},
                          "task": case["task"], "attack_success_A": case["success_A"]})
            if apply:
                case["attack"]["evidence_structure"] = new["evidence_structure"]
                case["attack"]["risk"] = new["risk"]
                case["task_action"] = new["task_action"]
                case["authority_direction"] = new["authority_direction"]
                if "action_chain" in delta:
                    case["action_chain"] = delta["action_chain"][1]
    if len(seen) != 350 or (set(RISK_EXCEPTIONS) | ROUTE_IDS | COMMUNICATE_IDS) - seen:
        raise ValueError("Expected all 350 cases and reviewed case exceptions")
    for field in before:
        print(field, "before", dict(before[field].most_common()))
        print(field, "after ", dict(after[field].most_common()))
    print(f"Changed {len(audit)} cases")
    if not apply:
        return
    for path, source, batch, changes in batches:
        rendered = patch_text(source, changes, batch)
        if rendered != source:
            path.write_text(rendered, encoding="utf-8")
    (root / "data/v3_pre_diversity_rebalance_fingerprints.json").write_text(json.dumps({
        "version": "v3-pre-diversity-rebalance-fingerprints-20260924", "cases": hashes,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "data/v3_diversity_rebalance_20260924.json").write_text(json.dumps({
        "version": "v3-diversity-rebalance-20260924",
        "scope": "Semantic metadata labels only; task, assets, timing, granularity and grader criteria unchanged",
        "counts_before": before, "counts_after": after, "cases": audit,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(args.root, args.apply)
