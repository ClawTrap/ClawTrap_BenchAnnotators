#!/usr/bin/env python3
"""Rebuild public v3 review data from the private, executable scenario plans.

The private plans remain the authority for interception targets. This script
copies only review-visible files; graders, source archives and plans stay
private. Dry-run is the default so a partial category repair is never silently
published.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
from html import unescape
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse


PUBLIC = Path(__file__).resolve().parents[1]
DEFAULT_PRIVATE = Path('/private/tmp/clawtrap-benchmark-v3-batch01')


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_changed(source: Path, target: Path, *, apply: bool) -> bool:
    if not source.is_file():
        raise FileNotFoundError(source)
    if target.is_file() and digest(source) == digest(target):
        return False
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return True


def target_url(rule: dict, old: dict | None, scenario: dict) -> str:
    match = rule['match']
    origin = urlparse(scenario['modes']['attack']['upstream_origin'])
    scheme = origin.scheme or 'https'
    host = match['host']
    route = match['route']
    if not route.startswith('/'):
        raise ValueError(f"Invalid route: {rule['id']}: {route}")
    return f'{scheme}://{host}{route}'


def target_row(rule: dict, old: dict | None, scenario: dict) -> dict:
    action = rule['action']
    result = {
        'action': action['type'],
        'methods': rule['match'].get('methods', ['GET']),
        'rule_id': rule['id'],
        'url': target_url(rule, old, scenario),
    }
    if action['type'] == 'replace_asset':
        result['replacement_asset'] = action['asset']
    elif action['type'] == 'redirect':
        result.update(location=action['location'], status=action.get('status', 302))
    elif action['type'] == 'set_headers':
        result['headers'] = action['headers']
    else:
        raise ValueError(f"Unknown action type: {action['type']}")
    # Keep review-only timing metadata, when it still describes the same rule.
    for key in ('active_turns', 'note'):
        if old and key in old:
            result[key] = old[key]
    if 'activation' in rule:
        result['activation'] = rule['activation']
    return result


def mounted_urls(scenario: dict) -> set[str]:
    urls = set()
    for mode in ('clean', 'attack'):
        definition = scenario['modes'][mode]
        origin = urlparse(definition['upstream_origin'])
        mounts = [{'host': origin.hostname, 'route': definition['route']},
                  *definition.get('page_mounts', []), *definition.get('static_mounts', [])]
        for mount in mounts:
            urls.add(f"{origin.scheme or 'https'}://{mount.get('host') or origin.hostname}{mount['route']}")
    return urls


def mounted_html_sources(scenario: dict) -> dict[str, str]:
    definition = scenario['modes']['clean']
    origin = urlparse(definition['upstream_origin'])
    mounts = [{'host': origin.hostname, 'route': definition['route'],
               'source': definition['entry_source']}, *definition.get('page_mounts', [])]
    return {f"{origin.scheme or 'https'}://{mount.get('host') or origin.hostname}{mount['route']}":
            mount['source'] for mount in mounts
            if mount['source'].lower().endswith(('.html', '.htm'))}


def task_asset_review_path(entry: dict) -> str:
    mount_target = entry.get('mount_target') or ''
    if mount_target.startswith('/workspace/'):
        return mount_target.removeprefix('/workspace/')
    return f"task_files/{entry['key']}/{Path(entry['source']).name}"


class PagePreview(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''
        self.description = ''
        self._in_title = False
        self._title_seen = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'title' and not self._title_seen:
            self._in_title = True
        elif tag == 'meta' and (str(attributes.get('name') or '').lower() == 'description'
                                 or str(attributes.get('property') or '').lower() == 'og:description'):
            self.description = self.description or attributes.get('content') or ''

    def handle_endtag(self, tag):
        if tag == 'title':
            if self._in_title:
                self._title_seen = True
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def clean_search_preview(url: str, scenario: dict, case: dict, private: Path) -> tuple[str, str]:
    if case['id'] == 'ct-oauth-v3-008':
        # The real article has a broad "Homelab" title, while its visible
        # Spotify table is the reason this result matches the task query.
        return ('Homelab | BeeDifferent · Spotify MCP scopes',
                'playlist-read-private: list + read private playlists; '
                'playlist-modify-private: create/edit private playlists.')
    source = mounted_html_sources(scenario).get(url)
    if source and (private / source).is_file():
        parser = PagePreview()
        parser.feed((private / source).read_text(encoding='utf-8', errors='replace')[:1_000_000])
        title = ' '.join(unescape(parser.title).split())
        description = ' '.join(unescape(parser.description).split())
        if title:
            return title[:180], (description or case['scenario'])[:320]
        if description:
            return f"{case['scenario']} · {urlparse(url).hostname}", description[:320]
    return f"{case['scenario']} · {urlparse(url).hostname}", case['scenario']


def update_search(search: dict, old_targets: list[dict], new_targets: list[dict],
                  case: dict, scenario: dict, private: Path) -> dict:
    row = dict(search)
    row['query_hint'] = case['scenario']
    old_urls = {target['url'] for target in old_targets}
    new_urls = {target['url'] for target in new_targets}
    old_by_id = {target['rule_id']: target['url'] for target in old_targets}
    new_by_id = {target['rule_id']: target['url'] for target in new_targets}
    translation = {old_by_id[rid]: url for rid, url in new_by_id.items()
                   if rid in old_by_id and old_by_id[rid] != url}
    mounted = mounted_urls(scenario)
    results = []
    for result in row.get('results', []):
        item = dict(result)
        if item['url'] in old_urls - new_urls:
            if item['url'] in mounted:
                # A former target can remain a clean auxiliary JSON/service
                # route that the Agent still has to consult.
                pass
            elif item['url'] in translation:
                item['url'] = translation[item['url']]
                item['title'], item['content'] = clean_search_preview(item['url'], scenario,
                                                                     case, private)
            else:
                continue
        # A controlled result must point to a served snapshot. Historical
        # synthetic task links and live, unmounted references are not
        # deterministic Agent inputs and must not remain discoverable.
        if item['url'] not in mounted and item['url'] not in new_urls:
            continue
        if item['url'] not in {r['url'] for r in results}:
            results.append(item)
    missing = new_urls - {result['url'] for result in results}
    for url in sorted(missing):
        title, content = clean_search_preview(url, scenario, case, private)
        results.append({'title': title, 'url': url,
                        'content': content,
                        'kind': 'mitm_target'})
    for item in results:
        if item['url'] in new_urls:
            item['kind'] = 'mitm_target'
            if case['id'] == 'ct-oauth-v3-008':
                item['title'], item['content'] = clean_search_preview(item['url'], scenario,
                                                                     case, private)
        elif item.get('kind') == 'mitm_target':
            item['kind'] = 'source_reference'
    # The official injected page must be discoverable before clean supporting
    # data routes. The latter can still appear for tasks that need them.
    results.sort(key=lambda item: item['url'] not in new_urls)
    row['results'] = results
    return row


def update_staged_search(override: dict, old_targets: list[dict],
                         new_targets: list[dict], scenario: dict,
                         case: dict, private: Path) -> dict:
    """Keep staged result order while translating moved target and context pages."""
    row = dict(override)
    row['query_hint'] = case['scenario']
    old_by_id = {target['rule_id']: target['url'] for target in old_targets}
    translation = {old_by_id[target['rule_id']]: target['url'] for target in new_targets
                   if target['rule_id'] in old_by_id}
    mounted = mounted_urls(scenario)
    page_sources = mounted_html_sources(scenario)
    new_targets_urls = {target['url'] for target in new_targets}
    remaining_contexts = [url for url in page_sources if url not in new_targets_urls]
    used = set()
    results = []
    for old_item in override['results']:
        item = dict(old_item)
        old_url = item['url']
        if old_url in translation:
            item['url'] = translation[old_url]
        elif item.get('kind') == 'mitm_target' and old_url not in mounted:
            # A second sync reads the already-updated public target index,
            # while the historical staged override still names its old URL.
            replacements = [url for url in new_targets_urls if url not in used]
            if len(replacements) != 1:
                raise ValueError(f"Cannot map staged target for {case['id']}: {old_url}")
            item['url'] = replacements[0]
        elif old_url not in mounted:
            replacements = [url for url in remaining_contexts if url not in used]
            if not replacements:
                # A redesigned delayed-trigger case may revisit one real page
                # instead of opening a separate earlier context page.
                continue
            if len(replacements) != 1:
                raise ValueError(f"Cannot map staged context for {case['id']}: {old_url}")
            item['url'] = replacements[0]
        if item['url'] != old_url:
            item['title'], item['content'] = clean_search_preview(item['url'], scenario,
                                                                 case, private)
        used.add(item['url'])
        results.append(item)
    row['results'] = results
    return row


def run(private: Path, apply: bool, strict: bool) -> None:
    case_paths = sorted((private / 'data/v3_batches').glob('*.json'))
    cases = [case for path in case_paths for case in load(path)['cases']]
    if len(case_paths) != 35 or len(cases) != 350 or len({case['id'] for case in cases}) != 350:
        raise ValueError('Expected exactly 35 batches and 350 unique cases')
    prior_index = load(PUBLIC / 'data/v3_mitm_targets.json')['cases']
    prior_search = load(PUBLIC / 'data/v3_controlled_search_results.json')
    staged_search = load(PUBLIC / 'data/v3_staged_search_overrides.json')['cases']
    prior_workspace = load(PUBLIC / 'data/v3_public_workspace_files.json')
    prior_services = load(PUBLIC / 'data/v3_public_service_seeds.json')
    private_triage = load(private / 'data/v3_task_form_triage.json')
    if set(prior_index) != {case['id'] for case in cases}:
        raise ValueError('Public MITM index is missing cases')
    if set(prior_search['cases']) != set(prior_index):
        raise ValueError('Public search index is missing cases')
    if set(private_triage['cases']) != set(prior_index):
        raise ValueError('Private task triage is missing cases')
    index, searches, workspace, services = {}, {}, {}, {}
    preview_assets = set()
    changed = []
    violations = []
    for case in cases:
        case_id = case['id']
        scenario = load(private / 'new_data/v3_mount_manifests' / (case_id + '.json'))
        if scenario['case_id'] != case_id:
            raise ValueError(f'Mismatched case plan: {case_id}')
        old_targets = prior_index[case_id]['targets']
        old_by_id = {target['rule_id']: target for target in old_targets}
        attack_rules = [rule for rule in scenario['interception']['rules']
                        if 'attack' in rule.get('modes', ['attack'])]
        scenario_assets = set()
        for mode in ('clean', 'attack'):
            definition = scenario['modes'][mode]
            scenario_assets.add(definition['entry_source'])
            for kind in ('page_mounts', 'static_mounts'):
                scenario_assets.update(mount['source'] for mount in definition.get(kind, []))
        for rule in scenario['interception']['rules']:
            if rule['action']['type'] == 'replace_asset':
                scenario_assets.add(rule['action']['asset'])
        for relative in scenario_assets:
            source = private / relative
            if source.is_dir():
                preview_assets.update(str(path.relative_to(private)) for path in source.rglob('*')
                                      if path.is_file())
            elif source.is_file():
                preview_assets.add(relative)
            else:
                violations.append(f'{case_id}: missing mounted source {relative}')
        for key in ('clean_asset', 'attack_asset'):
            if case.get(key) and case[key] not in scenario_assets:
                violations.append(f'{case_id}: stale case {key}: {case[key]}')
        for route in (case.get('attack_surface') or {}).get('routes', []):
            for key in ('clean_response', 'attack_response'):
                if route.get(key) and route[key] not in scenario_assets:
                    violations.append(f'{case_id}: stale case route {key}: {route[key]}')
        targets = [target_row(rule, old_by_id.get(rule['id']), scenario) for rule in attack_rules]
        if not targets:
            violations.append(f'{case_id}: no attack rule')
        for target in targets:
            if target['action'] != 'replace_asset':
                violations.append(f"{case_id}: {target['rule_id']} still uses {target['action']}")
                continue
            asset = target['replacement_asset']
            if not asset.endswith(('.html', '.htm')):
                violations.append(f'{case_id}: non-HTML attack asset {asset}')
            if not (private / asset).is_file():
                violations.append(f'{case_id}: missing attack asset {asset}')
        if 'http://' in case['task'] or 'https://' in case['task']:
            violations.append(f'{case_id}: URL in Agent task')
        index[case_id] = {'status': 'configured', 'targets': targets}
        searches[case_id] = update_search(prior_search['cases'][case_id], old_targets, targets,
                                          case, scenario, private)
        if case_id in staged_search:
            override = staged_search[case_id]
            override = update_staged_search(override, old_targets, targets,
                                            scenario, case, private)
            served = mounted_urls(scenario)
            listed = {item['url'] for item in override['results']}
            required = {target['url'] for target in targets}
            if not listed <= served or not required <= listed:
                violations.append(f'{case_id}: staged search has an unmounted or missing target')
            searches[case_id] = override
        # The reviewer also exposes some task briefs that are not mounted into
        # the runtime workspace. Preserve those explicit review entries.
        seeded = []
        seen_workspace = set()
        active_sources = {
            entry['source'] for entry in scenario.get('workspace_seed', [])
            if entry.get('agent_visible', True)
        }
        active_sources.update(
            entry['source'] for entry in scenario.get('task_assets', [])
            if entry.get('agent_visible', True)
        )
        active_sources.update(
            entry.get('path') or entry.get('source')
            for entry in case.get('task_files') or [] if isinstance(entry, dict)
        )
        case_workspace = case.get('workspace_seed')
        if isinstance(case_workspace, str):
            active_sources.add(case_workspace)
        elif isinstance(case_workspace, list):
            active_sources.update(entry['source'] for entry in case_workspace)
        current_seed_paths = {seed['source']: seed['destination']
                              for seed in scenario.get('workspace_seed', [])
                              if seed.get('agent_visible', True)}
        for entry in prior_workspace.get(case_id, []):
            source = entry['source']
            # A rehomed case may rename its brief or workspace file. The
            # previous review index is historical data, not authority for
            # what the Agent sees in the current scenario.
            if source not in active_sources:
                continue
            if source in current_seed_paths and entry['path'] != current_seed_paths[source]:
                continue
            path = private / source
            if not path.is_file():
                violations.append(f'{case_id}: missing public task source {source}')
                continue
            seeded.append({'path': entry['path'], 'sha256': digest(path), 'source': source})
            seen_workspace.add((source, entry['path']))
        for entry in scenario.get('workspace_seed', []):
            if not entry.get('agent_visible', True):
                continue
            source = entry['source']
            path = private / source
            if not path.is_file():
                violations.append(f'{case_id}: missing workspace source {source}')
                continue
            key = (source, entry['destination'])
            if key not in seen_workspace:
                seeded.append({'path': entry['destination'], 'sha256': digest(path), 'source': source})
                seen_workspace.add(key)
        indexed_sources = {entry['source'] for entry in seeded}
        for entry in scenario.get('task_assets', []):
            if not entry.get('agent_visible', True) or entry['source'] in indexed_sources:
                continue
            source = entry['source']
            path = private / source
            if not path.is_file():
                violations.append(f'{case_id}: missing agent-visible task asset {source}')
                continue
            seeded.append({'path': task_asset_review_path(entry),
                           'sha256': digest(path), 'source': source})
            indexed_sources.add(source)
        workspace[case_id] = seeded
        triage = dict(private_triage['cases'][case_id])
        triage['task_sha256'] = hashlib.sha256(case['task'].encode('utf-8')).hexdigest()
        triage['task_action'] = case.get('task_action', triage.get('task_action'))
        service = scenario.get('service_seed')
        if service:
            initial_source = private / service['source']
            if not initial_source.is_file():
                violations.append(f'{case_id}: missing isolated service seed {service["source"]}')
            else:
                public_service = {
                    'system': service['system'],
                    'get': service['get'],
                    'initial': load(initial_source),
                    'status': 'pending_runtime_e2e',
                }
                public_service['put' if 'put' in service else 'post'] = service.get('put', service.get('post'))
                services[case_id] = public_service
            triage['decision'] = 'redesigned_isolated_action'
            if triage.get('reason') is None or triage.get('reason', '').startswith('当前用户请求的交付物'):
                triage['reason'] = '任务需要在隔离服务中实际更新业务或安全状态，并通过宿主侧账本验收。'
            triage['runtime_status'] = scenario.get('execution_status', 'pending_runtime_e2e')
        elif case_id in prior_services['cases']:
            violations.append(f'{case_id}: public service seed exists but private plan has none')
        private_triage['cases'][case_id] = triage
    for path in case_paths:
        rel = path.relative_to(private)
        if (PUBLIC / rel).is_file() and load(path) == load(PUBLIC / rel):
            continue
        if copy_changed(path, PUBLIC / rel, apply=apply):
            changed.append(str(rel))
    for rel_text in sorted(preview_assets):
        if not rel_text.startswith(('new_data/clean_assets/', 'new_data/attack_assets/')):
            continue
        rel = Path(rel_text)
        if copy_changed(private / rel, PUBLIC / rel, apply=apply):
            changed.append(str(rel))
    visible_sources = {entry['source'] for entries in workspace.values() for entry in entries}
    # The private task_assets tree also contains service state and scoring
    # fixtures. Only files already public, or explicitly agent-visible in a
    # workspace seed/review brief, may cross this boundary.
    for folder in ('new_data/task_assets', 'new_data/workspace_seeds'):
        for source in sorted((private / folder).rglob('*')):
            if not source.is_file():
                continue
            rel = source.relative_to(private)
            if not (PUBLIC / rel).is_file() and str(rel) not in visible_sources:
                continue
            if copy_changed(source, PUBLIC / rel, apply=apply):
                changed.append(str(rel))
    output = {
        'data/v3_mitm_targets.json': {'cases': index},
        'data/v3_controlled_search_results.json': {**prior_search, 'cases': searches},
        'data/v3_public_workspace_files.json': workspace,
        'data/v3_task_form_triage.json': private_triage,
        'data/v3_public_service_seeds.json': {**prior_services, 'cases': services},
        'data/v3_preview_asset_index.json': {
            'version': 'clawtrap.v3.preview-assets.v1',
            'assets': sorted(preview_assets),
        },
    }
    for rel, value in output.items():
        target = PUBLIC / rel
        if not target.is_file() or load(target) != value:
            changed.append(rel)
            if apply:
                dump(target, value)
    print(json.dumps({'apply': apply, 'case_count': len(cases),
                      'rule_count': sum(len(v['targets']) for v in index.values()),
                      'changed_files': len(changed), 'sample_changes': changed[:30],
                      'violations': violations}, ensure_ascii=False, indent=2))
    if strict and violations:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, default=DEFAULT_PRIVATE)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    private = args.private.resolve()
    if args.apply and args.strict:
        # Validate the complete corpus before any review-visible file changes.
        preflight = io.StringIO()
        try:
            with redirect_stdout(preflight):
                run(private, False, True)
        except SystemExit:
            print(preflight.getvalue(), end='')
            raise
    run(private, args.apply, args.strict)
