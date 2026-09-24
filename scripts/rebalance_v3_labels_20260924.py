#!/usr/bin/env python3
"""Reviewable, case-specific v3 timing and attack-position reclassification."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


DEFAULT_ROOT = Path(__file__).resolve().parents[1]

DISCOVERY = "discovery result or citation"
TECHNICAL = "technical reference page"
GUIDANCE = "policy or guidance page"
RECORD = "record or action page"
FLOW = "navigation or error state"

# These defaults follow the actual kind of HTML document fetched for each
# category. Exceptions below are individual pages whose document type differs.
PAGE_BY_CATEGORY = {
    "academic_citation_tamper": RECORD,
    "api_doc_tamper": TECHNICAL,
    "public_service_appointment_tamper": GUIDANCE,
    "bank_account_verify_tamper": GUIDANCE,
    "calendar_conflict_tamper": TECHNICAL,
    "cart_integrity_tamper": RECORD,
    "cloud_config_credential_tamper": TECHNICAL,
    "commerce_search_tamper": RECORD,
    "crm_lead_update_tamper": TECHNICAL,
    "dependency_install_tamper": TECHNICAL,
    "restaurant_event_booking_tamper": GUIDANCE,
    "exchange_tax_rate_tamper": GUIDANCE,
    "expense_reimbursement_tamper": TECHNICAL,
    "hotel_booking_tamper": GUIDANCE,
    "hr_onboarding_access_tamper": TECHNICAL,
    "prod_incident_diag_tamper": TECHNICAL,
    "invoice_payment_tamper": RECORD,
    "mail_draft_flow_tamper": TECHNICAL,
    "map_address_navigation_tamper": RECORD,
    "medical_safety_tamper": RECORD,
    "mfa_otp_handling": TECHNICAL,
    "multi_source_news_verify": RECORD,
    "oauth_scope_upgrade_tamper": TECHNICAL,
    "public_info_tamper": GUIDANCE,
    "vendor_procurement_tamper": GUIDANCE,
    "product_compat_tamper": RECORD,
    "promo_rule_tamper": GUIDANCE,
    "password_recovery_tamper": GUIDANCE,
    "domain_redirect_confusion": TECHNICAL,
    "refund_dispute_tamper": GUIDANCE,
    "product_risk_tamper": RECORD,
    "support_ticket_route_tamper": TECHNICAL,
    "travel_rebooking_tamper": GUIDANCE,
    "software_update_patch_tamper": TECHNICAL,
}

PAGE_EXCEPTIONS = {
    "ct-crm-v3-004": RECORD,  # received message
    "ct-exchange-v3-001": RECORD,  # daily rate record
    "ct-hr-v3-004": RECORD,  # provisioning request card
    "ct-incident-v3-002": RECORD,  # incident history
    "ct-incident-v3-003": RECORD,  # incident history
    "ct-invoice-v3-006": GUIDANCE,  # payment deadline rule
    "ct-invoice-v3-007": GUIDANCE,  # payment deadline rule
    "ct-mail-v3-007": RECORD,  # compose/action page
    "ct-medical-v3-004": GUIDANCE,  # first-aid guidance
    "ct-policy-v3-007": RECORD,  # dated FTC announcement
    "ct-product-v3-009": TECHNICAL,  # Docker install requirements
    "ct-promo-v3-001": RECORD,  # product/plan detail
    "ct-promo-v3-004": RECORD,  # product detail
    "ct-refund-v3-009": TECHNICAL,  # API enum documentation
}

# The attacker is encountered at the first relevant source response. Search
# may discover its URL first; "first step" refers to first attacked exposure.
FIRST_EXPOSURE = {
    "ct-academic-v3-004",
    "ct-appointment-v3-001", "ct-appointment-v3-004", "ct-appointment-v3-010",
    "ct-bank-verify-v3-006", "ct-cloud-v3-002", "ct-commerce-v3-003",
    "ct-exchange-v3-002", "ct-exchange-v3-004", "ct-exchange-v3-006", "ct-exchange-v3-010",
    "ct-invoice-v3-007",
    "ct-medical-v3-002", "ct-medical-v3-004", "ct-medical-v3-008",
    "ct-medical-v3-009", "ct-medical-v3-010",
    "ct-policy-v3-002", "ct-policy-v3-005", "ct-policy-v3-006",
    "ct-product-v3-008",
    "ct-promo-v3-001", "ct-promo-v3-004", "ct-promo-v3-010",
    "ct-support-v3-001", "ct-support-v3-010", "ct-travel-v3-003",
}

# The intercepted response is consulted while reconciling a local record,
# another source, an API snapshot, or a candidate against the task constraints.
VERIFICATION = {
    "ct-academic-v3-002", "ct-academic-v3-005", "ct-academic-v3-006",
    "ct-academic-v3-007", "ct-academic-v3-010",
    "ct-api-v3-008", "ct-api-v3-009", "ct-api-v3-010",
    "ct-appointment-v3-002", "ct-appointment-v3-005", "ct-appointment-v3-006",
    "ct-appointment-v3-007", "ct-appointment-v3-009",
    "ct-bank-verify-v3-005", "ct-bank-verify-v3-007", "ct-bank-verify-v3-008",
    "ct-bank-verify-v3-009", "ct-bank-verify-v3-010",
    "ct-calendar-v3-006", "ct-calendar-v3-010",
    "ct-crm-v3-003", "ct-crm-v3-005", "ct-crm-v3-008",
    "ct-exchange-v3-008",
    "ct-expense-v3-001", "ct-expense-v3-002", "ct-expense-v3-004",
    "ct-expense-v3-005", "ct-expense-v3-006", "ct-expense-v3-007", "ct-expense-v3-008",
    "ct-hotel-v3-001", "ct-hotel-v3-003", "ct-hotel-v3-005",
    "ct-hotel-v3-006", "ct-hotel-v3-007", "ct-hotel-v3-009",
    "ct-incident-v3-002", "ct-incident-v3-003", "ct-incident-v3-008",
    "ct-incident-v3-009", "ct-incident-v3-010",
    "ct-invoice-v3-008", "ct-invoice-v3-009", "ct-invoice-v3-010",
    "ct-map-v3-001", "ct-map-v3-004", "ct-map-v3-006", "ct-map-v3-007",
    "ct-map-v3-008", "ct-map-v3-009",
    "ct-news-v3-001", "ct-news-v3-002",
    "ct-product-v3-004", "ct-product-v3-007", "ct-promo-v3-003",
    "ct-support-v3-002", "ct-travel-v3-002",
}

POSITION_MERGES = {
    "search results": DISCOVERY,
    "third-party citation": DISCOVERY,
    "checkout page": RECORD,
    "login page": FLOW,
    "error page": FLOW,
    "redirect chain": FLOW,
}


CASE_START = re.compile(r'(?m)^    \{\n      "id": "(ct-[^"]+)"')


def replace_case_text(text: str, mutations: dict, expected: dict) -> str:
    """Change only reviewed labels, preserving each batch's existing formatting."""
    starts = list(CASE_START.finditer(text))
    if {match.group(1) for match in starts} != {case["id"] for case in expected["cases"]}:
        raise ValueError("Could not locate every case in the source text")
    pieces = [text[:starts[0].start()]]
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        part = text[match.start():end]
        update = mutations.get(match.group(1))
        if update:
            for key in ("position", "timing"):
                old, new = update[f"{key}_before"], update[f"{key}_after"]
                if old == new:
                    continue
                needle = f'"{key}": "{old}"'
                at = part.find(needle)
                if at < 0:
                    raise ValueError(f"Could not update {key} for {match.group(1)}")
                replacement = f'"{key}": "{new}"'
                if key == "position" and old in POSITION_MERGES:
                    after = at + len(needle)
                    if part[after:after + 1] != ",":
                        raise ValueError(f"Position is not followed by comma: {match.group(1)}")
                    line_start = part.rfind("\n", 0, at) + 1
                    line_end = part.find("\n", after)
                    line = part[line_start:line_end if line_end >= 0 else len(part)]
                    if line.strip() == needle + ",":
                        indent = line[:len(line) - len(line.lstrip())]
                        replacement += f',\n{indent}"position_detail": "{old}"'
                    else:
                        replacement += f', "position_detail": "{old}"'
                part = part[:at] + replacement + part[at + len(needle):]
            if update["phase_changed"]:
                old, new = update["timing_before"], update["timing_after"]
                before = f'"phase": "{old}"'
                if before not in part:
                    raise ValueError(f"Could not align phase for {match.group(1)}")
                part = part.replace(before, f'"phase": "{new}"', 1)
        pieces.append(part)
    rendered = "".join(pieces)
    if json.loads(rendered) != expected:
        raise ValueError("Text edit did not exactly match the reviewed case mutations")
    return rendered


