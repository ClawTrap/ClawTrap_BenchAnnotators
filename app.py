#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from clawtrap_benchmark.constants import ATTACK_TYPES, INTERACTIVE_FORMS, TASK_TYPES
from clawtrap_benchmark.schema import normalize_case, validate_case
from clawtrap_benchmark.storage import DATA_DIR, read_cases, upsert_case


ROOT = Path(__file__).resolve().parent
SESSIONS: dict[str, dict[str, str]] = {}


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def admin_credentials() -> tuple[str, str]:
    return os.environ.get("ADMIN_USERNAME", "admin"), os.environ.get("ADMIN_PASSWORD", "admin")


def list_data_files() -> list[str]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    names = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            names.append(path.name)
    return names


def read_case_file(name: str) -> list[dict]:
    allowed = set(list_data_files())
    if name not in allowed:
        raise ValueError("unknown dataset")
    path = DATA_DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("dataset must be a JSON array")
    return data


def html_page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #20242a;
      --muted: #667085;
      --line: #d9dee7;
      --accent: #0f766e;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); }}
    header {{ display: flex; justify-content: space-between; align-items: center; padding: 14px 24px; border-bottom: 1px solid var(--line); background: var(--panel); position: sticky; top: 0; z-index: 2; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 22px; }}
    h1 {{ font-size: 22px; margin: 0; }}
    h2 {{ font-size: 18px; margin: 0 0 12px; }}
    a, button {{ color: inherit; }}
    .button, button {{ border: 1px solid var(--accent); background: var(--accent); color: white; padding: 9px 12px; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 14px; }}
    .secondary {{ background: white; color: var(--accent); }}
    .danger {{ border-color: var(--danger); background: var(--danger); }}
    .grid {{ display: grid; grid-template-columns: 320px 1fr; gap: 16px; align-items: start; }}
    .panel, .case {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 16px; }}
    .case {{ margin-bottom: 10px; }}
    .case h3 {{ margin: 0 0 8px; font-size: 15px; }}
    .meta {{ color: var(--muted); font-size: 12px; line-height: 1.5; }}
    label {{ display: block; font-weight: 600; margin: 12px 0 6px; font-size: 13px; }}
    input, select, textarea {{ width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 9px; font: inherit; background: white; }}
    textarea {{ min-height: 74px; resize: vertical; }}
    .checks {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }}
    .checks label {{ display: flex; align-items: center; gap: 6px; margin: 0; font-weight: 500; }}
    .checks input {{ width: auto; }}
    .row {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .errors {{ color: var(--danger); font-size: 13px; white-space: pre-wrap; }}
    .login {{ max-width: 380px; margin: 12vh auto; background: var(--panel); padding: 24px; border: 1px solid var(--line); border-radius: 8px; }}
    .admin-main {{ max-width: 1440px; }}
    .toolbar {{ display: grid; grid-template-columns: 180px 130px 180px 180px 140px minmax(220px, 1fr); gap: 10px; align-items: end; padding: 12px; }}
    .toolbar-actions {{ grid-column: 1 / -1; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; margin: 12px 0; }}
    .stat {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }}
    .stat strong {{ display: block; font-size: 20px; }}
    .stat span {{ color: var(--muted); font-size: 12px; }}
    .review-layout {{ display: grid; grid-template-columns: minmax(360px, 0.95fr) minmax(520px, 1.35fr); gap: 12px; align-items: start; }}
    .review-list {{ display: flex; flex-direction: column; gap: 8px; }}
    .review-item {{ width: 100%; text-align: left; background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 12px; cursor: pointer; }}
    .review-item:hover, .review-item.active {{ border-color: var(--accent); }}
    .review-item-title {{ display: block; font-size: 14px; font-weight: 700; line-height: 1.45; }}
    .review-item-attack {{ display: -webkit-box; margin-top: 8px; color: var(--muted); font-size: 12px; line-height: 1.45; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
    .review-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }}
    .pill {{ flex: none; border: 1px solid var(--line); border-radius: 999px; padding: 2px 8px; font-size: 12px; color: var(--muted); background: white; }}
    .pill.strong {{ color: var(--accent); border-color: #99d4cd; background: #effaf8; }}
    .detail-panel {{ position: sticky; top: 78px; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; max-height: calc(100vh - 100px); overflow: auto; }}
    .detail-panel h2 {{ font-size: 18px; line-height: 1.45; margin-bottom: 8px; }}
    .detail-empty {{ color: var(--muted); padding: 32px; text-align: center; }}
    dl {{ margin: 16px 0 0; }}
    dt {{ font-size: 12px; color: var(--muted); font-weight: 700; margin-top: 10px; }}
    dd {{ margin: 4px 0 0; font-size: 13px; line-height: 1.55; }}
    dd ul {{ margin: 4px 0 0; padding-left: 18px; }}
    @media (max-width: 980px) {{ .grid, .toolbar, .review-layout {{ grid-template-columns: 1fr; }} header {{ padding: 12px 16px; }} main {{ padding: 16px; }} .toolbar-actions {{ grid-column: auto; }} .detail-panel {{ position: static; max-height: none; }} }}
  </style>
</head>
<body>{body}</body>
</html>""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/admin/login":
            self.send_html(self.admin_login_page())
        elif parsed.path == "/admin/logout":
            self.logout("/admin/login")
        elif parsed.path == "/admin":
            self.require_admin_html(self.admin_page)
        elif parsed.path == "/api/admin/cases":
            self.require_admin_json(self.api_admin_cases)
        elif parsed.path == "/login":
            self.send_html(self.login_page())
        elif parsed.path == "/logout":
            self.logout("/login")
        elif parsed.path == "/api/cases":
            self.require_user_json(self.api_cases)
        else:
            self.require_user_html(self.index_page)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/admin/login":
            self.admin_login()
        elif parsed.path == "/login":
            self.login()
        elif parsed.path == "/api/cases":
            self.require_user_json(self.save_case)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def current_session(self) -> dict[str, str] | None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get("session")
        if not token:
            return None
        return SESSIONS.get(token.value)

    def current_user(self) -> str | None:
        session = self.current_session()
        if not session or session.get("role") != "annotator":
            return None
        return session.get("username")

    def current_admin(self) -> str | None:
        session = self.current_session()
        if not session or session.get("role") != "admin":
            return None
        return session.get("username")

    def require_user_html(self, fn) -> None:
        user = self.current_user()
        if not user:
            self.redirect("/login")
            return
        self.send_html(fn(user))

    def require_user_json(self, fn) -> None:
        user = self.current_user()
        if not user:
            self.send_json({"error": "not logged in"}, HTTPStatus.UNAUTHORIZED)
            return
        fn(user)

    def require_admin_html(self, fn) -> None:
        admin = self.current_admin()
        if not admin:
            self.redirect("/admin/login")
            return
        self.send_html(fn(admin))

    def require_admin_json(self, fn) -> None:
        admin = self.current_admin()
        if not admin:
            self.send_json({"error": "admin login required"}, HTTPStatus.UNAUTHORIZED)
            return
        fn(admin)

    def login_page(self) -> bytes:
        return html_page("ClawTrap 登录", """
<main><section class="login">
  <h1>ClawTrap Benchmark</h1>
  <form method="post" action="/login">
    <label>标注员用户名</label>
    <input name="username" required autocomplete="username" autofocus>
    <div style="height:14px"></div>
    <button type="submit">登录</button>
  </form>
</section></main>
""")

    def admin_login_page(self, error: str = "") -> bytes:
        error_html = f'<div class="errors">{error}</div>' if error else ""
        return html_page("ClawTrap 管理员登录", f"""
<main><section class="login">
  <h1>管理员审阅</h1>
  <form method="post" action="/admin/login">
    <label>管理员账号</label>
    <input name="username" required autocomplete="username" autofocus>
    <label>密码</label>
    <input name="password" type="password" required autocomplete="current-password">
    {error_html}
    <div style="height:14px"></div>
    <button type="submit">登录</button>
  </form>
  <p class="meta">生产部署前请在 .env 中设置 ADMIN_USERNAME 和 ADMIN_PASSWORD。</p>
</section></main>
""")

    def login(self) -> None:
        data = self.read_form()
        username = data.get("username", [""])[0].strip()
        if not username:
            self.send_html(self.login_page(), HTTPStatus.BAD_REQUEST)
            return
        token = secrets.token_urlsafe(24)
        SESSIONS[token] = {"role": "annotator", "username": username}
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()

    def admin_login(self) -> None:
        data = self.read_form()
        username = data.get("username", [""])[0].strip()
        password = data.get("password", [""])[0]
        expected_username, expected_password = admin_credentials()
        if not secrets.compare_digest(username, expected_username) or not secrets.compare_digest(password, expected_password):
            self.send_html(self.admin_login_page("账号或密码不正确"), HTTPStatus.UNAUTHORIZED)
            return
        token = secrets.token_urlsafe(24)
        SESSIONS[token] = {"role": "admin", "username": username}
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", "/admin")
        self.send_header("Set-Cookie", f"session={token}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()

    def logout(self, location: str) -> None:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        token = cookie.get("session")
        if token:
            SESSIONS.pop(token.value, None)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.send_header("Set-Cookie", "session=; Path=/; Max-Age=0")
        self.end_headers()

    def index_page(self, user: str) -> bytes:
        return html_page("ClawTrap Benchmark 标注", f"""
<header>
  <h1>ClawTrap Benchmark 标注</h1>
  <div class="row"><span class="meta">{user}</span><a class="button secondary" href="/logout">退出</a></div>
</header>
<main>
  <div class="grid">
    <section class="panel">
      <h2>我的场景</h2>
      <div id="caseList"></div>
    </section>
    <section class="panel">
      <h2>设计场景</h2>
      <form id="caseForm">
        <input type="hidden" name="id">
        <label>任务类型</label>
        <select name="task_type" required>{self.options(TASK_TYPES)}</select>
        <label>攻击类型</label>
        <select name="attack_type" required>{self.options(ATTACK_TYPES)}</select>
        <label>MITM 植入形式</label>
        <div class="checks">{self.checkboxes(INTERACTIVE_FORMS)}</div>
        <label>任务描述 task</label>
        <textarea name="task" required></textarea>
        <label>任务目标 target</label>
        <textarea name="target" required></textarea>
        <label>攻击方法 attack_method</label>
        <textarea name="attack_method" required></textarea>
        <label>成功防御状态 success_states（每行一条）</label>
        <textarea name="success_states" required></textarea>
        <label>失败状态 failure_states（每行一条）</label>
        <textarea name="failure_states" required></textarea>
        <label>攻击逻辑 logic</label>
        <textarea name="logic" required></textarea>
        <label>Metadata（每行一条）</label>
        <textarea name="metadata" required></textarea>
        <div class="errors" id="errors"></div>
        <div class="row" style="margin-top:14px">
          <button type="button" onclick="saveCase('draft')">保存草稿</button>
          <button type="button" class="secondary" onclick="saveCase('submitted')">提交</button>
          <button type="button" class="secondary" onclick="clearForm()">新建</button>
        </div>
      </form>
    </section>
  </div>
</main>
<script>
const listEl = document.getElementById('caseList');
const form = document.getElementById('caseForm');
const errors = document.getElementById('errors');

function lines(value) {{
  return value.split('\\n').map(v => v.trim()).filter(Boolean);
}}
function fillLines(items) {{
  return Array.isArray(items) ? items.join('\\n') : '';
}}
function formData(status) {{
  const data = Object.fromEntries(new FormData(form).entries());
  data.status = status;
  data.success_states = lines(form.success_states.value);
  data.failure_states = lines(form.failure_states.value);
  data.metadata = lines(form.metadata.value);
  data.interactive_form = [...form.querySelectorAll('input[name="interactive_form"]:checked')].map(i => i.value);
  return data;
}}
function clearForm() {{
  form.reset();
  form.id.value = '';
  errors.textContent = '';
}}
function editCase(item) {{
  clearForm();
  for (const key of ['id','task','target','task_type','attack_method','logic','attack_type']) {{
    form[key].value = item[key] || '';
  }}
  form.success_states.value = fillLines(item.success_states);
  form.failure_states.value = fillLines(item.failure_states);
  form.metadata.value = fillLines(item.metadata);
  for (const box of form.querySelectorAll('input[name="interactive_form"]')) {{
    box.checked = (item.interactive_form || []).includes(box.value);
  }}
  window.scrollTo({{top: 0, behavior: 'smooth'}});
}}
async function loadCases() {{
  const res = await fetch('/api/cases');
  const data = await res.json();
  listEl.innerHTML = '';
  for (const item of data.cases) {{
    const node = document.createElement('article');
    node.className = 'case';
    node.innerHTML = `<h3>${{escapeHtml(item.task || '(未命名任务)')}}</h3>
      <div class="meta">${{escapeHtml(item.status)}} · ${{escapeHtml(item.task_type)}} · ${{escapeHtml(item.attack_type)}}<br>${{escapeHtml((item.interactive_form || []).join(' / '))}}</div>
      <div style="height:10px"></div><button type="button" class="secondary">编辑</button>`;
    node.querySelector('button').onclick = () => editCase(item);
    listEl.appendChild(node);
  }}
}}
async function saveCase(status) {{
  errors.textContent = '';
  const res = await fetch('/api/cases', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(formData(status))
  }});
  const data = await res.json();
  if (!res.ok) {{
    errors.textContent = (data.errors || [data.error || '保存失败']).join('\\n');
    return;
  }}
  editCase(data.case);
  await loadCases();
}}
function escapeHtml(value) {{
  return String(value || '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}
loadCases();
</script>
""")

    def admin_page(self, admin: str) -> bytes:
        return html_page("ClawTrap 数据审阅", f"""
<header>
  <h1>ClawTrap 数据审阅</h1>
  <div class="row"><span class="meta">admin: {admin}</span><a class="button secondary" href="/admin/logout">退出</a></div>
</header>
<main class="admin-main">
  <section class="panel toolbar">
    <div>
      <label>数据集</label>
      <select id="dataset"></select>
    </div>
    <div>
      <label>状态</label>
      <select id="statusFilter"><option value="">全部</option><option value="draft">draft</option><option value="submitted">submitted</option></select>
    </div>
    <div>
      <label>攻击类型</label>
      <select id="attackFilter"><option value="">全部</option>{self.options(ATTACK_TYPES)}</select>
    </div>
    <div>
      <label>任务类型</label>
      <select id="taskFilter"><option value="">全部</option>{self.options(TASK_TYPES)}</select>
    </div>
    <div>
      <label>植入形式</label>
      <select id="formFilter"><option value="">全部</option>{self.options(INTERACTIVE_FORMS)}</select>
    </div>
    <div class="search-box">
      <label>搜索</label>
      <input id="search" placeholder="task / target / attack_method / id / owner">
    </div>
    <div class="row toolbar-actions">
      <button type="button" onclick="loadCases()">刷新</button>
      <button type="button" class="secondary" onclick="downloadFiltered()">导出当前筛选</button>
    </div>
  </section>
  <section class="stats" id="stats"></section>
  <section class="review-layout">
    <div class="review-list" id="reviewList"></div>
    <aside class="detail-panel" id="detailPanel"></aside>
  </section>
</main>
<script>
let allCases = [];
let filteredCases = [];
let selectedId = null;
const dataset = document.getElementById('dataset');
const controls = ['statusFilter','attackFilter','taskFilter','formFilter','search'].map(id => document.getElementById(id));

async function init() {{
  const res = await fetch('/api/admin/cases');
  const data = await res.json();
  dataset.innerHTML = data.datasets.map(name => `<option value="${{escapeHtml(name)}}">${{escapeHtml(name)}}</option>`).join('');
  dataset.value = data.dataset;
  allCases = data.cases;
  controls.concat(dataset).forEach(el => el.addEventListener('input', () => dataset === el ? loadCases() : render()));
  render();
}}
async function loadCases() {{
  const res = await fetch(`/api/admin/cases?dataset=${{encodeURIComponent(dataset.value)}}`);
  const data = await res.json();
  allCases = data.cases || [];
  render();
}}
function render() {{
  const status = document.getElementById('statusFilter').value;
  const attack = document.getElementById('attackFilter').value;
  const task = document.getElementById('taskFilter').value;
  const form = document.getElementById('formFilter').value;
  const q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = allCases.filter(item => {{
    if (status && item.status !== status) return false;
    if (attack && item.attack_type !== attack) return false;
    if (task && item.task_type !== task) return false;
    if (form && !(item.interactive_form || []).includes(form)) return false;
    if (q) {{
      const haystack = JSON.stringify(item).toLowerCase();
      if (!haystack.includes(q)) return false;
    }}
    return true;
  }});
  renderStats();
  renderList();
  renderDetail();
}}
function renderStats() {{
  const submitted = filteredCases.filter(c => c.status === 'submitted').length;
  const draft = filteredCases.filter(c => c.status === 'draft').length;
  document.getElementById('stats').innerHTML = [
    stat('当前筛选', filteredCases.length),
    stat('全部数据', allCases.length),
    stat('submitted', submitted),
    stat('draft', draft),
    stat('标注员数', new Set(filteredCases.map(c => c.owner || '')).size)
  ].join('');
}}
function stat(label, value) {{
  return `<article class="stat"><strong>${{value}}</strong><span>${{escapeHtml(label)}}</span></article>`;
}}
function renderList() {{
  if (!filteredCases.some(item => item.id === selectedId)) {{
    selectedId = filteredCases[0]?.id || null;
  }}
  const list = document.getElementById('reviewList');
  list.innerHTML = filteredCases.map(item => `
    <button class="review-item ${{item.id === selectedId ? 'active' : ''}}" type="button" onclick="selectCase('${{escapeAttr(item.id)}}')">
      <span class="review-item-title">${{escapeHtml(item.task || '(未命名任务)')}}</span>
      <span class="review-item-attack">${{escapeHtml(item.attack_method || '')}}</span>
      <span class="review-tags">
        <span class="pill strong">${{escapeHtml(item.status || 'draft')}}</span>
        <span class="pill">${{escapeHtml(item.task_type)}}</span>
        <span class="pill">${{escapeHtml(item.attack_type)}}</span>
        <span class="pill">${{escapeHtml((item.interactive_form || []).join('/'))}}</span>
      </span>
    </button>
  `).join('') || '<div class="detail-empty">没有匹配的数据</div>';
}}
function selectCase(id) {{
  selectedId = id;
  renderList();
  renderDetail();
}}
function renderDetail() {{
  const panel = document.getElementById('detailPanel');
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) {{
    panel.innerHTML = '<div class="detail-empty">选择左侧条目查看详情</div>';
    return;
  }}
  panel.innerHTML = `
    <h2>${{escapeHtml(item.task || '(未命名任务)')}}</h2>
    <div class="meta">${{escapeHtml(item.id)}} · ${{escapeHtml(item.owner)}} · ${{escapeHtml(item.created_at || '')}}</div>
    <div class="review-tags">
      <span class="pill strong">${{escapeHtml(item.status || 'draft')}}</span>
      <span class="pill">${{escapeHtml(item.task_type)}}</span>
      <span class="pill">${{escapeHtml(item.attack_type)}}</span>
      <span class="pill">${{escapeHtml((item.interactive_form || []).join('/'))}}</span>
    </div>
    <dl>
      <dt>Attack Method</dt><dd>${{escapeHtml(item.attack_method)}}</dd>
      <dt>Success States</dt><dd>${{listText(item.success_states)}}</dd>
      <dt>Failure States</dt><dd>${{listText(item.failure_states)}}</dd>
      <dt>Metadata</dt><dd>${{listText(item.metadata)}}</dd>
      <dt>Target</dt><dd>${{escapeHtml(item.target)}}</dd>
      <dt>Logic</dt><dd>${{escapeHtml(item.logic)}}</dd>
    </dl>
  `;
}}
function listText(items) {{
  return Array.isArray(items) ? `<ul>${{items.map(item => `<li>${{escapeHtml(item)}}</li>`).join('')}}</ul>` : escapeHtml(items || '');
}}
function downloadFiltered() {{
  const blob = new Blob([JSON.stringify(filteredCases, null, 2)], {{type: 'application/json;charset=utf-8'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `clawtrap-filtered-${{dataset.value}}`;
  a.click();
  URL.revokeObjectURL(url);
}}
function escapeHtml(value) {{
  return String(value || '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}
function escapeAttr(value) {{
  return String(value || '').replace(/[\\'\\\\]/g, ch => ch === '\\\\' ? '\\\\\\\\' : "\\\\'");
}}
init();
</script>
""")

    def api_cases(self, user: str) -> None:
        cases = [case for case in read_cases() if case.get("owner") in (user, "llm_seed")]
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        self.send_json({"cases": cases})

    def api_admin_cases(self, admin: str) -> None:
        query = parse_qs(urlparse(self.path).query)
        datasets = list_data_files()
        dataset = query.get("dataset", [datasets[0] if datasets else "cases.json"])[0]
        if dataset not in datasets and "cases.json" in datasets:
            dataset = "cases.json"
        try:
            cases = read_case_file(dataset) if datasets else []
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        self.send_json({"admin": admin, "dataset": dataset, "datasets": datasets, "cases": cases})

    def save_case(self, user: str) -> None:
        try:
            raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")) or b"{}")
        except json.JSONDecodeError:
            self.send_json({"error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return
        status = raw.get("status", "draft")
        if status not in ("draft", "submitted"):
            self.send_json({"error": "invalid status"}, HTTPStatus.BAD_REQUEST)
            return
        raw["status"] = status
        case = normalize_case(raw, owner=user, source=raw.get("source") or "manual")
        errors = validate_case(case, for_submit=status == "submitted")
        if errors:
            self.send_json({"errors": errors}, HTTPStatus.BAD_REQUEST)
            return
        saved = upsert_case(case, owner=user, source=case.get("source") or "manual")
        self.send_json({"case": saved})

    def read_form(self) -> dict[str, list[str]]:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")).decode("utf-8")
        return parse_qs(body)

    def options(self, values: list[str]) -> str:
        return "".join(f'<option value="{value}">{value}</option>' for value in values)

    def checkboxes(self, values: list[str]) -> str:
        return "".join(f'<label><input type="checkbox" name="interactive_form" value="{value}">{value}</label>' for value in values)

    def send_html(self, body: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    load_dotenv()
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))
    if os.environ.get("ADMIN_PASSWORD") is None:
        print("Warning: ADMIN_PASSWORD is not set. Development admin credential is admin/admin.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"ClawTrap benchmark app running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
