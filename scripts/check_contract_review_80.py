#!/usr/bin/env python3
"""Focused mount, authorization, and independent-review smoke test."""
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
    assert all("v3_contract" in case for case in cases)
    assert len({r["category"] for r in cases}) == len(batches)
    assert len({r["source_url"] for r in cases}) == len(cases)
    assert len({r["host"] for r in cases}) >= 15
    assert {r["category_number"] for r in cases} == set(range(1, len(batches) + 1))
    for case in cases:
        contract = case["v3_contract"]
        assert case["source_url"] in contract["task"]
        assert contract["scenario"] and contract["deliverable"] and contract["output_format"]
        assert contract["success_T"] and contract["success_A"]
        assert all(contract["attack"].get(field) for field in
                   ("form", "position", "evidence_structure", "risk", "timing"))
    for case in cases:
        for kind in ("clean", "attack"):
            entry = case["preview"][kind].lstrip("/").replace("-assets/", "_assets/", 1)
            snapshot = ROOT / "new_data" / entry
            expected = case["private_review"][f"{kind}_sha256"]
            assert snapshot.is_file(), (case["id"], kind)
            if expected:
                assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == expected, (case["id"], kind)
        assert (ROOT / case["v3_contract"]["source_archive"]).is_dir()
    bundle = ROOT / "runtime_assets/previews.zip"
    if bundle.is_file():
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            for case in cases:
                for kind in ("clean", "attack"):
                    entry = case["preview"][kind].lstrip("/").replace("-assets/", "_assets/", 1)
                    assert entry in names, (case["id"], kind, "missing from deployment bundle")
    source = ROOT / "data/v3_batches/news_001.json"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        reviews_path = Path(directory) / "contract_reviews.json"
        content_path = Path(directory) / "contract_content_edits.json"
        with patch.object(contract_review, "LOCAL_REVIEWS_PATH", reviews_path), \
             patch.object(contract_review, "LOCAL_CONTENT_PATH", content_path), \
             patch.object(storage, "database_configured", return_value=False), \
             patch.object(storage, "is_vercel_runtime", return_value=False):
            client = app.test_client()
            assert client.get("/api/contracts/catalog").status_code == 401
            assert client.post("/api/contracts/cases/" + cases[0]["id"], json={"verdict": "exclude"}).status_code == 401
            assert client.patch("/api/contracts/cases/" + cases[0]["id"] + "/content", json={}).status_code == 401
            assert client.get("/api/contracts/confirmed-export").status_code == 401
            assert client.get("/contract-review").status_code == 302
            with client.session_transaction() as session:
                session.update(role="admin", username="contract-smoke")
            response = client.get("/api/contracts/catalog")
            assert response.status_code == 200 and response.get_json()["total"] == len(cases)
            assert response.get_json()["confirmed"] == 0
            assert response.get_json()["content_writable"] is True
            assert client.get("/contract-review").status_code == 200
            assert b"contract_review.js" in client.get("/contract-review").data
            assert client.get("/static/contract_review.css").status_code == 200
            assert client.get("/static/contract_review.js").status_code == 200
            for case in cases:
                for kind in ("clean", "attack"):
                    preview = client.get(case["preview"][kind])
                    assert preview.status_code == 200, (case["id"], kind, preview.status_code)
                    assert preview.mimetype == "text/html", (case["id"], kind, preview.mimetype)
                    preview.close()
            case_id = cases[0]["id"]
            endpoint = "/api/contracts/cases/" + case_id
            assert client.post(endpoint, json={"verdict": "retain_material"}).status_code == 400
            assert client.post(endpoint, json={"verdict": "bogus"}).status_code == 400
            assert client.post("/api/contracts/cases/not-listed", json={"verdict": "exclude"}).status_code == 404
            saved = client.post(endpoint, json={"verdict": "retain_material", "checks": {
                "category_fit": "pass", "snapshot_and_injection": "pass",
                "task_and_boundary": "needs_work", "t_a_evidence": "unknown"},
                "notes": "Need independent world and observable events"})
            assert saved.status_code == 200, saved.get_json()
            assert saved.get_json()["review"]["verdict"] == "retain_material"
            assert reviews_path.is_file()
            refreshed = client.get("/api/contracts/catalog").get_json()
            assert refreshed["reviewed"] == 1
            assert next(r for r in refreshed["cases"] if r["id"] == case_id)["review"]["notes"] == "Need independent world and observable events"
            assert client.post(endpoint, json={"verdict": "clear"}).status_code == 200
            assert client.get("/api/contracts/catalog").get_json()["reviewed"] == 0

            original = cases[0]["v3_contract"]
            fields = {key: original[key] for key in contract_review.CONTENT_FIELDS}
            fields["task"] = "请访问指定公告，输出 JSON：date 与 source_url。"
            content_endpoint = endpoint + "/content"
            payload = {"fields": fields, "status": "draft", "revision": 0}
            assert client.patch(content_endpoint, json={**payload, "fields": {"task": "incomplete"}}).status_code == 400
            assert client.patch("/api/contracts/cases/not-listed/content", json=payload).status_code == 404
            draft_response = client.patch(content_endpoint, json=payload)
            assert draft_response.status_code == 200, draft_response.get_json()
            assert draft_response.get_json()["edit"]["revision"] == 1
            assert content_path.is_file()
            refreshed = client.get("/api/contracts/catalog").get_json()
            edited = next(r for r in refreshed["cases"] if r["id"] == case_id)
            assert edited["v3_contract"]["task"] == fields["task"]
            assert edited["public_draft"]["objective"] == fields["task"]
            assert edited["content_edit"]["status"] == "draft"
            assert refreshed["confirmed"] == 0
            assert client.patch(content_endpoint, json=payload).status_code == 400
            confirmed = client.patch(content_endpoint, json={**payload, "revision": 1, "status": "confirmed"})
            assert confirmed.status_code == 200, confirmed.get_json()
            assert confirmed.get_json()["edit"]["revision"] == 2
            assert client.get("/api/contracts/catalog").get_json()["confirmed"] == 1
            exported = client.get("/api/contracts/confirmed-export").get_json()
            assert len(exported["cases"]) == 1
            assert exported["cases"][0]["case"]["task"] == fields["task"]
            assert exported["cases"][0]["case"]["attack"] == original["attack"]
            assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
            with patch.object(storage, "is_vercel_runtime", return_value=True):
                assert client.get("/api/contracts/catalog").get_json()["content_writable"] is False
                no_db = client.patch(content_endpoint, json={**payload, "revision": 2})
                assert no_db.status_code == 503
            with client.session_transaction() as session:
                session.clear()
            with patch.dict("os.environ", CLAWTRAP_LAB_PROXY_TOKEN="test-proxy"):
                assert client.get("/api/contracts/catalog", headers={"X-ClawTrap-Lab-Proxy": "test-proxy"}).status_code == 401
                assert client.get("/api/contracts/confirmed-export", headers={"X-ClawTrap-Lab-Proxy": "test-proxy"}).status_code == 401
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    print(json.dumps({"cases": len(cases), "categories": len(batches),
                      "sites": len({r["host"] for r in cases}), "previews": 2 * len(cases),
                      "review_storage_independent": True, "source_case_unchanged": True,
                      "content_edit_and_confirmation": True,
                      "reviewer_auth_required": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
