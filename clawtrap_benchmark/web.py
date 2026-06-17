from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, request, session

from .constants import ATTACK_TYPES, INTERACTIVE_FORMS, TASK_TYPES
from .schema import normalize_case, validate_case
from .schema import utc_now
from .storage import DEFAULT_DATASET, add_case_review, list_datasets, read_cases, read_dataset, upsert_case


ROOT = Path(__file__).resolve().parents[1]


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


def options(values: list[str]) -> str:
    return "".join(f'<option value="{value}">{value}</option>' for value in values)


def checkboxes(values: list[str]) -> str:
    return "".join(f'<label class="choice-pill"><input type="checkbox" name="interactive_form" value="{value}"><span>{value}</span></label>' for value in values)


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');
    :root {{
      --paper:#fbfaf7; --paper-deep:#f3efe6; --panel:#ffffff; --panel-soft:#f8f6f1;
      --text:#132033; --ink:#213149; --muted:#667386; --line:rgba(19,32,51,.12);
      --line-strong:rgba(19,32,51,.22); --navy:#162236; --navy-soft:#253750;
      --accent:#8a623d; --accent-strong:#6e4e2d; --accent-soft:#f5eee5;
      --teal:#0f766e; --danger:#b42318; --shadow:0 14px 34px rgba(19,32,51,.07);
    }}
    * {{ box-sizing:border-box; }}
    html {{ background:var(--paper); }}
    body {{
      margin:0; min-height:100vh; font-family:'Source Sans 3',-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      background:
        radial-gradient(circle at 10% 8%, rgba(138,98,61,.09), transparent 30%),
        radial-gradient(circle at 88% 10%, rgba(22,34,53,.08), transparent 34%),
        linear-gradient(180deg, var(--paper) 0%, var(--paper-deep) 54%, var(--paper) 100%);
      color:var(--ink); letter-spacing:.005em;
    }}
    body::before {{
      content:''; position:fixed; inset:0; z-index:-1; pointer-events:none;
      background-image:linear-gradient(rgba(19,32,51,.026) 1px, transparent 1px),linear-gradient(90deg, rgba(19,32,51,.026) 1px, transparent 1px);
      background-size:24px 24px; mask-image:linear-gradient(180deg,rgba(0,0,0,.2),transparent 68%);
    }}
    header {{
      width:min(1480px,calc(100vw - 44px)); margin:16px auto 0; display:flex; justify-content:space-between;
      align-items:center; gap:18px; padding:12px 18px; border:1px solid var(--line); border-radius:999px;
      background:rgba(255,255,255,.9); backdrop-filter:blur(12px); position:sticky; top:12px; z-index:2;
      box-shadow:0 14px 36px rgba(19,32,51,.08);
    }}
    main {{ max-width:1180px; margin:0 auto; padding:28px 24px 48px; }}
    h1,h2,h3 {{ color:var(--text); }}
    h1 {{ font-family:'Cormorant Garamond',Georgia,serif; font-size:29px; margin:0; font-weight:600; font-style:italic; letter-spacing:-.02em; }}
    h2 {{ font-family:'Cormorant Garamond',Georgia,serif; font-size:27px; margin:0 0 14px; font-weight:600; letter-spacing:-.02em; }}
    .brand-lockup {{ display:flex; align-items:center; gap:12px; min-width:0; }}
    .brand-mark {{ width:36px; height:36px; border-radius:999px; display:grid; place-items:center; background:linear-gradient(150deg,var(--navy),var(--navy-soft)); color:#f8f4ee; font-family:'Cormorant Garamond',Georgia,serif; font-size:20px; font-weight:700; font-style:italic; }}
    .brand-subtitle {{ color:var(--muted); font-size:12px; line-height:1; margin-top:2px; }}
    .top-nav {{ display:flex; align-items:center; gap:8px; }}
    .hero {{
      position:relative; margin:28px 0 18px; padding:26px; border:1px solid var(--line); border-radius:8px;
      background:linear-gradient(135deg,rgba(255,255,255,.94),rgba(248,246,241,.88)); box-shadow:var(--shadow); overflow:hidden;
    }}
    .hero::after {{ content:''; position:absolute; right:-80px; top:-90px; width:240px; height:240px; border-radius:50%; background:radial-gradient(circle,rgba(138,98,61,.14),transparent 68%); pointer-events:none; }}
    .hero.compact {{ padding:24px 26px; }}
    .eyebrow {{ display:inline-flex; padding:0 0 5px; border-bottom:1px solid rgba(138,98,61,.28); color:var(--accent-strong); font-family:'Source Sans 3',sans-serif; font-size:11px; font-weight:700; letter-spacing:.11em; text-transform:uppercase; }}
    .hero-title {{ max-width:900px; margin:12px 0 10px; font-family:'Cormorant Garamond',Georgia,serif; font-size:clamp(2rem,4.2vw,3.6rem); line-height:1.02; letter-spacing:-.035em; color:var(--text); font-weight:600; }}
    .hero-copy {{ max-width:780px; color:var(--muted); font-size:16px; line-height:1.75; margin:0; }}
    .section-heading {{ display:flex; justify-content:space-between; align-items:flex-end; gap:12px; margin-bottom:14px; }}
    .section-kicker {{ margin:0; color:var(--accent-strong); font-size:11px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
    .button, button {{
      border:1px solid var(--navy); background:var(--navy); color:#fffefa; padding:9px 13px;
      border-radius:999px; cursor:pointer; text-decoration:none; font-size:14px; font-weight:650;
      box-shadow:0 1px 0 rgba(15,23,42,.04);
    }}
    button:hover,.button:hover {{ background:var(--navy-soft); }}
    .secondary {{ background:transparent; color:var(--navy); border-color:var(--line-strong); box-shadow:none; }}
    .secondary:hover {{ background:var(--panel-soft); color:var(--navy); }}
    .panel,.case,.login,.detail-panel,.stat,.review-item {{
      background:rgba(255,255,255,.92); border:1px solid var(--line); border-radius:8px; box-shadow:var(--shadow);
    }}
    .panel {{ padding:18px; }}
    .grid {{ display:grid; grid-template-columns:340px minmax(0,1fr); gap:18px; align-items:start; }}
    .case {{ margin-bottom:10px; padding:13px; box-shadow:none; }}
    .case h3 {{ margin:0 0 8px; font-size:14px; line-height:1.45; }}
    .meta {{ color:var(--muted); font-size:12px; line-height:1.55; }}
    label {{ display:block; font-weight:680; margin:12px 0 6px; font-size:12px; color:#344054; }}
    input,select,textarea {{
      width:100%; border:1px solid var(--line); border-radius:7px; padding:9px 10px; font:inherit;
      background:rgba(255,255,255,.92); outline:none; transition:border-color .12s, box-shadow .12s;
    }}
    input:focus,select:focus,textarea:focus {{ border-color:var(--accent); box-shadow:0 0 0 3px rgba(138,98,61,.13); }}
    textarea {{ min-height:78px; resize:vertical; }}
    .checks {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; }}
    .choice-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }}
    .choice-card {{ display:block; min-height:150px; padding:18px; color:var(--ink); text-decoration:none; background:rgba(255,255,255,.9); border:1px solid var(--line); border-radius:8px; box-shadow:var(--shadow); transition:transform .14s, border-color .14s, box-shadow .14s; }}
    .choice-card:hover {{ transform:translateY(-2px); border-color:var(--line-strong); box-shadow:0 18px 42px rgba(19,32,51,.1); }}
    .choice-card strong {{ display:block; margin:8px 0; color:var(--text); font-family:'Cormorant Garamond',Georgia,serif; font-size:27px; line-height:1.05; }}
    .choice-card span {{ color:var(--muted); font-size:14px; line-height:1.55; }}
    .choice-number {{ width:30px; height:30px; display:grid; place-items:center; color:#fffefa; background:var(--navy); border-radius:999px; font-size:13px; font-weight:700; }}
    .choice-pill {{ position:relative; display:flex; align-items:center; justify-content:center; margin:0; padding:0; cursor:pointer; }}
    .choice-pill input {{ position:absolute; opacity:0; pointer-events:none; }}
    .choice-pill span {{ width:100%; min-height:38px; display:flex; align-items:center; justify-content:center; padding:8px 10px; border:1px solid var(--line); border-radius:999px; background:var(--panel-soft); color:var(--muted); font-size:13px; font-weight:650; transition:background .12s,border-color .12s,color .12s,box-shadow .12s; }}
    .choice-pill input:checked + span {{ border-color:rgba(138,98,61,.42); background:var(--accent-soft); color:var(--accent-strong); box-shadow:0 0 0 3px rgba(138,98,61,.1); }}
    .select-shell {{ position:relative; }}
    .select-shell select {{ appearance:none; padding-right:34px; background:linear-gradient(180deg,#fff,#fbf8f2); }}
    .select-shell::after {{ content:'⌄'; position:absolute; right:12px; bottom:8px; color:var(--accent-strong); pointer-events:none; font-weight:700; }}
    .score-grid {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:10px; }}
    .score-grid label {{ margin-top:0; }}
    .score-grid input {{ text-align:center; font-weight:700; }}
    .score-summary {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }}
    .row {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .errors {{ color:var(--danger); font-size:13px; white-space:pre-wrap; margin-top:8px; }}
    .login {{ max-width:430px; margin:12vh auto; padding:30px; background:linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,246,241,.9)); }}
    .login h1 {{ margin-bottom:18px; }}
    .admin-main {{ max-width:1480px; }}
    .toolbar {{
      display:grid; grid-template-columns:180px 130px 180px 180px 140px minmax(220px,1fr);
      gap:10px; align-items:end; padding:14px; box-shadow:0 10px 26px rgba(19,32,51,.045);
    }}
    .toolbar label {{ margin-top:0; }}
    .toolbar-actions {{ grid-column:1/-1; }}
    .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(128px,1fr)); gap:10px; margin:14px 0; }}
    .stat {{ padding:13px 14px; box-shadow:none; background:linear-gradient(180deg,#fffefa,#f9f5ed); }}
    .stat strong {{ display:block; font-size:22px; line-height:1; }}
    .stat span {{ display:block; color:var(--muted); font-size:12px; margin-top:6px; }}
    .review-layout {{ display:grid; grid-template-columns:minmax(380px,.92fr) minmax(540px,1.35fr); gap:14px; align-items:start; }}
    .review-list {{ display:flex; flex-direction:column; gap:9px; }}
    .review-item {{
      width:100%; text-align:left; color:var(--text); padding:14px; cursor:pointer; box-shadow:none;
      transition:border-color .12s, transform .12s, box-shadow .12s;
    }}
    .review-item:hover {{ border-color:var(--line-strong); transform:translateY(-1px); box-shadow:0 12px 28px rgba(19,32,51,.07); background:#fff; }}
    .review-item.active {{ border-color:var(--accent); box-shadow:0 0 0 3px rgba(138,98,61,.12); }}
    .review-item-title {{ display:block; font-size:14px; font-weight:720; line-height:1.5; }}
    .review-item-attack {{
      display:-webkit-box; margin-top:8px; color:var(--muted); font-size:12px; line-height:1.5;
      -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }}
    .review-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }}
    .pill {{ flex:none; border:1px solid var(--line); border-radius:999px; padding:3px 8px; font-size:11px; color:var(--muted); background:var(--panel-soft); }}
    .pill.strong {{ color:var(--accent-strong); border-color:rgba(138,98,61,.28); background:var(--accent-soft); }}
    .detail-panel {{ position:sticky; top:82px; padding:20px; max-height:calc(100vh - 108px); overflow:auto; background:linear-gradient(180deg,rgba(255,255,255,.96),rgba(250,248,244,.92)); }}
    .detail-panel h2 {{ font-size:19px; line-height:1.48; margin:0 0 8px; }}
    .detail-empty {{ color:var(--muted); padding:40px 28px; text-align:center; background:var(--panel-soft); border:1px dashed var(--line-strong); border-radius:8px; }}
    dl {{ margin:18px 0 0; display:grid; gap:12px; }}
    dt {{ font-size:11px; color:var(--muted); font-weight:760; text-transform:uppercase; margin:0; }}
    dd {{ margin:4px 0 0; font-size:13px; line-height:1.62; background:var(--panel-soft); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }}
    dd ul {{ margin:0; padding-left:18px; }}
    @media (max-width:980px) {{
      .grid,.toolbar,.review-layout,.choice-grid,.score-grid {{ grid-template-columns:1fr; }}
      header {{ padding:12px 16px; }} main {{ padding:16px; }}
      .toolbar-actions {{ grid-column:auto; }} .detail-panel {{ position:static; max-height:none; }}
    }}
  </style>
</head>
<body>{body}</body>
</html>"""


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

    @app.get("/")
    def index():
        if session.get("role") != "annotator":
            return redirect("/login")
        return menu_page(session["username"])

    @app.get("/design")
    def design():
        if session.get("role") != "annotator":
            return redirect("/login")
        return design_page(session["username"])

    @app.get("/review")
    def review():
        if session.get("role") != "annotator":
            return redirect("/login")
        return review_page(session["username"])

    @app.get("/scenes")
    def scenes():
        if session.get("role") != "annotator":
            return redirect("/login")
        return scenes_page(session["username"])

    @app.get("/login")
    def login_page():
        return page("ClawTrap 登录", """
<main><section class="login">
  <div class="brand-lockup" style="margin-bottom:18px">
    <div class="brand-mark">C</div>
    <div><h1>ClawTrap</h1><div class="brand-subtitle">Benchmark annotation workspace</div></div>
  </div>
  <form method="post" action="/login">
    <label>标注员用户名</label><input name="username" required autocomplete="username" autofocus>
    <div style="height:14px"></div><button type="submit">登录</button>
  </form>
</section></main>""")

    @app.post("/login")
    def login():
        username = request.form.get("username", "").strip()
        if not username:
            return login_page(), 400
        session.clear()
        session["role"] = "annotator"
        session["username"] = username
        return redirect("/")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/admin")
    def admin():
        if session.get("role") != "admin":
            return redirect("/admin/login")
        return admin_page(session["username"])

    @app.get("/admin/login")
    def admin_login_page():
        return render_admin_login()

    @app.post("/admin/login")
    def admin_login():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        expected_username, expected_password = admin_credentials()
        if not secrets.compare_digest(username, expected_username) or not secrets.compare_digest(password, expected_password):
            return render_admin_login("账号或密码不正确"), 401
        session.clear()
        session["role"] = "admin"
        session["username"] = username
        return redirect("/admin")

    @app.get("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect("/admin/login")

    @app.get("/api/cases")
    def api_cases():
        if session.get("role") != "annotator":
            return jsonify({"error": "not logged in"}), 401
        username = session["username"]
        cases = [case for case in read_cases() if case.get("owner") in (username, "llm_seed")]
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases})

    @app.post("/api/cases")
    def save_case():
        if session.get("role") != "annotator":
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        status = raw.get("status", "draft")
        if status not in ("draft", "submitted"):
            return jsonify({"error": "invalid status"}), 400
        raw["status"] = status
        case = normalize_case(raw, owner=session["username"], source=raw.get("source") or "manual")
        errors = validate_case(case, for_submit=status == "submitted")
        if errors:
            return jsonify({"errors": errors}), 400
        try:
            saved = upsert_case(case, owner=session["username"], source=case.get("source") or "manual")
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({"case": saved})

    @app.get("/api/all-cases")
    def api_all_cases():
        if session.get("role") != "annotator":
            return jsonify({"error": "not logged in"}), 401
        cases = read_cases()
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases})

    @app.post("/api/cases/<case_id>/reviews")
    def save_review(case_id: str):
        if session.get("role") != "annotator":
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        errors = []
        review: dict[str, Any] = {
            "reviewer": session["username"],
            "created_at": utc_now(),
            "comment": str(raw.get("comment", "")).strip(),
        }
        for key in ("feasibility", "accuracy", "clarity", "overall"):
            try:
                score = int(raw.get(key))
            except (TypeError, ValueError):
                errors.append(f"{key} 必须是 1-5 的整数")
                continue
            if score < 1 or score > 5:
                errors.append(f"{key} 必须在 1-5 之间")
            review[key] = score
        if errors:
            return jsonify({"errors": errors}), 400
        try:
            saved = add_case_review(case_id, review)
        except KeyError:
            return jsonify({"error": "case not found"}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({"case": saved})

    @app.get("/api/admin/cases")
    def api_admin_cases():
        if session.get("role") != "admin":
            return jsonify({"error": "admin login required"}), 401
        datasets = list_datasets()
        dataset = request.args.get("dataset") or (DEFAULT_DATASET if DEFAULT_DATASET in datasets else datasets[0])
        if dataset not in datasets:
            return jsonify({"error": "unknown dataset"}), 400
        cases = read_dataset(dataset)
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"dataset": dataset, "datasets": datasets, "cases": cases})

    return app


def render_admin_login(error: str = "") -> str:
    error_html = f'<div class="errors">{error}</div>' if error else ""
    return page("ClawTrap 管理员登录", f"""
<main><section class="login">
  <div class="brand-lockup" style="margin-bottom:18px">
    <div class="brand-mark">C</div>
    <div><h1>ClawTrap</h1><div class="brand-subtitle">Administrator review console</div></div>
  </div>
  <form method="post" action="/admin/login">
    <label>管理员账号</label><input name="username" required autocomplete="username" autofocus>
    <label>密码</label><input name="password" type="password" required autocomplete="current-password">
    {error_html}
    <div style="height:14px"></div><button type="submit">登录</button>
  </form>
</section></main>""")


def app_header(user: str, subtitle: str) -> str:
    return f"""
<header>
  <div class="brand-lockup"><div class="brand-mark">C</div><div><h1>ClawTrap</h1><div class="brand-subtitle">{subtitle}</div></div></div>
  <div class="top-nav"><a class="button secondary" href="/">菜单</a><span class="meta">{user}</span><a class="button secondary" href="/logout">退出</a></div>
</header>"""


def menu_page(user: str) -> str:
    return page("ClawTrap 工作台", f"""
{app_header(user, "Benchmark annotation workspace")}
<main>
<section class="hero">
  <div class="eyebrow">Workspace</div>
  <h2 class="hero-title">ClawTrap benchmark annotation console.</h2>
  <p class="hero-copy">当前账户：<strong>{user}</strong>。请选择下一步工作：设计新场景、审核并评分已有场景，或查看全部场景及评分。</p>
</section>
<section class="choice-grid">
  <a class="choice-card" href="/design"><div class="choice-number">1</div><strong>设计新场景</strong><span>填写 task、target、攻击方式、判定状态和 metadata，保存为草稿或提交。</span></a>
  <a class="choice-card" href="/review"><div class="choice-number">2</div><strong>审核 + 打分老场景</strong><span>从已有 case 中选择，按可实现性、准确性、描述清晰度和综合质量评分。</span></a>
  <a class="choice-card" href="/scenes"><div class="choice-number">3</div><strong>查看已有场景及评分</strong><span>浏览所有场景、筛选类别，并查看每条 case 的评分均值和历史审核记录。</span></a>
</section>
</main>""")


def design_page(user: str) -> str:
    return page("ClawTrap Benchmark 标注", f"""
{app_header(user, "MITM benchmark annotation")}
<main>
<section class="hero compact">
  <div class="eyebrow">Annotation Workspace</div>
  <h2 class="hero-title">Design concrete attack cases for agentic MITM evaluation.</h2>
  <p class="hero-copy">选择固定攻击类别与任务类型，描述可执行场景、判定状态和所需 metadata。草稿可以反复编辑，提交时会检查字段完整性。</p>
</section>
<div class="grid">
  <section class="panel">
    <div class="section-heading"><div><p class="section-kicker">Library</p><h2>我的场景</h2></div></div>
    <div id="caseList"></div>
  </section>
  <section class="panel">
    <div class="section-heading"><div><p class="section-kicker">Configuration</p><h2>设计场景</h2></div></div>
    <form id="caseForm">
      <input type="hidden" name="id">
      <label>任务类型</label><div class="select-shell"><select name="task_type" required>{options(TASK_TYPES)}</select></div>
      <label>攻击类型</label><div class="select-shell"><select name="attack_type" required>{options(ATTACK_TYPES)}</select></div>
      <label>MITM 植入形式</label><div class="checks">{checkboxes(INTERACTIVE_FORMS)}</div>
      <label>任务描述 task</label><textarea name="task" required></textarea>
      <label>任务目标 target</label><textarea name="target" required></textarea>
      <label>攻击方法 attack_method</label><textarea name="attack_method" required></textarea>
      <label>成功防御状态 success_states（每行一条）</label><textarea name="success_states" required></textarea>
      <label>失败状态 failure_states（每行一条）</label><textarea name="failure_states" required></textarea>
      <label>攻击逻辑 logic</label><textarea name="logic" required></textarea>
      <label>Metadata（每行一条）</label><textarea name="metadata" required></textarea>
      <div class="errors" id="errors"></div>
      <div class="row" style="margin-top:14px">
        <button type="button" onclick="saveCase('draft')">保存草稿</button>
        <button type="button" class="secondary" onclick="saveCase('submitted')">提交</button>
        <button type="button" class="secondary" onclick="clearForm()">新建</button>
      </div>
    </form>
  </section>
</div></main>
<script>{annotator_js()}</script>""")


def review_page(user: str) -> str:
    return page("ClawTrap 场景审核", f"""
{app_header(user, "Case review and scoring")}
<main class="admin-main">
  <section class="hero compact">
    <div class="eyebrow">Review</div>
    <h2 class="hero-title">Score existing attack cases.</h2>
    <p class="hero-copy">选择左侧 case，在右侧查看场景并从可实现性、准确性、描述清晰度和综合质量四个维度打分。</p>
  </section>
  <section class="review-layout">
    <div class="review-list" id="reviewList"></div>
    <aside class="detail-panel" id="detailPanel"></aside>
  </section>
</main>
<script>{review_js()}</script>""")


def scenes_page(user: str) -> str:
    return page("ClawTrap 场景与评分", f"""
{app_header(user, "Scene library and scores")}
<main class="admin-main">
  <section class="hero compact">
    <div class="eyebrow">Scene Library</div>
    <h2 class="hero-title">Browse cases and review scores.</h2>
    <p class="hero-copy">查看已有场景、评分均值和审核记录。评分会保存在 case 的 <code>reviews</code> 字段里。</p>
  </section>
  <section class="panel toolbar">
    <div><label>状态</label><select id="statusFilter"><option value="">全部</option><option value="draft">draft</option><option value="submitted">submitted</option></select></div>
    <div><label>攻击类型</label><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div>
    <div><label>任务类型</label><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div>
    <div><label>植入形式</label><select id="formFilter"><option value="">全部</option>{options(INTERACTIVE_FORMS)}</select></div>
    <div><label>搜索</label><input id="search" placeholder="task / target / id / owner"></div>
    <div class="row toolbar-actions"><button type="button" onclick="loadCases()">刷新</button></div>
  </section>
  <section class="stats" id="stats"></section>
  <section class="review-layout"><div class="review-list" id="reviewList"></div><aside class="detail-panel" id="detailPanel"></aside></section>
</main>
<script>{scenes_js()}</script>""")


def admin_page(admin: str) -> str:
    return page("ClawTrap 数据审阅", f"""
<header>
  <div class="brand-lockup"><div class="brand-mark">C</div><div><h1>ClawTrap</h1><div class="brand-subtitle">Benchmark data review</div></div></div>
  <div class="top-nav"><span class="meta">admin: {admin}</span><a class="button secondary" href="/admin/logout">退出</a></div>
</header>
<main class="admin-main">
  <section class="hero compact">
    <div class="eyebrow">Review Console</div>
    <h2 class="hero-title">Inspect generated and submitted MITM benchmark cases.</h2>
    <p class="hero-copy">筛选数据集、攻击类型和任务类型，在左侧快速浏览 case，在右侧查看完整判定逻辑与 metadata。</p>
  </section>
  <section class="panel toolbar">
    <div><label>数据集</label><select id="dataset"></select></div>
    <div><label>状态</label><select id="statusFilter"><option value="">全部</option><option value="draft">draft</option><option value="submitted">submitted</option></select></div>
    <div><label>攻击类型</label><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div>
    <div><label>任务类型</label><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div>
    <div><label>植入形式</label><select id="formFilter"><option value="">全部</option>{options(INTERACTIVE_FORMS)}</select></div>
    <div><label>搜索</label><input id="search" placeholder="task / target / attack_method / id / owner"></div>
    <div class="row toolbar-actions"><button type="button" onclick="loadCases()">刷新</button><button type="button" class="secondary" onclick="downloadFiltered()">导出当前筛选</button></div>
  </section>
  <section class="stats" id="stats"></section>
  <section class="review-layout"><div class="review-list" id="reviewList"></div><aside class="detail-panel" id="detailPanel"></aside></section>
</main>
<script>{admin_js()}</script>""")


def annotator_js() -> str:
    return r"""
const listEl = document.getElementById('caseList');
const form = document.getElementById('caseForm');
const errors = document.getElementById('errors');
function lines(value) { return value.split('\n').map(v => v.trim()).filter(Boolean); }
function fillLines(items) { return Array.isArray(items) ? items.join('\n') : ''; }
function formData(status) {
  const data = Object.fromEntries(new FormData(form).entries());
  data.status = status;
  data.success_states = lines(form.success_states.value);
  data.failure_states = lines(form.failure_states.value);
  data.metadata = lines(form.metadata.value);
  data.interactive_form = [...form.querySelectorAll('input[name="interactive_form"]:checked')].map(i => i.value);
  return data;
}
function clearForm() { form.reset(); form.id.value = ''; errors.textContent = ''; }
function editCase(item) {
  clearForm();
  for (const key of ['id','task','target','task_type','attack_method','logic','attack_type']) form[key].value = item[key] || '';
  form.success_states.value = fillLines(item.success_states);
  form.failure_states.value = fillLines(item.failure_states);
  form.metadata.value = fillLines(item.metadata);
  for (const box of form.querySelectorAll('input[name="interactive_form"]')) box.checked = (item.interactive_form || []).includes(box.value);
  window.scrollTo({top: 0, behavior: 'smooth'});
}
async function loadCases() {
  const res = await fetch('/api/cases'); const data = await res.json(); listEl.innerHTML = '';
  for (const item of data.cases) {
    const node = document.createElement('article'); node.className = 'case';
    node.innerHTML = `<h3>${escapeHtml(item.task || '(未命名任务)')}</h3><div class="meta">${escapeHtml(item.status)} · ${escapeHtml(item.task_type)} · ${escapeHtml(item.attack_type)}<br>${escapeHtml((item.interactive_form || []).join(' / '))}</div><div style="height:10px"></div><button type="button" class="secondary">编辑</button>`;
    node.querySelector('button').onclick = () => editCase(item); listEl.appendChild(node);
  }
}
async function saveCase(status) {
  errors.textContent = '';
  const res = await fetch('/api/cases', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(formData(status))});
  const data = await res.json();
  if (!res.ok) { errors.textContent = (data.errors || [data.error || '保存失败']).join('\n'); return; }
  editCase(data.case); await loadCases();
}
function escapeHtml(value) { return String(value || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
loadCases();
"""


def shared_case_js() -> str:
    return r"""
let allCases = []; let filteredCases = []; let selectedId = null;
function summaryText(item) {
  const s = item.review_summary || {};
  if (!s.count) return '暂无评分';
  return `评分 ${s.overall ?? '-'} · 可实现 ${s.feasibility ?? '-'} · 准确 ${s.accuracy ?? '-'} · 清晰 ${s.clarity ?? '-'} · ${s.count} 条`;
}
function caseTags(item) {
  return `<span class="pill strong">${escapeHtml(item.status || 'draft')}</span><span class="pill">${escapeHtml(item.task_type)}</span><span class="pill">${escapeHtml(item.attack_type)}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span>`;
}
function renderCaseList(onClickName='selectCase') {
  if (!filteredCases.some(item => item.id === selectedId)) selectedId = filteredCases[0]?.id || null;
  const list = document.getElementById('reviewList');
  list.innerHTML = filteredCases.map(item => `<button class="review-item ${item.id === selectedId ? 'active' : ''}" type="button" onclick="${onClickName}('${escapeAttr(item.id)}')"><span class="review-item-title">${escapeHtml(item.task || '(未命名任务)')}</span><span class="review-item-attack">${escapeHtml(item.attack_method || '')}</span><span class="meta">${escapeHtml(summaryText(item))}</span><span class="review-tags">${caseTags(item)}</span></button>`).join('') || '<div class="detail-empty">没有匹配的数据</div>';
}
function detailFields(item, includeReviews=true) {
  const reviews = Array.isArray(item.reviews) ? item.reviews : [];
  const reviewHtml = includeReviews ? `<dt>Reviews</dt><dd>${reviews.length ? `<ul>${reviews.map(r => `<li>${escapeHtml(r.reviewer || 'unknown')}：综合 ${escapeHtml(r.overall)}，可实现 ${escapeHtml(r.feasibility)}，准确 ${escapeHtml(r.accuracy)}，清晰 ${escapeHtml(r.clarity)}${r.comment ? ` · ${escapeHtml(r.comment)}` : ''}</li>`).join('')}</ul>` : '暂无评分'}</dd>` : '';
  return `<dl><dt>Attack Method</dt><dd>${escapeHtml(item.attack_method)}</dd><dt>Target</dt><dd>${escapeHtml(item.target)}</dd><dt>Success States</dt><dd>${listText(item.success_states)}</dd><dt>Failure States</dt><dd>${listText(item.failure_states)}</dd><dt>Metadata</dt><dd>${listText(item.metadata)}</dd><dt>Logic</dt><dd>${escapeHtml(item.logic)}</dd>${reviewHtml}</dl>`;
}
function baseDetail(item) {
  return `<h2>${escapeHtml(item.task || '(未命名任务)')}</h2><div class="meta">${escapeHtml(item.id)} · ${escapeHtml(item.owner)} · ${escapeHtml(item.created_at || '')}</div><div class="review-tags">${caseTags(item)}<span class="pill">${escapeHtml(summaryText(item))}</span></div>`;
}
function listText(items) { return Array.isArray(items) ? `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : escapeHtml(items || ''); }
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function escapeAttr(value) { return String(value ?? '').replace(/[\'\\]/g, ch => ch === '\\' ? '\\\\' : "\\'"); }
"""


def review_js() -> str:
    return shared_case_js() + r"""
async function loadReviewCases() {
  const res = await fetch('/api/all-cases');
  const data = await res.json();
  allCases = data.cases || [];
  filteredCases = allCases;
  renderCaseList();
  renderDetail();
}
function selectCase(id) { selectedId = id; renderCaseList(); renderDetail(); }
function renderDetail() {
  const panel = document.getElementById('detailPanel');
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) { panel.innerHTML = '<div class="detail-empty">选择左侧条目进行审核</div>'; return; }
  panel.innerHTML = `${baseDetail(item)}${detailFields(item, false)}
    <form id="reviewForm" style="margin-top:18px">
      <div class="section-heading"><div><p class="section-kicker">Scoring</p><h2>审核评分</h2></div></div>
      <div class="score-grid">
        <label>可实现性<input name="feasibility" type="number" min="1" max="5" value="4" required></label>
        <label>准确性<input name="accuracy" type="number" min="1" max="5" value="4" required></label>
        <label>描述清晰度<input name="clarity" type="number" min="1" max="5" value="4" required></label>
        <label>综合评分<input name="overall" type="number" min="1" max="5" value="4" required></label>
      </div>
      <label>审核备注</label><textarea name="comment" placeholder="可选：指出需要修改的字段或原因"></textarea>
      <div class="errors" id="reviewErrors"></div>
      <div class="row" style="margin-top:14px"><button type="button" onclick="submitReview()">提交评分</button></div>
    </form>`;
}
async function submitReview() {
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  const form = document.getElementById('reviewForm');
  const payload = Object.fromEntries(new FormData(form).entries());
  const res = await fetch(`/api/cases/${encodeURIComponent(item.id)}/reviews`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const data = await res.json();
  if (!res.ok) { document.getElementById('reviewErrors').textContent = (data.errors || [data.error || '提交失败']).join('\n'); return; }
  const index = allCases.findIndex(c => c.id === data.case.id);
  if (index >= 0) allCases[index] = data.case;
  filteredCases = allCases;
  selectedId = data.case.id;
  renderCaseList();
  renderDetail();
}
loadReviewCases();
"""


def scenes_js() -> str:
    return shared_case_js() + r"""
const controls = ['statusFilter','attackFilter','taskFilter','formFilter','search'].map(id => document.getElementById(id));
async function loadCases() {
  const res = await fetch('/api/all-cases');
  const data = await res.json();
  allCases = data.cases || [];
  render();
}
function render() {
  const status = document.getElementById('statusFilter').value, attack = document.getElementById('attackFilter').value, task = document.getElementById('taskFilter').value, form = document.getElementById('formFilter').value, q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = allCases.filter(item => (!status || item.status === status) && (!attack || item.attack_type === attack) && (!task || item.task_type === task) && (!form || (item.interactive_form || []).includes(form)) && (!q || JSON.stringify(item).toLowerCase().includes(q)));
  renderStats(); renderCaseList(); renderDetail();
}
function renderStats() {
  const reviewed = filteredCases.filter(c => c.review_summary?.count).length;
  document.getElementById('stats').innerHTML = [stat('当前筛选', filteredCases.length), stat('已有评分', reviewed), stat('未评分', filteredCases.length - reviewed), stat('标注员数', new Set(filteredCases.map(c => c.owner || '')).size)].join('');
}
function stat(label, value) { return `<article class="stat"><strong>${value}</strong><span>${escapeHtml(label)}</span></article>`; }
function selectCase(id) { selectedId = id; renderCaseList(); renderDetail(); }
function renderDetail() {
  const panel = document.getElementById('detailPanel');
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) { panel.innerHTML = '<div class="detail-empty">选择左侧条目查看评分</div>'; return; }
  panel.innerHTML = `${baseDetail(item)}<div class="score-summary">${['overall','feasibility','accuracy','clarity'].map(k => `<span class="pill strong">${k}: ${escapeHtml(item.review_summary?.[k] ?? '-')}</span>`).join('')}</div>${detailFields(item, true)}`;
}
controls.forEach(el => el.addEventListener('input', render));
loadCases();
"""


def admin_js() -> str:
    return r"""
let allCases = []; let filteredCases = []; let selectedId = null;
const dataset = document.getElementById('dataset');
const controls = ['statusFilter','attackFilter','taskFilter','formFilter','search'].map(id => document.getElementById(id));
async function init() {
  const res = await fetch('/api/admin/cases'); const data = await res.json();
  dataset.innerHTML = data.datasets.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
  dataset.value = data.dataset; allCases = data.cases || [];
  controls.concat(dataset).forEach(el => el.addEventListener('input', () => dataset === el ? loadCases() : render()));
  render();
}
async function loadCases() {
  const res = await fetch(`/api/admin/cases?dataset=${encodeURIComponent(dataset.value)}`);
  const data = await res.json(); allCases = data.cases || []; render();
}
function render() {
  const status = document.getElementById('statusFilter').value, attack = document.getElementById('attackFilter').value, task = document.getElementById('taskFilter').value, form = document.getElementById('formFilter').value, q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = allCases.filter(item => (!status || item.status === status) && (!attack || item.attack_type === attack) && (!task || item.task_type === task) && (!form || (item.interactive_form || []).includes(form)) && (!q || JSON.stringify(item).toLowerCase().includes(q)));
  renderStats(); renderList(); renderDetail();
}
function renderStats() {
  document.getElementById('stats').innerHTML = [
    stat('当前筛选', filteredCases.length), stat('全部数据', allCases.length),
    stat('submitted', filteredCases.filter(c => c.status === 'submitted').length),
    stat('draft', filteredCases.filter(c => c.status === 'draft').length),
    stat('标注员数', new Set(filteredCases.map(c => c.owner || '')).size)
  ].join('');
}
function stat(label, value) { return `<article class="stat"><strong>${value}</strong><span>${escapeHtml(label)}</span></article>`; }
function renderList() {
  if (!filteredCases.some(item => item.id === selectedId)) selectedId = filteredCases[0]?.id || null;
  const list = document.getElementById('reviewList');
  list.innerHTML = filteredCases.map(item => `<button class="review-item ${item.id === selectedId ? 'active' : ''}" type="button" onclick="selectCase('${escapeAttr(item.id)}')"><span class="review-item-title">${escapeHtml(item.task || '(未命名任务)')}</span><span class="review-item-attack">${escapeHtml(item.attack_method || '')}</span><span class="review-tags"><span class="pill strong">${escapeHtml(item.status || 'draft')}</span><span class="pill">${escapeHtml(item.task_type)}</span><span class="pill">${escapeHtml(item.attack_type)}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span></span></button>`).join('') || '<div class="detail-empty">没有匹配的数据</div>';
}
function selectCase(id) { selectedId = id; renderList(); renderDetail(); }
function renderDetail() {
  const panel = document.getElementById('detailPanel'); const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) { panel.innerHTML = '<div class="detail-empty">选择左侧条目查看详情</div>'; return; }
  panel.innerHTML = `<h2>${escapeHtml(item.task || '(未命名任务)')}</h2><div class="meta">${escapeHtml(item.id)} · ${escapeHtml(item.owner)} · ${escapeHtml(item.created_at || '')}</div><div class="review-tags"><span class="pill strong">${escapeHtml(item.status || 'draft')}</span><span class="pill">${escapeHtml(item.task_type)}</span><span class="pill">${escapeHtml(item.attack_type)}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span></div><dl><dt>Attack Method</dt><dd>${escapeHtml(item.attack_method)}</dd><dt>Success States</dt><dd>${listText(item.success_states)}</dd><dt>Failure States</dt><dd>${listText(item.failure_states)}</dd><dt>Metadata</dt><dd>${listText(item.metadata)}</dd><dt>Target</dt><dd>${escapeHtml(item.target)}</dd><dt>Logic</dt><dd>${escapeHtml(item.logic)}</dd></dl>`;
}
function listText(items) { return Array.isArray(items) ? `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : escapeHtml(items || ''); }
function downloadFiltered() { const blob = new Blob([JSON.stringify(filteredCases, null, 2)], {type:'application/json;charset=utf-8'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `clawtrap-filtered-${dataset.value}.json`; a.click(); URL.revokeObjectURL(url); }
function escapeHtml(value) { return String(value || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function escapeAttr(value) { return String(value || '').replace(/[\'\\]/g, ch => ch === '\\' ? '\\\\' : "\\'"); }
init();
"""


app = create_app()


if __name__ == "__main__":
    load_dotenv()
    app.run(host=os.environ.get("APP_HOST", "127.0.0.1"), port=int(os.environ.get("APP_PORT", "8000")))
