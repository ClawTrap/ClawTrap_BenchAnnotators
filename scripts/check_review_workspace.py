#!/usr/bin/env python3
"""Exercise review-only persistence without touching source cases or a live DB."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clawtrap_benchmark import storage
from clawtrap_benchmark.web import app


def main():
    source = ROOT / 'new_data/academic_citation_tamper_001.jsonl'
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'cases.json'
        with patch.object(storage, 'CASES_PATH', path), patch.object(storage, 'DATA_DIR', Path(directory)), \
                patch.object(storage, 'database_configured', return_value=False), \
                patch.object(storage, 'use_database', return_value=False), \
                patch.object(storage, 'is_vercel_runtime', return_value=False):
            client = app.test_client()
            assert client.get('/api/review/catalog').status_code == 401
            with client.session_transaction() as session:
                session.update(role='admin', username='workspace-check')
            response = client.get('/api/review/catalog')
            assert response.status_code == 200
            rows = response.get_json()['cases']
            assert len(rows) == len({r['id'] for r in rows}) == 400
            for row in rows:
                assert row['scenario_key'] == row['declared_workflow']
                assert row['domain'] == row['declared_domain']
            row = next(r for r in rows if r['dataset'] == 'academic_citation_tamper_001')
            endpoint = '/api/review/cases/' + row['id']
            assessment = dict(checks=dict(intent='pass', causality='question', realism='pass', diversity='fail'),
                              issues=['template_repeat'], notes='Review-only persistence check')
            response = client.post(endpoint, json=dict(assessment=assessment))
            assert response.status_code == 200, response.get_json()
            assert response.get_json()['decision'] == ''
            assert client.get(endpoint).get_json()['case']['design_review']['notes'] == assessment['notes']
            response = client.post(endpoint, json=dict(assessment=assessment, decision='accepted'))
            assert response.status_code == 200, response.get_json()
            assert response.get_json()['selected'] is True
            listing = client.get('/api/review/catalog').get_json()['cases']
            saved = next(r for r in listing if r['id'] == row['id'])
            assert saved['decision'] == 'accepted' and saved['assessment']['checks']['diversity'] == 'fail'
            response = client.post(endpoint, json=dict(assessment=assessment, decision='clear'))
            assert response.status_code == 200 and not response.get_json()['selected']
            assert client.post(endpoint, json=dict(assessment={'checks': {'intent': 'invented'}})).status_code == 400
            assert client.get('/api/review/cases/unknown').status_code == 404
            for route in ('/', '/review', '/scenes', '/diversity', '/benchmark', '/static/review.css', '/static/review.js', '/static/vendor/lucide.min.js'):
                response = client.get(route)
                assert response.status_code == 200, route
                response.close()
            with client.session_transaction() as session:
                session.clear()
            with patch.dict('os.environ', CLAWTRAP_LAB_PROXY_TOKEN='test-proxy'):
                assert client.get('/api/review/catalog', headers={'X-ClawTrap-Lab-Proxy':'test-proxy'}).status_code == 401
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    print(json.dumps(dict(cases=400, own_labels_preserved=True, source_unchanged=True,
                          notes_persist=True, decision_and_undo=True, human_auth_required=True), indent=2))


if __name__ == '__main__':
    main()