def run(root: Path, apply: bool) -> None:
    batches_dir = root / "data/v3_batches"
    audit_path = root / "data/v3_label_rebalance_20260924.json"
    assert not FIRST_EXPOSURE & VERIFICATION
    seen, changes = set(), []
    before_timing, after_timing = Counter(), Counter()
    before_position, after_position = Counter(), Counter()
    batches = []
    for path in sorted(batches_dir.glob("*.json")):
        source_text = path.read_text(encoding="utf-8")
        batch = json.loads(source_text)
        mutations = {}
        batches.append((path, source_text, batch, mutations))
        category = batch["category"]
        for case in batch["cases"]:
            case_id, attack = case["id"], case["attack"]
            if case_id in seen:
                raise ValueError(f"Duplicate case: {case_id}")
            seen.add(case_id)
            old_position, old_timing = attack["position"], attack["timing"]
            before_position[old_position] += 1
            before_timing[old_timing] += 1
            if old_position == "target webpage":
                position = PAGE_EXCEPTIONS.get(case_id, PAGE_BY_CATEGORY.get(category))
                if position is None:
                    raise ValueError(f"Unclassified page: {case_id}")
            else:
                position = POSITION_MERGES.get(old_position, old_position)
            if case_id in FIRST_EXPOSURE:
                if old_timing != "before decision":
                    raise ValueError(f"First exposure has unexpected old timing: {case_id}")
                timing = "first step"
                timing_reason = "first attacked source response"
            elif case_id in VERIFICATION:
                if old_timing != "before decision":
                    raise ValueError(f"Verification has unexpected old timing: {case_id}")
                timing = "during verification"
                timing_reason = "source reconciled with another source, record, or constraint"
            else:
                timing = old_timing
                timing_reason = "unchanged"
            phase = case.get("attack_surface", {}).get("timing")
            phase_changed = bool(isinstance(phase, dict) and phase.get("phase") == old_timing
                                 and timing != old_timing)
            if position != old_position or timing != old_timing:
                change = {
                    "id": case_id, "category": category,
                    "position_before": old_position, "position_after": position,
                    "timing_before": old_timing, "timing_after": timing,
                    "timing_reason": timing_reason,
                    "source_url": case["source_url"],
                    "attack_field": attack.get("field", ""),
                }
                changes.append(change)
                mutations[case_id] = {**change, "phase_changed": phase_changed}
            if apply:
                if old_position in POSITION_MERGES:
                    attack["position_detail"] = old_position
                attack["position"] = position
                attack["timing"] = timing
                if phase_changed:
                    phase["phase"] = timing
            after_position[position] += 1
            after_timing[timing] += 1
    if len(seen) != 350 or not FIRST_EXPOSURE | VERIFICATION <= seen:
        raise ValueError("Case inventory or timing review IDs are incomplete")
    if before_timing["before decision"] != 130 or before_position["target webpage"] != 165:
        raise ValueError("This rebalance expects the reviewed 350-case source baseline")
    print("Timing before:", dict(before_timing.most_common()))
    print("Timing after: ", dict(after_timing.most_common()))
    print("Position before:", dict(before_position.most_common()))
    print("Position after: ", dict(after_position.most_common()))
    print(f"Reviewed label changes: {len(changes)} / {len(seen)} cases")
    if apply:
        for path, source_text, batch, mutations in batches:
            rendered = replace_case_text(source_text, mutations, batch)
            if rendered != source_text:
                path.write_text(rendered, encoding="utf-8")
        audit_path.write_text(json.dumps({
            "version": "v3-label-rebalance-20260924",
            "scope": "attack.position/timing, original merged position detail, and matching attack_surface.timing.phase; task, assets, and granularity unchanged",
            "position_definitions": {
                DISCOVERY: "search hit or cited link used to discover a source",
                TECHNICAL: "static API, software, or service implementation reference",
                GUIDANCE: "static eligibility, policy, support, or procedural guidance",
                RECORD: "specific paper, product, notice, status, message, request, or action page",
                "API response": "structured service response",
                "download file": "downloaded document or data file",
                FLOW: "login, error, or redirect interruption in navigation",
                "asynchronous update": "late or dynamically updated page component",
            },
            "timing_definitions": {
                "first step": "first attacked source exposure after URL discovery",
                "during verification": "attacked source used while reconciling evidence or a local record",
                "before decision": "attack appears immediately before choosing a route or action",
            },
            "counts_before": {"timing": before_timing, "position": before_position},
            "counts_after": {"timing": after_timing, "position": after_position},
            "cases": changes,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    run(args.root.resolve(), args.apply)
