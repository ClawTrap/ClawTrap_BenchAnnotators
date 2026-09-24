#!/usr/bin/env python3
"""Apply the reviewed 350-case attack-form taxonomy without changing payloads."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION = Path("data/v3_local_form_classification_20260924.json")
LEGACY_FORMS = {
    "ct-calendar-v3-006": "file replacement",
    "ct-calendar-v3-010": "local identifier or destination rewrite",
    "ct-crm-v3-002": "API JSON mutation",
    "ct-crm-v3-003": "file replacement",
    "ct-crm-v3-004": "mixed benign–malicious content",
    "ct-crm-v3-005": "file replacement",
    "ct-crm-v3-007": "API JSON mutation",
    "ct-crm-v3-008": "local identifier or destination rewrite",
    "ct-crm-v3-010": "API JSON mutation",
    "ct-session-v3-002": "mixed benign–malicious content",
    "ct-session-v3-006": "mixed benign–malicious content",
}
CASE_START = re.compile(r'(?m)^    \{\n      "id": "(ct-[^"]+)"')


def fingerprint(batch: dict, case: dict) -> str:
    source = {"contract": case, "category": batch["category"],
              "domain": batch["domain"], "candidate_version": batch["version"]}
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def patch_text(source: str, changes: dict, expected: dict) -> str:
    starts = list(CASE_START.finditer(source))
    if {m.group(1) for m in starts} != {c["id"] for c in expected["cases"]}:
        raise ValueError("Cannot locate each case in batch source")
    pieces = [source[:starts[0].start()]]
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        part = source[match.start():end]
        change = changes.get(match.group(1))
        if change:
            old, new = change["before"], change["after"]
            needle = f'"form": "{old}"'
            if part.count(needle) != 1:
                raise ValueError(f"Cannot locate unique form in {match.group(1)}")
            replacement = f'"form": "{new}"'
            if change["detail"]:
                at = part.index(needle)
                line_start = part.rfind("\n", 0, at) + 1
                indent = part[line_start:at]
                replacement += f',\n{indent}"form_detail": "{old}"'
            part = part.replace(needle, replacement, 1)
        pieces.append(part)
    rendered = "".join(pieces)
    if json.loads(rendered) != expected:
        raise ValueError("Text edit changed more than reviewed form labels")
    return rendered


def run(root: Path, apply: bool) -> None:
    reviewed = json.loads((root / CLASSIFICATION).read_text(encoding="utf-8"))
    local = reviewed["cases"]
    labels = reviewed["labels"]
    carrier_forms = reviewed["carrier_precedence"]
    if len(local) != 194 or set(labels) != set("FRSIO") or set(local) & set(LEGACY_FORMS):
        raise ValueError("Reviewed classification inventory is incomplete")
    batches = []
    hashes, audit, seen = {}, [], set()
    before, after = Counter(), Counter()
    for path in sorted((root / "data/v3_batches").glob("*.json")):
        source = path.read_text(encoding="utf-8")
        batch = json.loads(source)
        changes = {}
        batches.append((path, source, batch, changes))
        for case in batch["cases"]:
            case_id, attack = case["id"], case["attack"]
            if case_id in seen:
                raise ValueError(f"Duplicate case: {case_id}")
            seen.add(case_id)
            old = attack["form"]
            before[old] += 1
            if case_id in local:
                check = local[case_id]
                if old != "selective substitution" or attack.get("field", "") != check["attack_field"]:
                    raise ValueError(f"Classification no longer matches source: {case_id}")
                new = carrier_forms.get(attack["position"], labels[check["class"]])
            elif case_id in LEGACY_FORMS:
                if old in {"selective substitution", "API JSON mutation", "file replacement",
                           "mixed benign–malicious content", "full-page replacement", "redirect rewriting"}:
                    raise ValueError(f"Rare label no longer present: {case_id}")
                new = LEGACY_FORMS[case_id]
            else:
                new = old
            after[new] += 1
            if new != old:
                hashes[case_id] = fingerprint(batch, case)
                detail = case_id in LEGACY_FORMS
                changes[case_id] = {"before": old, "after": new, "detail": detail}
                audit.append({"id": case_id, "form_before": old, "form_after": new,
                              "form_detail": old if detail else None,
                              "attack_field": attack.get("field", ""),
                              "reason": ("specific carrier or inserted overlay consolidated"
                                         if detail else "API response or downloaded file takes carrier form precedence"
                                         if attack["position"] in carrier_forms else
                                         reviewed["definitions"][check["class"]])})
                if apply:
                    attack["form"] = new
                    if detail:
                        attack["form_detail"] = old
    if len(seen) != 350 or (set(local) | set(LEGACY_FORMS)) - seen:
        raise ValueError("350-case inventory or reviewed IDs mismatch")
    if before["selective substitution"] != 194 or sum(before.values()) != 350 or len(audit) != 205:
        raise ValueError("Unexpected source form distribution")
    if min(after.values()) <= 5 or len(after) != 10:
        raise ValueError("New form distribution still contains sparse labels")
    print("Before:", dict(before.most_common()))
    print("After: ", dict(after.most_common()))
    print(f"Changed {len(audit)} / {len(seen)} labels")
    if apply:
        for path, source, batch, changes in batches:
            rendered = patch_text(source, changes, batch)
            if rendered != source:
                path.write_text(rendered, encoding="utf-8")
        (root / "data/v3_pre_form_rebalance_fingerprints.json").write_text(json.dumps({
            "version": "v3-pre-form-rebalance-fingerprints-20260924",
            "cases": hashes,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / "data/v3_form_rebalance_20260924.json").write_text(json.dumps({
            "version": "v3-form-rebalance-20260924",
            "scope": "attack.form and original rare form_detail only; task, assets, position, timing, and granularity unchanged",
            "counts_before": before, "counts_after": after, "cases": audit,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    run(args.root.resolve(), args.apply)
