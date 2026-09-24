#!/usr/bin/env python3
"""Keep old reviewer edits without letting them replace a newer source case."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clawtrap_benchmark import contract_review, storage


def main() -> None:
    source = contract_review.candidate_index()["cases"][0]
    case_id = source["id"]
    old_edit = {
        "fields": {"task": "old task", "authorized_boundary": "old boundary"},
        "labels": {"timing": "first step", "risk": "read-only"},
        "status": "confirmed", "revision": 7,
        "editor": "earlier-reviewer", "updated_at": "earlier-time",
    }
    with tempfile.TemporaryDirectory() as directory:
        edits_path = Path(directory) / "edits.json"
        reviews_path = Path(directory) / "reviews.json"
        edits_path.write_text(json.dumps({case_id: old_edit}), encoding="utf-8")
        reviews_path.write_text(json.dumps({case_id: {"selected": True}}), encoding="utf-8")
        original_bytes = edits_path.read_bytes()
        with patch.object(contract_review, "LOCAL_CONTENT_PATH", edits_path), \
             patch.object(contract_review, "LOCAL_REVIEWS_PATH", reviews_path), \
             patch.object(storage, "database_configured", return_value=False), \
             patch.object(storage, "is_vercel_runtime", return_value=False):
            catalog = contract_review.catalog()
            row = next(item for item in catalog["cases"] if item["id"] == case_id)
            assert row["content_edit"]["status"] == "stale"
            assert row["content_edit"]["revision"] == 7
            assert row["content_edit"]["editor"] == "earlier-reviewer"
            assert row["v3_contract"]["task"] == source["v3_contract"]["task"]
            assert row["v3_contract"]["authorized_boundary"] == source["v3_contract"]["authorized_boundary"]
            assert row["v3_contract"]["attack"] == source["v3_contract"]["attack"]
            assert row["review"]["selected"] is True
            assert catalog["confirmed"] == 0
            assert contract_review.confirmed_export()["cases"] == []
            selected = contract_review.selected_export()["cases"]
            assert len(selected) == 1 and selected[0]["case"] == source["v3_contract"]
            assert edits_path.read_bytes() == original_bytes

            saved = contract_review.save_content_edit(
                case_id, {"fields": {"task": "new reviewer task"},
                          "status": "confirmed", "revision": 7}, "current-reviewer")
            assert saved["base_source_sha256"] == contract_review._source_fingerprint(source)
            assert saved["revision"] == 8
            assert saved["fields"]["task"] == "new reviewer task"
            assert saved["fields"]["authorized_boundary"] == source["v3_contract"]["authorized_boundary"]
            assert saved["labels"] == {}
            assert contract_review.catalog()["confirmed"] == 1
            changed_source = deepcopy(source)
            changed_source["v3_contract"]["task"] = "new source revision"
            assert contract_review._edited_row(changed_source, saved)["content_edit"]["status"] == "stale"
    print("Source fingerprint regression passed: stale edits preserved; fresh edits apply")


if __name__ == "__main__":
    main()
