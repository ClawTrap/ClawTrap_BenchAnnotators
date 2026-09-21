#!/usr/bin/env python3
"""Check the published review corpus through the authenticated website API."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clawtrap_benchmark.storage import active_release, read_file_dataset
from clawtrap_benchmark.web import app


def main():
    release = active_release()
    manifest = json.loads((ROOT / release["source_manifest"]).read_text())
    expected = {row["scenario_id"] for row in manifest["scenarios"]}
    assert len(expected) == release["case_count"] == 400
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(role="admin", username="release-check")
    # Do not contact or mutate the production review database during this check.
    with patch("clawtrap_benchmark.storage.read_persisted_case_map", return_value={}):
        index = client.get("/api/datasets").get_json()
        assert index["total"] == sum(index["counts"].values()) == 400
        seen = []
        for group in index["datasets"]:
            response = client.get("/api/all-cases", query_string={"dataset": group})
            assert response.status_code == 200, group
            cases = response.get_json()["cases"]
            assert len(cases) == index["counts"][group], group
            seen.extend(case["id"] for case in cases)
            for case in cases:
                assert not any(p.get("error") for p in case["task_file_previews"]), case["id"]
        assert len(seen) == len(set(seen)) == 400
        assert set(seen) == expected
        for retired in ("cases", "demo_cases_new_taxonomy_8", "demo1"):
            assert client.get("/api/all-cases", query_string={"dataset": retired}).status_code == 400
            assert read_file_dataset(retired) == []
        for route in ("/review", "/scenes", "/benchmark"):
            assert client.get(route).status_code == 200, route
        previews = 0
        for dataset in release["datasets"]:
            mount = json.loads((ROOT / "new_data/mount_manifests" / f"{dataset}.json").read_text())
            for mode in ("clean", "attack"):
                route = mount["modes"][mode]["review_route"]
                response = client.get(route)
                assert response.status_code == 200, (dataset, mode, route)
                assert response.data, (dataset, mode)
                response.close()
                previews += 1
    print(json.dumps({"release": release["release"], "cases": len(seen),
                      "categories": len(index["datasets"]), "previews": previews,
                      "retired_datasets_hidden": True}, indent=2))


if __name__ == "__main__":
    main()
