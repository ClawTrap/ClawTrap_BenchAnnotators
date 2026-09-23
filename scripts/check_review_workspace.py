#!/usr/bin/env python3
"""Smoke test that the retired 362-case UI is no longer served."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clawtrap_benchmark.web import app


def main():
    source = ROOT / 'new_data/academic_citation_tamper_001.jsonl'
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    client = app.test_client()
    assert client.get('/review').headers['Location'] == '/login'
    assert client.get('/api/review/catalog').status_code == 401
    with client.session_transaction() as session:
        session.update(role='admin', username='workspace-check')
    for route in ('/', '/review', '/benchmark', '/design'):
        response = client.get(route)
        assert response.status_code == 302 and response.headers['Location'] == '/contract-review'
    assert client.get('/scenes').headers['Location'] == '/diversity'
    assert client.get('/api/review/catalog').status_code == 410
    assert client.get('/api/review/cases/unknown').status_code == 410
    assert client.get('/contract-review').status_code == 200
    assert client.get('/diversity').status_code == 200
    assert '逐题审核' not in client.get('/contract-review').data.decode('utf-8')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    print(json.dumps(dict(legacy_ui_retired=True, source_unchanged=True,
                          new_review_active=True, human_auth_required=True), ensure_ascii=False))


if __name__ == '__main__':
    main()
