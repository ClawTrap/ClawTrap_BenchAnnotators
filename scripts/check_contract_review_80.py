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
    assert len(cases) == 90
    legacy = [case for case in cases if "v3_contract" not in case]
    v3 = [case for case in cases if "v3_contract" in case]
    assert len(legacy) == 80 and len(v3) == 10
    assert len({r["category"] for r in cases}) == 30
    assert len({r["host"] for r in legacy}) == 59
    assert len({r["host"] for r in v3}) == 10
    for case in v3:
        contract = case["v3_contract"]
        assert contract["scenario"]
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
        if "v3_contract" in case:
            assert (ROOT / case["v3_contract"]["source_archive"]).is_dir()
    bundle = ROOT / "runtime_assets/previews.zip"
    if bundle.is_file():
        with zipfile.ZipFile(bundle) as archive:
            names = set(archive.namelist())
            for case in cases:
                for kind in ("clean", "attack"):
                    entry = case["preview"][kind].lstrip("/").replace("-assets/", "_assets/", 1)
                    assert entry in names, (case["id"], kind, "missing from deployment bundle")
    source = ROOT / "new_data/academic_citation_tamper_001.jsonl"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        reviews_path = Path(directory) / "contract_reviews.json"
        with patch.object(contract_review, "LOCAL_REVIEWS_PATH", reviews_path), \
             patch.object(storage, "database_configured", return_value=False), \
             patch.object(storage, "is_vercel_runtime", return_value=False):
            client = app.test_client()
            assert client.get("/api/contracts/catalog").status_code == 401
            assert client.post("/api/contracts/cases/" + cases[0]["id"], json={"verdict": "exclude"}).status_code == 401
            assert client.get("/contract-review").status_code == 302
            with client.session_transaction() as session:
                session.update(role="admin", username="contract-smoke")
            response = client.get("/api/contracts/catalog")
            assert response.status_code == 200 and response.get_json()["total"] == 90
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
            before_old = client.get("/api/review/cases/" + case_id).get_json()["case"]
            saved = client.post(endpoint, json={"verdict": "retain_material", "checks": {
                "category_fit": "pass", "snapshot_and_injection": "pass",
                "task_and_boundary": "needs_work", "t_a_evidence": "unknown"},
                "notes": "Need independent world and observable events"})
            assert saved.status_code == 200, saved.get_json()
            assert saved.get_json()["review"]["verdict"] == "retain_material"
            assert reviews_path.is_file()
            after_old = client.get("/api/review/cases/" + case_id).get_json()["case"]
            assert before_old.get("expert_decision") == after_old.get("expert_decision")
            assert before_old.get("benchmark_selected") == after_old.get("benchmark_selected")
            refreshed = client.get("/api/contracts/catalog").get_json()
            assert refreshed["reviewed"] == 1
            assert next(r for r in refreshed["cases"] if r["id"] == case_id)["review"]["notes"] == "Need independent world and observable events"
            assert client.post(endpoint, json={"verdict": "clear"}).status_code == 200
            assert client.get("/api/contracts/catalog").get_json()["reviewed"] == 0
            with client.session_transaction() as session:
                session.clear()
            with patch.dict("os.environ", CLAWTRAP_LAB_PROXY_TOKEN="test-proxy"):
                assert client.get("/api/contracts/catalog", headers={"X-ClawTrap-Lab-Proxy": "test-proxy"}).status_code == 401
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    print(json.dumps({"cases": 90, "legacy_cases": 80, "v3_cases": 10,
                      "categories": 30, "v3_sites": 10, "previews": 180,
                      "review_storage_independent": True, "old_case_unchanged": True,
                      "reviewer_auth_required": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
