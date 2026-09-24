#!/usr/bin/env python3
"""Focused v3 mount, edit, selection, and legacy-retirement smoke test."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clawtrap_benchmark import contract_review, storage
from clawtrap_benchmark.web import app


def main() -> None:
    cases = contract_review.candidate_index()["cases"]
    batches = [json.loads(path.read_text(encoding="utf-8"))
               for path in sorted((ROOT / "data/v3_batches").glob("*.json"))]
    assert len(cases) == sum(len(batch["cases"]) for batch in batches)
    assert all(len(batch["cases"]) == 10 for batch in batches)
    assert len({case["id"] for case in cases}) == len(cases)
    assert len({case["category"] for case in cases}) == len(batches)
    assert {case["category_number"] for case in cases} == set(range(1, len(batches) + 1))
    assert len({case["host"] for case in cases}) >= 15
    assert len({case["v3_contract"]["task_action"] for case in cases}) >= 8
    for case in cases:
        contract = case["v3_contract"]
        assert set(case["public_draft"]) == {"objective", "boundary", "entry"}
        assert "审核合同" not in json.dumps(case["public_draft"], ensure_ascii=False)
        # The reviewer and runner expose the entry URL separately, so a
        # natural-language task need not repeat a long source URL verbatim.
        assert case["public_draft"]["entry"] == case["source_url"]
        assert contract["success_T"] and contract["success_A"]
        assert contract["task_action"] in contract_review.STANDARD_LABELS["task_action"]
        assert contract["action_chain"][-1] == contract["task_action"]
        assert contract["authority_direction"] in {"READ", "WRITE", "ACT", "SEND", "RECEIVE", "GRANT"}
        assert contract["workflow_target"] and contract["deliverable"]
        assert not any(term in contract["task"] for term in ("用 JSON", "用 YAML", "写成一行 CSV", "benchmark", "评分器"))
        for label in ("form", "position", "evidence_structure", "risk", "granularity", "timing"):
            assert contract["attack"][label] in contract_review.STANDARD_LABELS[label], (case["id"], label)
        for kind in ("clean", "attack"):
            entry = case["preview"][kind].lstrip("/").replace("-assets/", "_assets/", 1)
            snapshot = ROOT / "new_data" / entry
            assert snapshot.is_file(), (case["id"], kind)
            expected = case["private_review"][f"{kind}_sha256"]
            if expected:
                assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == expected
        assert (ROOT / contract["source_archive"]).is_dir()
    bundle = ROOT / "runtime_assets/previews.zip"
    if bundle.is_file():
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            for case in cases:
                for kind in ("clean", "attack"):
                    entry = case["preview"][kind].lstrip("/").replace("-assets/", "_assets/", 1)
                    assert entry in names, (case["id"], kind)

    source = ROOT / "data/v3_batches/news_001.json"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(contract_review, "LOCAL_REVIEWS_PATH", Path(directory) / "reviews.json"), \
             patch.object(contract_review, "LOCAL_CONTENT_PATH", Path(directory) / "edits.json"), \
             patch.object(storage, "database_configured", return_value=False), \
             patch.object(storage, "is_vercel_runtime", return_value=False):
            client = app.test_client()
            assert client.get("/api/contracts/catalog").status_code == 401
            assert client.get("/api/contracts/selected-export").status_code == 401
            assert client.post(f"/api/contracts/cases/{cases[0]['id']}", json={"selected": True}).status_code == 401
            assert client.get("/contract-review").status_code == 302
            with client.session_transaction() as session:
                session.update(role="admin", username="review-smoke")

            catalog = client.get("/api/contracts/catalog").get_json()
            assert catalog["total"] == len(cases) and catalog["selected"] == 0
            assert len(catalog["label_options"]["categories"]) == len(batches)
            assert set(catalog["label_options"]["task_action"]) == contract_review.STANDARD_LABELS["task_action"]
            assert set(catalog["label_options"]["authority_direction"]) == contract_review.STANDARD_LABELS["authority_direction"]
            for label in ("form", "position", "evidence_structure", "risk", "granularity", "timing"):
                assert contract_review.STANDARD_LABELS[label] <= set(catalog["label_options"][label])
            assert catalog["content_writable"] is True
            assert client.get("/contract-review").status_code == 200
            assert client.get("/diversity").status_code == 200
            assert b"contract_review.js" in client.get("/contract-review").data
            assert b"diversity.js" in client.get("/diversity").data
            assert b"/api/contracts/catalog" in client.get("/static/diversity.js").data
            assert b"/api/review/catalog" not in client.get("/static/diversity.js").data
            for route in ("/", "/review", "/benchmark", "/design"):
                assert client.get(route).headers["Location"] == "/contract-review"
            assert client.get("/scenes").headers["Location"] == "/diversity"
            for route in ("/api/review/catalog", f"/api/review/cases/{cases[0]['id']}"):
                assert client.get(route).status_code == 410
            assert client.post(f"/api/review/cases/{cases[0]['id']}", json={}).status_code == 410

            for case in cases:
                for kind in ("clean", "attack"):
                    preview = client.get(case["preview"][kind])
                    suffix = Path(case["preview"][kind]).suffix.lower()
                    expected_type = {
                        ".html": "text/html", ".json": "application/json",
                        ".yaml": "text/plain", ".yml": "text/plain", ".toml": "text/plain",
                        ".ris": "text/plain", ".bib": "text/plain",
                        ".md": "text/plain", ".txt": "text/plain",
                        ".csv": "text/plain",
                        ".pdf": "application/pdf",
                    }.get(suffix)
                    assert expected_type is not None, (case["id"], kind, suffix)
                    assert preview.status_code == 200 and preview.mimetype == expected_type
                    preview.close()

            first = cases[0]
            endpoint = f"/api/contracts/cases/{first['id']}"
            assert client.post(endpoint, json={"verdict": "retain_material"}).status_code == 400
            assert client.post(endpoint, json={"selected": "true"}).status_code == 400
            assert client.post("/api/contracts/cases/not-listed", json={"selected": True}).status_code == 404
            response = client.post(endpoint, json={"selected": True})
            assert response.status_code == 200 and response.get_json()["review"]["selected"] is True
            assert client.get("/api/contracts/catalog").get_json()["selected"] == 1
            assert len(client.get("/api/contracts/selected-export").get_json()["cases"]) == 1

            content_endpoint = endpoint + "/content"
            original = first["v3_contract"]
            category = next(item for item in cases if item["category"] != first["category"])
            change = {"fields": {"task": "为本周会议准备一份明确的日程安排，核对网页上的会场和时间后写给参与者。"},
                      "labels": {"category": category["category"], "task_action": "prepare", "authority_direction": "WRITE", "form": "full-page replacement",
                                 "risk": "read-only", "granularity": "component", "timing": "before decision"},
                      "status": "confirmed", "revision": 0}
            assert client.patch(content_endpoint, json={**change, "labels": {"category": "not-a-category"}}).status_code == 400
            assert client.patch(content_endpoint, json={"fields": {"task": ""}, "status": "confirmed", "revision": 0}).status_code == 400
            assert client.patch("/api/contracts/cases/not-listed/content", json=change).status_code == 404
            response = client.patch(content_endpoint, json=change)
            assert response.status_code == 200 and response.get_json()["edit"]["revision"] == 1
            assert client.patch(content_endpoint, json=change).status_code == 400
            refreshed = client.get("/api/contracts/catalog").get_json()
            edited = next(row for row in refreshed["cases"] if row["id"] == first["id"])
            assert edited["content_edit"]["status"] == "confirmed"
            assert contract_review.read_content_edits()[first["id"]]["base_source_sha256"] == contract_review._source_fingerprint(first)
            assert edited["category"] == category["category"]
            assert edited["domain"] == category["domain"]
            assert edited["v3_contract"]["task"] == change["fields"]["task"]
            assert edited["v3_contract"]["task_action"] == "prepare"
            assert edited["v3_contract"]["action_chain"][-1] == "prepare"
            assert edited["v3_contract"]["authority_direction"] == "WRITE"
            assert edited["v3_contract"]["attack"]["form"] == "full-page replacement"
            assert edited["v3_contract"]["attack"]["granularity"] == "component"
            assert edited["v3_contract"]["attack"]["timing"] == "before decision"
            assert edited["v3_contract"]["attack"]["field"] == original["attack"]["field"]
            assert refreshed["confirmed"] == 1
            selected = client.get("/api/contracts/selected-export").get_json()["cases"]
            assert selected[0]["category"] == category["category"]
            assert selected[0]["case"]["task"] == change["fields"]["task"]
            with patch.object(contract_review, "_legacy_task_hashes", return_value={first["id"]: hashlib.sha256(b"old baseline").hexdigest()}), \
                 patch.object(contract_review, "_legacy_boundary_hashes", return_value={first["id"]: hashlib.sha256(b"old boundary").hexdigest()}):
                legacy_edit = {"fields": {"task": "old baseline", "authorized_boundary": "old boundary"},
                               "labels": {"risk": "legacy risk", "timing": "legacy timing"},
                               "status": "confirmed", "revision": 1, "editor": "review-smoke", "updated_at": "now"}
                restored = contract_review._edited_row(first, legacy_edit)
                assert restored["content_edit"]["status"] == "stale"
                assert restored["content_edit"]["revision"] == 1
                assert restored["v3_contract"]["task"] == original["task"]
                assert restored["v3_contract"]["authorized_boundary"] == original["authorized_boundary"]
                assert restored["v3_contract"]["attack"]["risk"] == original["attack"]["risk"]
                assert restored["v3_contract"]["attack"]["timing"] == original["attack"]["timing"]
                manual_edit = {**legacy_edit,
                               "base_source_sha256": contract_review._source_fingerprint(first),
                               "fields": {"task": "reviewer-written task", "authorized_boundary": "reviewer-written boundary"}}
                assert contract_review._edited_row(first, manual_edit)["v3_contract"]["task"] == "reviewer-written task"
                assert contract_review._edited_row(first, manual_edit)["v3_contract"]["authorized_boundary"] == "reviewer-written boundary"
            response = client.post(endpoint, json={"selected": False})
            assert response.status_code == 200 and client.get("/api/contracts/catalog").get_json()["selected"] == 0
            assert client.get("/api/contracts/selected-export").get_json()["cases"] == []
            contract_review.LOCAL_REVIEWS_PATH.write_text(
                json.dumps({first["id"]: {"verdict": "retain_material", "checks": {}, "notes": ""}}),
                encoding="utf-8",
            )
            assert client.get("/api/contracts/catalog").get_json()["selected"] == 1
            assert len(client.get("/api/contracts/selected-export").get_json()["cases"]) == 1
            assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
            with patch.object(storage, "is_vercel_runtime", return_value=True):
                assert client.get("/api/contracts/catalog").get_json()["content_writable"] is False
                assert client.patch(content_endpoint, json={**change, "revision": 1}).status_code == 503
            with client.session_transaction() as session:
                session.clear()
            with patch.dict("os.environ", CLAWTRAP_LAB_PROXY_TOKEN="test-proxy"):
                assert client.get("/api/contracts/catalog", headers={"X-ClawTrap-Lab-Proxy": "test-proxy"}).status_code == 401
                assert client.get("/api/contracts/selected-export", headers={"X-ClawTrap-Lab-Proxy": "test-proxy"}).status_code == 401
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    print(json.dumps({"cases": len(cases), "categories": len(batches), "sites": len({r["host"] for r in cases}),
                      "previews": 2 * len(cases), "legacy_ui_retired": True,
                      "inline_edit_labels_and_selection": True, "source_case_unchanged": True,
                      "reviewer_auth_required": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
