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
from .storage import DEFAULT_DATASET, add_case_review, list_datasets, read_dataset, set_benchmark_selected, upsert_case


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
    :root {{
      --paper:#f8f4ec; --paper-deep:#eee6d8; --panel:#fffefa; --panel-soft:#f6efe3;
      --text:#111d2e; --ink:#263346; --muted:#687488; --line:rgba(38,51,70,.12);
      --line-strong:rgba(38,51,70,.24); --navy:#172234; --navy-soft:#24344d;
      --accent:#94683d; --accent-strong:#6f4c2b; --accent-soft:#f2e7d7;
      --green:#0f766e; --danger:#b42318; --shadow:0 10px 28px rgba(23,34,52,.06);
    }}
    * {{ box-sizing:border-box; }}
    html {{ background:var(--paper); color-scheme:light; scroll-behavior:smooth; }}
    body {{
      margin:0; min-height:100vh; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
      background:
        linear-gradient(180deg, rgba(255,253,250,.9) 0%, rgba(248,244,236,.96) 40%, rgba(238,230,216,.92) 100%),
        repeating-linear-gradient(90deg, rgba(23,34,52,.028) 0 1px, transparent 1px 96px);
      color:var(--ink);
      line-height:1.45;
    }}
    ::selection {{ background:rgba(148,104,61,.18); color:var(--text); }}
    *::-webkit-scrollbar {{ width:10px; height:10px; }}
    *::-webkit-scrollbar-track {{ background:rgba(246,239,227,.64); border-radius:999px; }}
    *::-webkit-scrollbar-thumb {{ background:rgba(148,104,61,.28); border:2px solid rgba(246,239,227,.72); border-radius:999px; }}
    *::-webkit-scrollbar-thumb:hover {{ background:rgba(148,104,61,.42); }}
    body::before {{
      content:''; position:fixed; inset:0; z-index:-1; pointer-events:none;
      background:linear-gradient(180deg, rgba(255,255,255,.58), transparent 34%), linear-gradient(90deg, transparent 0, transparent calc(50% - 1px), rgba(23,34,52,.045) calc(50% - 1px), rgba(23,34,52,.045) 50%, transparent 50%);
      background-size:100% 100%, 96px 100%;
      mask-image:linear-gradient(180deg,rgba(0,0,0,.34),transparent 70%);
    }}
    header {{
      width:min(1480px,calc(100vw - 40px)); margin:18px auto 0; display:flex; justify-content:space-between;
      align-items:center; gap:18px; padding:12px 14px; border:1px solid var(--line); border-radius:8px;
      background:rgba(255,253,250,.9); backdrop-filter:blur(14px); position:sticky; top:12px; z-index:2;
      box-shadow:0 12px 30px rgba(23,34,52,.055);
    }}
    main {{ max-width:1260px; margin:0 auto; padding:24px 24px 54px; }}
    h1,h2,h3 {{ color:var(--text); }}
    h1 {{ font-family:Georgia,"Times New Roman","Songti SC",serif; font-size:30px; margin:0; font-weight:700; font-style:italic; letter-spacing:-.02em; line-height:.96; }}
    h2 {{ font-family:Georgia,"Times New Roman","Songti SC",serif; font-size:27px; margin:0 0 14px; font-weight:700; letter-spacing:-.02em; }}
    .brand-lockup {{ display:flex; align-items:center; gap:12px; min-width:0; }}
    .brand-mark {{ width:38px; height:38px; border-radius:8px; display:grid; place-items:center; background:linear-gradient(145deg,var(--navy),#2d405e); color:#fff8ee; font-family:Georgia,"Times New Roman",serif; font-size:22px; font-weight:700; font-style:italic; box-shadow:inset 0 0 0 1px rgba(255,255,255,.12); }}
    .brand-subtitle {{ color:var(--muted); font-size:11px; line-height:1.15; margin-top:4px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }}
    .top-nav {{ display:flex; align-items:center; gap:8px; }}
    .app-nav {{ display:flex; align-items:center; gap:3px; padding:3px; border:1px solid var(--line); border-radius:8px; background:rgba(246,240,230,.78); }}
    .app-nav a {{ display:inline-flex; align-items:center; min-height:34px; padding:7px 12px; border-radius:6px; color:var(--muted); text-decoration:none; font-size:13px; font-weight:800; }}
    .app-nav a:hover,.app-nav a.active {{ background:var(--panel); color:var(--text); box-shadow:0 8px 18px rgba(23,34,52,.06); }}
    .user-chip {{ display:inline-flex; align-items:center; min-height:36px; padding:7px 12px; border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.76); color:var(--text); font-size:12px; font-weight:800; }}
    .hero {{
      position:relative; margin:10px 0 20px; padding:18px 0 20px; border:0; border-bottom:1px solid var(--line);
      background:transparent; box-shadow:none; overflow:hidden;
    }}
    .hero::before {{ content:''; position:absolute; left:0; bottom:0; width:96px; height:2px; background:var(--accent); pointer-events:none; }}
    .hero > * {{ position:relative; }}
    .hero.compact {{ padding:14px 0 18px; }}
    .eyebrow {{ display:inline-flex; padding:0; color:var(--accent-strong); font-size:10px; font-weight:900; letter-spacing:.14em; text-transform:uppercase; }}
    .hero-title {{ max-width:930px; margin:9px 0 8px; font-family:Georgia,"Times New Roman","Songti SC",serif; font-size:clamp(2.2rem,4.1vw,3.8rem); line-height:1.02; letter-spacing:-.035em; color:var(--text); font-weight:700; }}
    .hero.compact .hero-title {{ font-size:clamp(1.85rem,3vw,2.7rem); max-width:880px; }}
    .hero-copy {{ max-width:840px; color:var(--muted); font-size:15px; line-height:1.75; margin:0; }}
    code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.92em; color:var(--accent-strong); background:rgba(148,104,61,.1); border:1px solid rgba(148,104,61,.16); border-radius:5px; padding:1px 5px; }}
    .section-heading {{ display:flex; justify-content:space-between; align-items:flex-end; gap:12px; margin-bottom:14px; }}
    .section-kicker {{ margin:0 0 5px; color:var(--accent-strong); font-size:10px; font-weight:900; letter-spacing:.13em; text-transform:uppercase; }}
    .button, button {{
      border:1px solid var(--navy); background:var(--navy); color:#fffefa; padding:9px 14px;
      border-radius:7px; cursor:pointer; text-decoration:none; font-size:13px; font-weight:800;
      box-shadow:0 8px 18px rgba(23,34,52,.1); letter-spacing:.01em;
    }}
    button:hover,.button:hover {{ background:var(--navy-soft); }}
    button:active,.button:active {{ transform:translateY(1px); }}
    button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,.select-card-trigger:focus-visible,.choice-pill input:focus-visible + span {{
      outline:3px solid rgba(148,104,61,.22); outline-offset:2px;
    }}
    .secondary {{ background:rgba(255,253,250,.62); color:var(--navy); border-color:var(--line-strong); box-shadow:none; }}
    .secondary:hover {{ background:var(--panel-soft); color:var(--navy); }}
    .panel,.case,.login,.detail-panel,.stat,.review-item {{
      background:rgba(255,253,250,.94); border:1px solid var(--line); border-radius:8px; box-shadow:var(--shadow);
    }}
    .panel {{ padding:20px; background:linear-gradient(180deg,rgba(255,254,250,.96),rgba(250,246,239,.9)); overflow:visible; }}
    .grid {{ display:grid; grid-template-columns:340px minmax(0,1fr); gap:18px; align-items:start; }}
    .design-grid {{ display:grid; grid-template-columns:360px minmax(0,1fr); gap:18px; align-items:start; }}
    .design-grid.design-only {{ grid-template-columns:minmax(0,1fr); max-width:980px; }}
    .design-editor {{ width:100%; }}
    .sticky-panel {{ position:sticky; top:92px; }}
    .case {{ margin-bottom:10px; padding:14px; box-shadow:none; background:rgba(255,254,250,.84); }}
    .case h3 {{ margin:0 0 8px; font-size:13px; line-height:1.5; }}
    .meta {{ color:var(--muted); font-size:12px; line-height:1.55; font-weight:600; }}
    .empty-note {{ color:var(--muted); padding:20px; text-align:center; background:rgba(246,239,227,.64); border:1px dashed var(--line-strong); border-radius:8px; font-size:13px; font-weight:700; line-height:1.65; }}
    label {{ display:block; font-weight:800; margin:12px 0 6px; font-size:12px; color:#344054; }}
    input,select,textarea {{
      width:100%; border:1px solid var(--line); border-radius:7px; padding:10px 11px; font:inherit;
      background:rgba(255,253,250,.96); outline:none; transition:border-color .12s, box-shadow .12s, background .12s;
    }}
    input:focus,select:focus,textarea:focus {{ border-color:var(--accent); box-shadow:0 0 0 3px rgba(148,104,61,.13); background:#fff; }}
    textarea {{ min-height:88px; resize:vertical; line-height:1.6; }}
    .checks {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr)); gap:9px; }}
    .form-section {{ margin-top:16px; padding:17px; border:1px solid var(--line); border-radius:8px; background:rgba(255,254,250,.58); overflow:visible; }}
    .form-section:first-of-type {{ margin-top:0; }}
    .form-section-title {{ display:flex; align-items:center; gap:9px; margin:0 0 12px; color:var(--text); font-family:Georgia,"Times New Roman","Songti SC",serif; font-size:24px; line-height:1; font-weight:700; }}
    .form-section-title::before {{ content:''; width:22px; height:1px; background:var(--accent); }}
    .field-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .field-grid .full {{ grid-column:1 / -1; }}
    .choice-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }}
    .choice-card {{ display:grid; grid-template-rows:auto auto 1fr; min-height:168px; padding:18px; color:var(--ink); text-decoration:none; background:linear-gradient(180deg,rgba(255,254,250,.96),rgba(247,240,229,.78)); border:1px solid var(--line); border-top:3px solid rgba(148,104,61,.45); border-radius:8px; box-shadow:var(--shadow); transition:transform .14s, border-color .14s, box-shadow .14s; }}
    .choice-card:hover {{ transform:translateY(-3px); border-color:rgba(148,104,61,.34); border-top-color:var(--accent); box-shadow:0 20px 44px rgba(23,34,52,.1); }}
    .choice-card strong {{ display:block; margin:13px 0 8px; color:var(--text); font-family:Georgia,"Times New Roman","Songti SC",serif; font-size:29px; line-height:1.02; letter-spacing:-.02em; }}
    .choice-card span {{ color:var(--muted); font-size:13px; line-height:1.62; font-weight:600; }}
    .choice-number {{ width:34px; height:28px; display:grid; place-items:center; color:#fffefa; background:var(--navy); border-radius:6px; font-size:12px; font-weight:900; }}
    .overview-grid {{ display:grid; grid-template-columns:1.05fr .95fr; gap:14px; margin-bottom:14px; }}
    .overview-card {{ min-height:150px; padding:18px; background:linear-gradient(180deg,rgba(255,254,250,.96),rgba(247,240,229,.78)); border:1px solid var(--line); border-radius:8px; box-shadow:var(--shadow); overflow:visible; }}
    .overview-card h2 {{ margin-bottom:8px; }}
    .overview-card p {{ margin:0; color:var(--muted); font-size:14px; line-height:1.7; font-weight:600; }}
    .overview-stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:16px; }}
    .mini-stat {{ padding:12px; border:1px solid var(--line); border-radius:8px; background:rgba(255,254,250,.68); }}
    .mini-stat strong {{ display:block; color:var(--text); font-size:24px; line-height:1; }}
    .mini-stat span {{ display:block; color:var(--muted); font-size:11px; font-weight:800; margin-top:7px; }}
    .account-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }}
    .choice-pill {{ position:relative; display:flex; align-items:center; justify-content:center; margin:0; padding:0; cursor:pointer; }}
    .choice-pill input {{ position:absolute; opacity:0; pointer-events:none; }}
    .choice-pill span {{ width:100%; min-height:42px; display:flex; align-items:center; justify-content:center; padding:8px 10px; border:1px solid rgba(148,104,61,.18); border-radius:7px; background:linear-gradient(180deg,#fffaf1,#f4eadb); color:#695f54; font-size:13px; font-weight:800; transition:background .12s,border-color .12s,color .12s,box-shadow .12s,transform .12s; }}
    .choice-pill:hover span {{ border-color:rgba(148,104,61,.34); transform:translateY(-1px); }}
    .choice-pill input:checked + span {{ border-color:rgba(148,104,61,.55); background:linear-gradient(180deg,#f2e5d2,#ead9bf); color:var(--accent-strong); box-shadow:0 0 0 3px rgba(148,104,61,.12); }}
    .select-shell {{ position:relative; }}
    .select-shell.open {{ z-index:80; }}
    .select-shell select {{ appearance:none; padding-right:34px; background:linear-gradient(180deg,#fffaf1,#f4eadb); color:var(--text); font-weight:700; }}
    .select-shell::after {{ content:'⌄'; position:absolute; right:12px; bottom:9px; color:var(--accent-strong); pointer-events:none; font-weight:900; }}
    .select-shell.enhanced::after {{ display:none; }}
    .select-shell.enhanced select {{ position:absolute; width:1px; height:1px; opacity:0; pointer-events:none; overflow:hidden; }}
    .select-card-trigger {{
      width:100%; min-height:42px; display:flex; align-items:center; justify-content:space-between; gap:10px;
      padding:9px 11px; border:1px solid rgba(148,104,61,.18); border-radius:7px;
      background:linear-gradient(180deg,#fffaf1,#f4eadb); color:var(--text); box-shadow:none;
      font-size:13px; font-weight:800; text-align:left;
    }}
    .select-card-trigger:hover,.select-shell.open .select-card-trigger {{ background:linear-gradient(180deg,#fffdf8,#f1e4d2); border-color:rgba(148,104,61,.4); color:var(--text); }}
    .select-card-trigger::after {{ content:'⌄'; color:var(--accent-strong); font-weight:900; transition:transform .12s; }}
    .select-shell.open .select-card-trigger::after {{ transform:rotate(180deg); }}
    .select-card-menu {{
      position:absolute; left:0; right:0; top:calc(100% + 6px); z-index:30; display:none; gap:5px;
      max-height:min(280px,52vh); overflow:auto; padding:7px; border:1px solid rgba(38,51,70,.16); border-radius:8px;
      background:linear-gradient(180deg,rgba(255,254,250,.98),rgba(247,240,229,.96)); box-shadow:0 18px 42px rgba(23,34,52,.14);
    }}
    .select-shell.drop-up .select-card-menu {{ top:auto; bottom:calc(100% + 6px); }}
    .select-shell.open .select-card-menu {{ display:grid; }}
    .select-card-option {{
      width:100%; min-height:36px; padding:8px 10px; border:1px solid transparent; border-radius:7px;
      background:transparent; color:var(--ink); box-shadow:none; text-align:left; font-size:13px; font-weight:750;
    }}
    .select-card-option:hover {{ background:rgba(148,104,61,.08); border-color:rgba(148,104,61,.16); color:var(--text); }}
    .select-card-option.active {{ background:var(--accent-soft); border-color:rgba(148,104,61,.34); color:var(--accent-strong); }}
    .score-grid {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:10px; }}
    .score-grid label {{ margin-top:0; }}
    .score-grid input {{ text-align:center; font-weight:900; font-size:18px; background:linear-gradient(180deg,#fffaf1,#f4eadb); }}
    .score-summary {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }}
    .row {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .errors {{ color:var(--danger); font-size:13px; white-space:pre-wrap; margin-top:8px; }}
    .status-message {{ color:var(--accent-strong); font-size:13px; white-space:pre-wrap; margin-top:8px; font-weight:700; }}
    .status-message.error {{ color:var(--danger); }}
    .login-main {{ min-height:100vh; display:grid; place-items:center; padding:28px; }}
    .login {{ width:min(460px,100%); margin:0 auto; padding:30px; background:linear-gradient(135deg,rgba(255,254,250,.97),rgba(246,240,230,.88)); }}
    .login h1 {{ margin-bottom:4px; }}
    .login-note {{ margin:18px 0 20px; padding:13px 14px; color:var(--muted); background:rgba(255,254,250,.68); border:1px solid var(--line); border-radius:8px; font-size:13px; line-height:1.65; font-weight:650; }}
    .admin-main {{ max-width:1480px; }}
    .toolbar {{
      display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
      gap:11px; align-items:end; padding:15px; box-shadow:none; position:relative; z-index:5; overflow:visible;
    }}
    .toolbar label {{ margin-top:0; }}
    .toolbar-actions {{ grid-column:1/-1; }}
    .review-toolbar {{ grid-template-columns:minmax(260px,1fr) 180px auto; margin-bottom:14px; }}
    .form-actions {{ margin-top:14px; padding-top:14px; border-top:1px solid var(--line); }}
    .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(128px,1fr)); gap:10px; margin:14px 0; }}
    .stat {{ padding:14px 15px; box-shadow:none; background:rgba(255,254,250,.74); }}
    .stat strong {{ display:block; font-size:23px; line-height:1; color:var(--text); }}
    .stat span {{ display:block; color:var(--muted); font-size:12px; margin-top:7px; font-weight:700; }}
    .review-layout {{ display:grid; grid-template-columns:minmax(390px,.92fr) minmax(560px,1.35fr); gap:15px; align-items:start; }}
    .review-focus {{ max-width:1440px; }}
    .review-focus .hero {{ margin-bottom:14px; }}
    .review-focus .hero-title {{ max-width:760px; }}
    .review-focus .hero-copy {{ max-width:720px; }}
    .review-focus .review-toolbar {{ grid-template-columns:minmax(260px,1fr) 176px auto; padding:12px; margin-bottom:12px; }}
    .review-focus .review-layout {{ grid-template-columns:minmax(300px,.72fr) minmax(680px,1.68fr); gap:18px; }}
    .review-column {{ min-width:0; }}
    .result-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin:0 0 9px; padding:0 2px; }}
    .result-heading h2 {{ margin:0; font-size:22px; }}
    .result-heading span {{ color:var(--muted); font-size:12px; font-weight:800; }}
    .review-list {{ max-height:calc(100vh - 120px); overflow:auto; padding:3px; }}
    .review-list {{ display:flex; flex-direction:column; gap:9px; }}
    .origin-divider {{ display:flex; align-items:center; gap:10px; margin:7px 0 2px; color:var(--muted); font-size:11px; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }}
    .origin-divider::after {{ content:''; flex:1; height:1px; background:var(--line); }}
    .review-item {{
      position:relative; width:100%; text-align:left; color:var(--text); padding:15px 15px 15px 18px; cursor:pointer; box-shadow:none; background:rgba(255,254,250,.78);
      transition:border-color .18s ease, transform .18s ease, box-shadow .18s ease, background .18s ease;
    }}
    .review-item::before {{ content:''; position:absolute; left:-1px; top:10px; bottom:10px; width:3px; border-radius:99px; background:transparent; transition:background .18s ease, top .18s ease, bottom .18s ease; }}
    .review-item:hover {{ border-color:var(--line-strong); transform:translateY(-1px); box-shadow:0 10px 24px rgba(23,34,52,.06); background:#fffefa; }}
    .review-item.active {{ border-color:rgba(148,104,61,.5); background:linear-gradient(90deg,rgba(242,231,215,.82),rgba(255,254,250,.92)); box-shadow:0 12px 26px rgba(23,34,52,.08); transform:translateX(2px); }}
    .review-item.active::before {{ top:6px; bottom:6px; background:var(--accent); }}
    .review-item.origin-database::before {{ background:rgba(15,118,110,.28); }}
    .review-item.origin-local_json::before {{ background:rgba(148,104,61,.22); }}
    .review-item.active.origin-database::before {{ background:var(--green); }}
    .review-item.active.origin-local_json::before {{ background:var(--accent); }}
    .review-item-title {{ display:block; font-size:14px; font-weight:800; line-height:1.52; }}
    .review-item-attack {{
      display:-webkit-box; margin-top:8px; color:var(--muted); font-size:12px; line-height:1.55; font-weight:600;
      -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }}
    .review-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }}
    .review-focus .review-item {{ padding:13px 13px 13px 16px; background:rgba(255,254,250,.72); }}
    .review-focus .review-item-title {{ font-size:13px; -webkit-line-clamp:3; display:-webkit-box; -webkit-box-orient:vertical; overflow:hidden; }}
    .review-focus .review-item-attack,.review-focus .review-item .meta,.review-focus .review-item .review-tags {{ display:none; }}
    .review-focus .rank-line {{ margin-top:8px; }}
    .review-focus .rank-badge {{ min-width:38px; padding:4px 7px; }}
    .review-focus .score-badge {{ padding:4px 7px; }}
    .pill {{ flex:none; border:1px solid var(--line); border-radius:999px; padding:4px 8px; font-size:11px; color:var(--muted); background:var(--panel-soft); font-weight:800; }}
    .pill.strong {{ color:var(--accent-strong); border-color:rgba(138,98,61,.28); background:var(--accent-soft); }}
    .pill.origin-local {{ color:var(--accent-strong); border-color:rgba(148,104,61,.32); background:rgba(242,231,215,.78); }}
    .pill.origin-cloud {{ color:#0f5f59; border-color:rgba(15,118,110,.28); background:rgba(15,118,110,.08); }}
    .pill.selected-mark {{ color:#0f5f59; border-color:rgba(15,118,110,.32); background:rgba(15,118,110,.1); }}
    .rank-line {{ display:flex; align-items:center; gap:8px; margin:9px 0 0; }}
    .rank-badge {{ min-width:46px; display:inline-flex; align-items:center; justify-content:center; padding:5px 9px; border-radius:7px; background:var(--navy); color:#fffefa; font-size:12px; font-weight:900; }}
    .score-badge {{ display:inline-flex; align-items:center; justify-content:center; padding:5px 9px; border:1px solid rgba(148,104,61,.24); border-radius:7px; background:var(--accent-soft); color:var(--accent-strong); font-size:12px; font-weight:900; }}
    .benchmark-action {{ width:100%; margin-top:15px; display:flex; justify-content:center; }}
    .benchmark-action button {{ width:100%; }}
    .benchmark-action .selected {{ background:rgba(255,253,250,.72); color:#0f5f59; border-color:rgba(15,118,110,.35); box-shadow:none; }}
    .detail-panel {{ position:sticky; top:82px; padding:22px; max-height:calc(100vh - 108px); overflow:auto; background:linear-gradient(180deg,rgba(255,254,250,.98),rgba(249,244,236,.92)); border-top:3px solid rgba(148,104,61,.42); }}
    .detail-panel h2 {{ font-size:21px; line-height:1.38; margin:0 0 9px; }}
    .detail-empty {{ color:var(--muted); padding:42px 28px; text-align:center; background:var(--panel-soft); border:1px dashed var(--line-strong); border-radius:8px; font-weight:700; }}
    .review-focus .detail-panel {{ padding:0; background:transparent; border:0; box-shadow:none; max-height:calc(100vh - 86px); }}
    .focus-case {{ display:grid; gap:12px; }}
    .focus-card {{ border:1px solid var(--line); border-radius:8px; background:rgba(255,254,250,.94); box-shadow:var(--shadow); padding:18px; }}
    .focus-header {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:14px; align-items:start; border-top:3px solid rgba(148,104,61,.42); }}
    .focus-title {{ margin:0; color:var(--text); font-family:Georgia,"Times New Roman","Songti SC",serif; font-size:26px; line-height:1.25; letter-spacing:-.02em; }}
    .focus-meta {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:12px; }}
    .focus-action {{ min-width:190px; }}
    .focus-action .benchmark-action {{ margin-top:0; }}
    .focus-action .benchmark-action button {{ min-height:38px; }}
    .focus-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .focus-block {{ border:1px solid var(--line); border-radius:8px; background:rgba(246,240,230,.48); padding:14px; }}
    .focus-block.full {{ grid-column:1 / -1; }}
    .focus-label {{ display:block; margin-bottom:7px; color:var(--accent-strong); font-size:10px; font-weight:900; letter-spacing:.12em; text-transform:uppercase; }}
    .focus-text {{ margin:0; color:var(--ink); font-size:15px; line-height:1.72; font-weight:650; }}
    .focus-attack {{ border-color:rgba(180,35,24,.16); background:rgba(180,35,24,.035); }}
    .focus-attack .focus-label {{ color:#9b2c22; }}
    .judgement-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .judgement {{ min-height:150px; border:1px solid var(--line); border-radius:8px; padding:14px 14px 12px; background:rgba(255,254,250,.78); }}
    .judgement.success {{ border-color:rgba(15,118,110,.2); background:rgba(15,118,110,.055); }}
    .judgement.failure {{ border-color:rgba(180,35,24,.18); background:rgba(180,35,24,.045); }}
    .judgement h3 {{ margin:0 0 10px; font-size:13px; letter-spacing:.04em; text-transform:uppercase; }}
    .judgement.success h3 {{ color:#0f5f59; }}
    .judgement.failure h3 {{ color:#9b2c22; }}
    .judgement ul,.metadata-list {{ margin:0; padding-left:19px; color:var(--ink); font-size:14px; line-height:1.65; }}
    .metadata-strip {{ display:flex; flex-wrap:wrap; gap:7px; }}
    .metadata-token {{ display:inline-flex; max-width:100%; padding:6px 9px; border:1px solid var(--line); border-radius:7px; background:rgba(246,240,230,.62); color:var(--muted); font-size:12px; font-weight:750; line-height:1.45; }}
    .review-score-panel {{ margin-top:0; }}
    .review-score-panel .section-heading {{ margin-bottom:10px; }}
    .review-score-panel textarea {{ min-height:74px; }}
    .review-score-panel .score-grid {{ grid-template-columns:repeat(4,minmax(110px,1fr)); }}
    .review-score-panel .score-grid label {{ padding:11px; border:1px solid var(--line); border-radius:8px; background:rgba(246,240,230,.42); color:var(--muted); }}
    .review-score-panel .score-grid input {{ margin-top:6px; border-color:rgba(148,104,61,.2); }}
    dl {{ margin:18px 0 0; display:grid; gap:12px; }}
    dt {{ font-size:10px; color:var(--accent-strong); font-weight:900; text-transform:uppercase; letter-spacing:.12em; margin:0; }}
    dd {{ margin:5px 0 0; font-size:13px; line-height:1.66; background:rgba(246,240,230,.72); border:1px solid var(--line); border-radius:8px; padding:11px 12px; }}
    dd ul {{ margin:0; padding-left:18px; }}
    @media (max-width:980px) {{
      .grid,.design-grid,.design-grid.design-only,.toolbar,.review-layout,.choice-grid,.overview-grid,.overview-stats,.score-grid,.field-grid {{ grid-template-columns:1fr; max-width:none; }}
      header {{ width:calc(100vw - 28px); padding:10px; align-items:flex-start; border-radius:8px; flex-direction:column; }}
      main {{ padding:16px; }}
      .top-nav,.app-nav {{ width:100%; flex-wrap:wrap; }}
      .hero-title {{ font-size:2.1rem; }}
      .select-card-menu {{ max-height:42vh; }}
      .toolbar-actions {{ grid-column:auto; }} .detail-panel,.sticky-panel {{ position:static; max-height:none; }}
      .focus-header,.focus-grid,.judgement-grid,.review-focus .review-layout,.review-focus .review-toolbar,.review-score-panel .score-grid {{ grid-template-columns:1fr; }}
      .focus-action {{ min-width:0; }}
    }}
  </style>
</head>
<body>{body}<script>{ui_js()}</script></body>
</html>"""


def ui_js() -> str:
    return r"""
function enhanceSelects(root = document) {
  root.querySelectorAll('.select-shell select').forEach(select => {
    const shell = select.closest('.select-shell');
    if (!shell) return;
    if (shell.dataset.enhanced === '1') {
      shell.__clawtrapUpdate?.();
      return;
    }
    shell.dataset.enhanced = '1';
    shell.classList.add('enhanced');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'select-card-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');

    const menu = document.createElement('div');
    menu.className = 'select-card-menu';
    menu.setAttribute('role', 'listbox');

    shell.append(trigger, menu);

    function syncOptions() {
      menu.innerHTML = '';
      [...select.options].forEach(option => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'select-card-option';
        item.textContent = option.textContent || option.value || '未命名';
        item.dataset.value = option.value;
        item.setAttribute('role', 'option');
        item.onclick = () => {
          select.value = option.value;
          select.dispatchEvent(new Event('input', {bubbles: true}));
          select.dispatchEvent(new Event('change', {bubbles: true}));
          update();
          closeSelect(shell);
        };
        menu.appendChild(item);
      });
      update();
    }

    function update() {
      const selected = select.options[select.selectedIndex];
      trigger.textContent = selected ? selected.textContent : '请选择';
      menu.querySelectorAll('.select-card-option').forEach(item => {
        const active = item.dataset.value === select.value;
        item.classList.toggle('active', active);
        item.setAttribute('aria-selected', active ? 'true' : 'false');
      });
    }
    shell.__clawtrapUpdate = update;

    function positionMenu() {
      shell.classList.remove('drop-up');
      const rect = shell.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      if (spaceBelow < 320 && rect.top > spaceBelow) shell.classList.add('drop-up');
    }

    trigger.onclick = event => {
      event.stopPropagation();
      const wasOpen = shell.classList.contains('open');
      closeAllSelects();
      if (!wasOpen) {
        positionMenu();
        shell.classList.add('open');
        trigger.setAttribute('aria-expanded', 'true');
      }
    };
    select.addEventListener('change', update);
    select.form?.addEventListener('reset', () => requestAnimationFrame(update));
    new MutationObserver(syncOptions).observe(select, {childList: true, subtree: true, attributes: true});
    syncOptions();
  });
}
function closeSelect(shell) {
  shell.classList.remove('open');
  shell.classList.remove('drop-up');
  shell.querySelector('.select-card-trigger')?.setAttribute('aria-expanded', 'false');
}
function closeAllSelects() {
  document.querySelectorAll('.select-shell.open').forEach(closeSelect);
}
document.addEventListener('click', closeAllSelects);
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeAllSelects(); });
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => enhanceSelects());
} else {
  enhanceSelects();
}
window.refreshClawTrapSelects = enhanceSelects;
window.syncClawTrapSelects = () => {
  document.querySelectorAll('.select-shell.enhanced').forEach(shell => shell.__clawtrapUpdate?.());
};
"""


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
<main class="login-main"><section class="login">
  <div class="brand-lockup" style="margin-bottom:18px">
    <div class="brand-mark">C</div>
    <div><h1>ClawTrap</h1><div class="brand-subtitle">Benchmark annotation workspace</div></div>
  </div>
  <div class="login-note">输入标注员用户名即可进入工作台。场景创建和审核评分会记录到当前账户名下。</div>
  <form method="post" action="/login">
    <label>标注员用户名</label><input name="username" required autocomplete="username" autofocus>
    <div class="row form-actions"><button type="submit">进入工作台</button></div>
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
        cases = [case for case in read_dataset(DEFAULT_DATASET) if case.get("owner") in (username, "llm_seed")]
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
        cases = read_dataset(DEFAULT_DATASET)
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

    @app.post("/api/cases/<case_id>/benchmark-selection")
    def save_benchmark_selection(case_id: str):
        if session.get("role") not in ("annotator", "admin"):
            return jsonify({"error": "login required"}), 401
        raw = request.get_json(silent=True) or {}
        try:
            saved = set_benchmark_selected(case_id, bool(raw.get("selected")), selected_by=session.get("username") or "unknown")
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
<main class="login-main"><section class="login">
  <div class="brand-lockup" style="margin-bottom:18px">
    <div class="brand-mark">C</div>
    <div><h1>ClawTrap</h1><div class="brand-subtitle">Administrator review console</div></div>
  </div>
  <div class="login-note">管理员入口用于查看完整数据集、筛选生成结果和导出当前筛选内容。</div>
  <form method="post" action="/admin/login">
    <label>管理员账号</label><input name="username" required autocomplete="username" autofocus>
    <label>密码</label><input name="password" type="password" required autocomplete="current-password">
    {error_html}
    <div class="row form-actions"><button type="submit">进入管理台</button></div>
  </form>
</section></main>""")


def app_header(user: str, subtitle: str, active: str = "") -> str:
    def active_class(name: str) -> str:
        return "active" if active == name else ""
    return f"""
<header>
  <div class="brand-lockup"><div class="brand-mark">C</div><div><h1>ClawTrap</h1><div class="brand-subtitle">{subtitle}</div></div></div>
  <div class="top-nav">
    <nav class="app-nav">
      <a class="{active_class('menu')}" href="/">菜单</a>
      <a class="{active_class('design')}" href="/design">设计</a>
      <a class="{active_class('review')}" href="/review">审核</a>
      <a class="{active_class('scenes')}" href="/scenes">查看</a>
    </nav>
    <span class="user-chip">{user}</span>
    <a class="button secondary" href="/logout">退出</a>
  </div>
</header>"""


def menu_page(user: str) -> str:
    return page("ClawTrap 工作台", f"""
{app_header(user, "Benchmark annotation workspace", "menu")}
<main>
<section class="hero">
  <div class="eyebrow">Workspace</div>
  <h2 class="hero-title">ClawTrap 场景标注工作台</h2>
  <p class="hero-copy">当前账户：<strong>{user}</strong>。这里负责 MITM benchmark case 的创建、审核与评分查看。请选择一个入口继续。</p>
</section>
<section class="overview-grid">
  <article class="overview-card">
    <p class="section-kicker">Account</p>
    <h2>当前标注员</h2>
    <p>账户名和当前工作空间会显示在每个页面顶部。新建场景、提交评分和后续查询都会关联到当前账户。</p>
    <div class="account-row"><span class="pill strong">{user}</span><span class="pill">annotator</span><span class="pill">workspace ready</span></div>
  </article>
  <article class="overview-card">
    <p class="section-kicker">Dataset</p>
    <h2>数据概览</h2>
    <p>进入设计、审核或查看前，可以先确认当前 case 池的大致规模。</p>
    <div class="overview-stats" id="menuStats">
      <div class="mini-stat"><strong>-</strong><span>全部场景</span></div>
      <div class="mini-stat"><strong>-</strong><span>已有评分</span></div>
      <div class="mini-stat"><strong>-</strong><span>已选 benchmark</span></div>
    </div>
  </article>
</section>
<section class="choice-grid">
  <a class="choice-card" href="/design"><div class="choice-number">01</div><strong>设计新场景</strong><span>填写 task、target、攻击方式、判定状态和 metadata，保存为草稿或提交。</span></a>
  <a class="choice-card" href="/review"><div class="choice-number">02</div><strong>审核与打分</strong><span>从已有 case 中选择，按可实现性、准确性、描述清晰度和综合质量评分。</span></a>
  <a class="choice-card" href="/scenes"><div class="choice-number">03</div><strong>查看场景评分</strong><span>浏览所有场景、筛选类别，并查看每条 case 的评分均值和历史审核记录。</span></a>
</section>
<script>{menu_js()}</script>
</main>""")


def menu_js() -> str:
    return r"""
async function loadMenuStats() {
  const el = document.getElementById('menuStats');
  try {
    const res = await fetch('/api/all-cases');
    const data = await res.json();
    const cases = data.cases || [];
    const reviewed = cases.filter(item => item.review_summary?.count).length;
    const selected = cases.filter(item => item.benchmark_selected).length;
    el.innerHTML = [
      stat(cases.length, '全部场景'),
      stat(reviewed, '已有评分'),
      stat(selected, '已选 benchmark')
    ].join('');
  } catch (error) {
    el.innerHTML = [
      stat('-', '全部场景'),
      stat('-', '已有评分'),
      stat('-', '标注员数')
    ].join('');
  }
}
function stat(value, label) {
  return `<div class="mini-stat"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
loadMenuStats();
"""


def design_page(user: str) -> str:
    return page("ClawTrap Benchmark 标注", f"""
{app_header(user, "MITM benchmark annotation", "design")}
<main>
<section class="hero compact">
  <div class="eyebrow">Design</div>
  <h2 class="hero-title">设计一个具体、可执行的攻击场景</h2>
  <p class="hero-copy">选择固定攻击类别与任务类型，描述真实任务、MITM 植入方式、判定状态和必要 metadata。草稿可以反复编辑，提交时会检查字段完整性。</p>
</section>
<div class="design-grid design-only">
  <section class="panel design-editor">
    <div class="section-heading"><div><p class="section-kicker">Editor</p><h2>场景编辑</h2></div></div>
    <form id="caseForm">
      <input type="hidden" name="id">
      <section class="form-section">
        <h3 class="form-section-title">场景设定</h3>
        <div class="field-grid">
          <div><label>任务类型</label><div class="select-shell"><select name="task_type" required>{options(TASK_TYPES)}</select></div></div>
          <div><label>攻击类型</label><div class="select-shell"><select name="attack_type" required>{options(ATTACK_TYPES)}</select></div></div>
          <div class="full"><label>MITM 植入形式</label><div class="checks">{checkboxes(INTERACTIVE_FORMS)}</div></div>
        </div>
      </section>
      <section class="form-section">
        <h3 class="form-section-title">任务定义</h3>
        <label>任务描述 task</label><textarea name="task" required></textarea>
        <label>任务目标 target</label><textarea name="target" required></textarea>
      </section>
      <section class="form-section">
        <h3 class="form-section-title">攻击与判定</h3>
        <label>攻击方法 attack_method</label><textarea name="attack_method" required></textarea>
        <label>成功防御状态 success_states（每行一条）</label><textarea name="success_states" required></textarea>
        <label>失败状态 failure_states（每行一条）</label><textarea name="failure_states" required></textarea>
        <label>攻击逻辑 logic</label><textarea name="logic" required></textarea>
        <label>Metadata（每行一条）</label><textarea name="metadata" required></textarea>
      </section>
      <div class="status-message" id="errors"></div>
      <div class="row form-actions">
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
{app_header(user, "Case review and scoring", "review")}
<main class="admin-main review-focus">
  <section class="hero compact">
    <div class="eyebrow">Review</div>
    <h2 class="hero-title">聚焦当前场景，完成质量评估</h2>
    <p class="hero-copy">左侧用于快速定位 case；右侧只保留审核所需信息：任务、攻击、成功/失败判定和评分。</p>
  </section>
  <section class="panel toolbar review-toolbar">
    <div><label>搜索</label><input id="reviewSearch" placeholder="task / target / attack_method / owner / id"></div>
    <div><label>来源</label><div class="select-shell"><select id="reviewOriginFilter"><option value="">全部</option><option value="local_json">本地 JSON</option><option value="database">云端数据库</option></select></div></div>
    <div class="row"><button type="button" onclick="loadReviewCases()">刷新</button></div>
  </section>
  <section class="review-layout">
    <div class="review-column"><div class="result-heading"><div><p class="section-kicker">Cases</p><h2>待审核列表</h2></div><span id="reviewCount">-</span></div><div class="review-list" id="reviewList"></div></div>
    <aside class="detail-panel" id="detailPanel"></aside>
  </section>
</main>
<script>{review_js()}</script>""")


def scenes_page(user: str) -> str:
    return page("ClawTrap 场景与评分", f"""
{app_header(user, "Scene library and scores", "scenes")}
<main class="admin-main">
  <section class="hero compact">
    <div class="eyebrow">Scene Library</div>
    <h2 class="hero-title">查看已有场景与评分记录</h2>
    <p class="hero-copy">查看已有场景、评分均值和审核记录。评分会保存在 case 的 <code>reviews</code> 字段里。</p>
  </section>
  <section class="panel toolbar">
    <div><label>状态</label><div class="select-shell"><select id="statusFilter"><option value="">全部</option><option value="draft">draft</option><option value="submitted">submitted</option></select></div></div>
    <div><label>来源</label><div class="select-shell"><select id="originFilter"><option value="">全部</option><option value="local_json">本地 JSON</option><option value="database">云端数据库</option></select></div></div>
    <div><label>Benchmark</label><div class="select-shell"><select id="selectedFilter"><option value="">全部</option><option value="selected">已选中</option><option value="unselected">未选中</option></select></div></div>
    <div><label>攻击类型</label><div class="select-shell"><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>任务类型</label><div class="select-shell"><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>植入形式</label><div class="select-shell"><select id="formFilter"><option value="">全部</option>{options(INTERACTIVE_FORMS)}</select></div></div>
    <div><label>搜索</label><input id="search" placeholder="task / target / id / owner"></div>
    <div class="row toolbar-actions"><button type="button" onclick="loadCases()">刷新</button></div>
  </section>
  <section class="stats" id="stats"></section>
  <section class="review-layout"><div class="review-column"><div class="result-heading"><div><p class="section-kicker">Cases</p><h2>场景列表</h2></div><span id="resultCount">-</span></div><div class="review-list" id="reviewList"></div></div><aside class="detail-panel" id="detailPanel"></aside></section>
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
    <div><label>数据集</label><div class="select-shell"><select id="dataset"></select></div></div>
    <div><label>状态</label><div class="select-shell"><select id="statusFilter"><option value="">全部</option><option value="draft">draft</option><option value="submitted">submitted</option></select></div></div>
    <div><label>来源</label><div class="select-shell"><select id="originFilter"><option value="">全部</option><option value="local_json">本地 JSON</option><option value="database">云端数据库</option></select></div></div>
    <div><label>Benchmark</label><div class="select-shell"><select id="selectedFilter"><option value="">全部</option><option value="selected">已选中</option><option value="unselected">未选中</option></select></div></div>
    <div><label>攻击类型</label><div class="select-shell"><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>任务类型</label><div class="select-shell"><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>植入形式</label><div class="select-shell"><select id="formFilter"><option value="">全部</option>{options(INTERACTIVE_FORMS)}</select></div></div>
    <div><label>搜索</label><input id="search" placeholder="task / target / attack_method / id / owner"></div>
    <div class="row toolbar-actions"><button type="button" onclick="loadCases()">刷新</button><button type="button" class="secondary" onclick="downloadFiltered()">导出当前筛选</button></div>
  </section>
  <section class="stats" id="stats"></section>
  <section class="review-layout"><div class="review-column"><div class="result-heading"><div><p class="section-kicker">Cases</p><h2>数据列表</h2></div><span id="resultCount">-</span></div><div class="review-list" id="reviewList"></div></div><aside class="detail-panel" id="detailPanel"></aside></section>
</main>
<script>{admin_js()}</script>""")


def annotator_js() -> str:
    return r"""
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
function clearForm() {
  form.reset();
  form.id.value = '';
  errors.textContent = '';
  errors.classList.remove('error');
  requestAnimationFrame(() => window.syncClawTrapSelects?.());
}
function editCase(item) {
  clearForm();
  for (const key of ['id','task','target','task_type','attack_method','logic','attack_type']) form[key].value = item[key] || '';
  form.success_states.value = fillLines(item.success_states);
  form.failure_states.value = fillLines(item.failure_states);
  form.metadata.value = fillLines(item.metadata);
  for (const box of form.querySelectorAll('input[name="interactive_form"]')) box.checked = (item.interactive_form || []).includes(box.value);
  window.syncClawTrapSelects?.();
  window.scrollTo({top: 0, behavior: 'smooth'});
}
async function saveCase(status) {
  errors.textContent = '';
  errors.classList.remove('error');
  const res = await fetch('/api/cases', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(formData(status))});
  const data = await res.json();
  if (!res.ok) {
    errors.classList.add('error');
    errors.textContent = (data.errors || [data.error || '保存失败']).join('\n');
    return;
  }
  editCase(data.case);
  errors.textContent = `已${status === 'submitted' ? '提交' : '保存草稿'}：${data.case.id}`;
}
function escapeHtml(value) { return String(value || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
"""


def shared_case_js() -> str:
    return r"""
let allCases = []; let filteredCases = []; let selectedId = null;
function summaryText(item) {
  const s = item.review_summary || {};
  if (!s.count) return '暂无评分';
  return `总分 ${totalScore(item) ?? '-'} · 综合 ${s.overall ?? '-'} · 可实现 ${s.feasibility ?? '-'} · 准确 ${s.accuracy ?? '-'} · 清晰 ${s.clarity ?? '-'} · ${s.count} 条`;
}
function totalScore(item) {
  const s = item.review_summary || {};
  if (s.total_score !== undefined && s.total_score !== null) return Number(s.total_score);
  const values = ['overall','feasibility','accuracy','clarity'].map(key => Number(s[key])).filter(value => Number.isFinite(value));
  if (!values.length) return null;
  return Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) / 100;
}
function rankSort(a, b) {
  const scoreA = totalScore(a), scoreB = totalScore(b);
  if (scoreA !== null || scoreB !== null) return (scoreB ?? -1) - (scoreA ?? -1);
  return String(b.updated_at || '').localeCompare(String(a.updated_at || ''));
}
function applyRanks(items) {
  const ranked = [...items].sort(rankSort);
  ranked.forEach((item, index) => { item.__rank = totalScore(item) === null ? null : index + 1; });
  return ranked;
}
function originValue(item) {
  return item.storage_origin || 'local_json';
}
function originLabel(origin) {
  return origin === 'database' ? '云端数据库' : '本地 JSON';
}
function originPill(item) {
  const origin = originValue(item);
  const cls = origin === 'database' ? 'origin-cloud' : 'origin-local';
  return `<span class="pill ${cls}">${originLabel(origin)}</span>`;
}
function caseTags(item) {
  const selected = item.benchmark_selected ? '<span class="pill selected-mark">已选入 benchmark</span>' : '';
  return `${selected}${originPill(item)}<span class="pill strong">${escapeHtml(item.status || 'draft')}</span><span class="pill">${escapeHtml(item.task_type)}</span><span class="pill">${escapeHtml(item.attack_type)}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span>`;
}
function groupedCaseList(onClickName='selectCase') {
  const rankedCases = applyRanks(filteredCases);
  const groups = [
    ['database', rankedCases.filter(item => originValue(item) === 'database')],
    ['local_json', rankedCases.filter(item => originValue(item) !== 'database')],
  ];
  return groups.filter(([, items]) => items.length).map(([origin, items]) => {
    const cards = items.map(item => {
      const originClass = `origin-${originValue(item)}`;
      return `<button class="review-item ${originClass} ${item.id === selectedId ? 'active' : ''}" data-case-id="${escapeHtml(item.id)}" type="button" onclick="${onClickName}('${escapeAttr(item.id)}')"><span class="review-item-title">${escapeHtml(item.task || '(未命名任务)')}</span><span class="review-item-attack">${escapeHtml(item.attack_method || '')}</span><span class="rank-line"><span class="rank-badge">#${escapeHtml(item.__rank ?? '-')}</span><span class="score-badge">总分 ${escapeHtml(totalScore(item) ?? '-')}</span></span><span class="meta">${escapeHtml(summaryText(item))}</span><span class="review-tags">${caseTags(item)}</span></button>`;
    }).join('');
    return `<div class="origin-divider">${originLabel(origin)} · ${items.length}</div>${cards}`;
  }).join('');
}
function renderCaseList(onClickName='selectCase') {
  if (!filteredCases.some(item => item.id === selectedId)) selectedId = filteredCases[0]?.id || null;
  const countEl = document.getElementById('resultCount') || document.getElementById('reviewCount');
  if (countEl) countEl.textContent = `${filteredCases.length} 条`;
  const list = document.getElementById('reviewList');
  list.innerHTML = groupedCaseList(onClickName) || '<div class="detail-empty">没有匹配的数据</div>';
}
function updateActiveListItem() {
  document.querySelectorAll('.review-item[data-case-id]').forEach(node => {
    node.classList.toggle('active', node.dataset.caseId === selectedId);
  });
}
function detailFields(item, includeReviews=true) {
  const reviews = Array.isArray(item.reviews) ? item.reviews : [];
  const reviewHtml = includeReviews ? `<dt>Reviews</dt><dd>${reviews.length ? `<ul>${reviews.map(r => `<li>${escapeHtml(r.reviewer || 'unknown')}：综合 ${escapeHtml(r.overall)}，可实现 ${escapeHtml(r.feasibility)}，准确 ${escapeHtml(r.accuracy)}，清晰 ${escapeHtml(r.clarity)}${r.comment ? ` · ${escapeHtml(r.comment)}` : ''}</li>`).join('')}</ul>` : '暂无评分'}</dd>` : '';
  return `<dl><dt>Attack Method</dt><dd>${escapeHtml(item.attack_method)}</dd><dt>Target</dt><dd>${escapeHtml(item.target)}</dd><dt>Success States</dt><dd>${listText(item.success_states)}</dd><dt>Failure States</dt><dd>${listText(item.failure_states)}</dd><dt>Metadata</dt><dd>${listText(item.metadata)}</dd><dt>Logic</dt><dd>${escapeHtml(item.logic)}</dd>${reviewHtml}</dl>`;
}
function baseDetail(item) {
  return `<h2>${escapeHtml(item.task || '(未命名任务)')}</h2><div class="meta">${escapeHtml(item.id)} · ${escapeHtml(item.owner)} · ${escapeHtml(item.created_at || '')}</div><div class="rank-line"><span class="rank-badge">#${escapeHtml(item.__rank ?? '-')}</span><span class="score-badge">总分 ${escapeHtml(totalScore(item) ?? '-')}</span></div><div class="review-tags">${caseTags(item)}<span class="pill">${escapeHtml(summaryText(item))}</span></div>`;
}
async function toggleBenchmarkSelection(id, selected) {
  const res = await fetch(`/api/cases/${encodeURIComponent(id)}/benchmark-selection`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({selected})});
  const data = await res.json();
  if (!res.ok) throw new Error((data.errors || [data.error || '更新选中状态失败']).join('\n'));
  const index = allCases.findIndex(item => item.id === data.case.id);
  if (index >= 0) allCases[index] = data.case;
  selectedId = data.case.id;
  return data.case;
}
function benchmarkButton(item, handlerName='toggleSelectedCase') {
  const selected = Boolean(item.benchmark_selected);
  return `<div class="benchmark-action"><button type="button" class="${selected ? 'selected' : ''}" onclick="${handlerName}('${escapeAttr(item.id)}', ${selected ? 'false' : 'true'})">${selected ? '取消选中 benchmark' : '选中进入 benchmark'}</button></div>`;
}
function compactTags(item) {
  return `<span class="pill strong">${escapeHtml(item.task_type || '-')}</span><span class="pill">${escapeHtml(item.attack_type || '-')}</span><span class="pill">${escapeHtml((item.interactive_form || []).join(' / ') || '-')}</span>${originPill(item)}${item.benchmark_selected ? '<span class="pill selected-mark">已选入 benchmark</span>' : ''}`;
}
function focusList(items) {
  if (!Array.isArray(items) || !items.length) return '<ul><li>-</li></ul>';
  return `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}
function metadataTokens(items) {
  if (!Array.isArray(items) || !items.length) return '<span class="metadata-token">无补充信息</span>';
  return items.map(item => `<span class="metadata-token">${escapeHtml(item)}</span>`).join('');
}
function focusedReviewDetail(item) {
  return `<div class="focus-case">
    <section class="focus-card focus-header">
      <div>
        <h2 class="focus-title">${escapeHtml(item.task || '(未命名任务)')}</h2>
        <div class="meta">${escapeHtml(item.id)} · ${escapeHtml(item.owner || '')} · ${escapeHtml(item.created_at || '')}</div>
        <div class="rank-line"><span class="rank-badge">#${escapeHtml(item.__rank ?? '-')}</span><span class="score-badge">总分 ${escapeHtml(totalScore(item) ?? '-')}</span><span class="pill">${escapeHtml(summaryText(item))}</span></div>
        <div class="focus-meta">${compactTags(item)}</div>
      </div>
      <div class="focus-action">${benchmarkButton(item)}</div>
    </section>
    <section class="focus-card">
      <div class="focus-grid">
        <article class="focus-block"><span class="focus-label">User Task</span><p class="focus-text">${escapeHtml(item.task)}</p></article>
        <article class="focus-block"><span class="focus-label">Expected Target</span><p class="focus-text">${escapeHtml(item.target)}</p></article>
        <article class="focus-block focus-attack full"><span class="focus-label">MITM Attack</span><p class="focus-text">${escapeHtml(item.attack_method)}</p></article>
      </div>
    </section>
    <section class="judgement-grid">
      <article class="judgement success"><h3>Success Criteria</h3>${focusList(item.success_states)}</article>
      <article class="judgement failure"><h3>Failure Criteria</h3>${focusList(item.failure_states)}</article>
    </section>
    <section class="focus-card">
      <div class="focus-grid">
        <article class="focus-block"><span class="focus-label">Implementation Notes</span><div class="metadata-strip">${metadataTokens(item.metadata)}</div></article>
        <article class="focus-block"><span class="focus-label">Attack Logic</span><p class="focus-text">${escapeHtml(item.logic || '-')}</p></article>
      </div>
    </section>
  </div>`;
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
  filterReviewCases();
}
function filterReviewCases() {
  const q = (document.getElementById('reviewSearch')?.value || '').trim().toLowerCase();
  const origin = document.getElementById('reviewOriginFilter')?.value || '';
  filteredCases = applyRanks(allCases.filter(item => (!origin || originValue(item) === origin) && (!q || JSON.stringify(item).toLowerCase().includes(q))));
  renderCaseList();
  renderDetail();
}
function selectCase(id) { selectedId = id; updateActiveListItem(); renderDetail(); }
function renderDetail() {
  const panel = document.getElementById('detailPanel');
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) { panel.innerHTML = '<div class="detail-empty">选择左侧条目进行审核</div>'; return; }
  panel.innerHTML = `${focusedReviewDetail(item)}
    <form id="reviewForm" class="focus-card review-score-panel">
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
async function toggleSelectedCase(id, selected) {
  const panel = document.getElementById('detailPanel');
  try {
    await toggleBenchmarkSelection(id, selected);
    filterReviewCases();
  } catch (error) {
    panel.insertAdjacentHTML('afterbegin', `<div class="errors">${escapeHtml(error.message)}</div>`);
  }
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
  selectedId = data.case.id;
  filterReviewCases();
}
document.getElementById('reviewSearch')?.addEventListener('input', filterReviewCases);
document.getElementById('reviewOriginFilter')?.addEventListener('input', filterReviewCases);
loadReviewCases();
"""


def scenes_js() -> str:
    return shared_case_js() + r"""
const controls = ['statusFilter','originFilter','selectedFilter','attackFilter','taskFilter','formFilter','search'].map(id => document.getElementById(id));
async function loadCases() {
  const res = await fetch('/api/all-cases');
  const data = await res.json();
  allCases = data.cases || [];
  render();
}
function render() {
  const status = document.getElementById('statusFilter').value, origin = document.getElementById('originFilter').value, selected = document.getElementById('selectedFilter').value, attack = document.getElementById('attackFilter').value, task = document.getElementById('taskFilter').value, form = document.getElementById('formFilter').value, q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = applyRanks(allCases.filter(item => (!status || item.status === status) && (!origin || originValue(item) === origin) && (!selected || (selected === 'selected') === Boolean(item.benchmark_selected)) && (!attack || item.attack_type === attack) && (!task || item.task_type === task) && (!form || (item.interactive_form || []).includes(form)) && (!q || JSON.stringify(item).toLowerCase().includes(q))));
  renderStats(); renderCaseList(); renderDetail();
}
function renderStats() {
  const reviewed = filteredCases.filter(c => c.review_summary?.count).length;
  const cloud = filteredCases.filter(c => originValue(c) === 'database').length;
  const local = filteredCases.length - cloud;
  document.getElementById('stats').innerHTML = [stat('当前筛选', filteredCases.length), stat('云端数据', cloud), stat('本地数据', local), stat('已选 benchmark', filteredCases.filter(c => c.benchmark_selected).length), stat('已有评分', reviewed), stat('未评分', filteredCases.length - reviewed), stat('标注员数', new Set(filteredCases.map(c => c.owner || '')).size)].join('');
}
function stat(label, value) { return `<article class="stat"><strong>${value}</strong><span>${escapeHtml(label)}</span></article>`; }
function selectCase(id) { selectedId = id; updateActiveListItem(); renderDetail(); }
function renderDetail() {
  const panel = document.getElementById('detailPanel');
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) { panel.innerHTML = '<div class="detail-empty">选择左侧条目查看评分</div>'; return; }
  panel.innerHTML = `${baseDetail(item)}${benchmarkButton(item)}<div class="score-summary">${['total_score','overall','feasibility','accuracy','clarity'].map(k => `<span class="pill strong">${k}: ${escapeHtml(k === 'total_score' ? totalScore(item) ?? '-' : item.review_summary?.[k] ?? '-')}</span>`).join('')}</div>${detailFields(item, true)}`;
}
async function toggleSelectedCase(id, selected) {
  const panel = document.getElementById('detailPanel');
  try {
    await toggleBenchmarkSelection(id, selected);
    render();
  } catch (error) {
    panel.insertAdjacentHTML('afterbegin', `<div class="errors">${escapeHtml(error.message)}</div>`);
  }
}
controls.forEach(el => el.addEventListener('input', render));
loadCases();
"""


def admin_js() -> str:
    return r"""
let allCases = []; let filteredCases = []; let selectedId = null;
const dataset = document.getElementById('dataset');
const controls = ['statusFilter','originFilter','selectedFilter','attackFilter','taskFilter','formFilter','search'].map(id => document.getElementById(id));
async function init() {
  const res = await fetch('/api/admin/cases'); const data = await res.json();
  dataset.innerHTML = data.datasets.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
  dataset.value = data.dataset; allCases = data.cases || [];
  window.refreshClawTrapSelects?.();
  window.syncClawTrapSelects?.();
  controls.concat(dataset).forEach(el => el.addEventListener('input', () => dataset === el ? loadCases() : render()));
  render();
}
async function loadCases() {
  const res = await fetch(`/api/admin/cases?dataset=${encodeURIComponent(dataset.value)}`);
  const data = await res.json(); allCases = data.cases || []; window.syncClawTrapSelects?.(); render();
}
function render() {
  const status = document.getElementById('statusFilter').value, origin = document.getElementById('originFilter').value, selected = document.getElementById('selectedFilter').value, attack = document.getElementById('attackFilter').value, task = document.getElementById('taskFilter').value, form = document.getElementById('formFilter').value, q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = applyRanks(allCases.filter(item => (!status || item.status === status) && (!origin || originValue(item) === origin) && (!selected || (selected === 'selected') === Boolean(item.benchmark_selected)) && (!attack || item.attack_type === attack) && (!task || item.task_type === task) && (!form || (item.interactive_form || []).includes(form)) && (!q || JSON.stringify(item).toLowerCase().includes(q))));
  renderStats(); renderList(); renderDetail();
}
function renderStats() {
  document.getElementById('stats').innerHTML = [
    stat('当前筛选', filteredCases.length), stat('全部数据', allCases.length),
    stat('云端数据', filteredCases.filter(c => originValue(c) === 'database').length),
    stat('本地数据', filteredCases.filter(c => originValue(c) !== 'database').length),
    stat('已选 benchmark', filteredCases.filter(c => c.benchmark_selected).length),
    stat('submitted', filteredCases.filter(c => c.status === 'submitted').length),
    stat('draft', filteredCases.filter(c => c.status === 'draft').length),
    stat('标注员数', new Set(filteredCases.map(c => c.owner || '')).size)
  ].join('');
}
function stat(label, value) { return `<article class="stat"><strong>${value}</strong><span>${escapeHtml(label)}</span></article>`; }
function originValue(item) { return item.storage_origin || 'local_json'; }
function originLabel(origin) { return origin === 'database' ? '云端数据库' : '本地 JSON'; }
function totalScore(item) {
  const s = item.review_summary || {};
  if (s.total_score !== undefined && s.total_score !== null) return Number(s.total_score);
  const values = ['overall','feasibility','accuracy','clarity'].map(key => Number(s[key])).filter(value => Number.isFinite(value));
  if (!values.length) return null;
  return Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) / 100;
}
function rankSort(a, b) {
  const scoreA = totalScore(a), scoreB = totalScore(b);
  if (scoreA !== null || scoreB !== null) return (scoreB ?? -1) - (scoreA ?? -1);
  return String(b.updated_at || '').localeCompare(String(a.updated_at || ''));
}
function applyRanks(items) {
  const ranked = [...items].sort(rankSort);
  ranked.forEach((item, index) => { item.__rank = totalScore(item) === null ? null : index + 1; });
  return ranked;
}
function originPill(item) {
  const origin = originValue(item);
  const cls = origin === 'database' ? 'origin-cloud' : 'origin-local';
  return `<span class="pill ${cls}">${originLabel(origin)}</span>`;
}
function adminTags(item) {
  const selected = item.benchmark_selected ? '<span class="pill selected-mark">已选入 benchmark</span>' : '';
  return `${selected}${originPill(item)}<span class="pill strong">${escapeHtml(item.status || 'draft')}</span><span class="pill">${escapeHtml(item.task_type)}</span><span class="pill">${escapeHtml(item.attack_type)}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span>`;
}
function renderList() {
  if (!filteredCases.some(item => item.id === selectedId)) selectedId = filteredCases[0]?.id || null;
  const countEl = document.getElementById('resultCount');
  if (countEl) countEl.textContent = `${filteredCases.length} 条`;
  const list = document.getElementById('reviewList');
  const rankedCases = applyRanks(filteredCases);
  const groups = [
    ['database', rankedCases.filter(item => originValue(item) === 'database')],
    ['local_json', rankedCases.filter(item => originValue(item) !== 'database')],
  ];
  list.innerHTML = groups.filter(([, items]) => items.length).map(([origin, items]) => {
    const cards = items.map(item => `<button class="review-item origin-${originValue(item)} ${item.id === selectedId ? 'active' : ''}" data-case-id="${escapeHtml(item.id)}" type="button" onclick="selectCase('${escapeAttr(item.id)}')"><span class="review-item-title">${escapeHtml(item.task || '(未命名任务)')}</span><span class="review-item-attack">${escapeHtml(item.attack_method || '')}</span><span class="rank-line"><span class="rank-badge">#${escapeHtml(item.__rank ?? '-')}</span><span class="score-badge">总分 ${escapeHtml(totalScore(item) ?? '-')}</span></span><span class="review-tags">${adminTags(item)}</span></button>`).join('');
    return `<div class="origin-divider">${originLabel(origin)} · ${items.length}</div>${cards}`;
  }).join('') || '<div class="detail-empty">没有匹配的数据</div>';
}
function updateActiveListItem() {
  document.querySelectorAll('.review-item[data-case-id]').forEach(node => {
    node.classList.toggle('active', node.dataset.caseId === selectedId);
  });
}
function selectCase(id) { selectedId = id; updateActiveListItem(); renderDetail(); }
function renderDetail() {
  const panel = document.getElementById('detailPanel'); const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) { panel.innerHTML = '<div class="detail-empty">选择左侧条目查看详情</div>'; return; }
  panel.innerHTML = `<h2>${escapeHtml(item.task || '(未命名任务)')}</h2><div class="meta">${escapeHtml(item.id)} · ${escapeHtml(item.owner)} · ${escapeHtml(item.created_at || '')}</div><div class="rank-line"><span class="rank-badge">#${escapeHtml(item.__rank ?? '-')}</span><span class="score-badge">总分 ${escapeHtml(totalScore(item) ?? '-')}</span></div><div class="review-tags">${adminTags(item)}</div>${benchmarkButton(item)}<div class="score-summary">${['total_score','overall','feasibility','accuracy','clarity'].map(k => `<span class="pill strong">${k}: ${escapeHtml(k === 'total_score' ? totalScore(item) ?? '-' : item.review_summary?.[k] ?? '-')}</span>`).join('')}</div><dl><dt>Attack Method</dt><dd>${escapeHtml(item.attack_method)}</dd><dt>Success States</dt><dd>${listText(item.success_states)}</dd><dt>Failure States</dt><dd>${listText(item.failure_states)}</dd><dt>Metadata</dt><dd>${listText(item.metadata)}</dd><dt>Target</dt><dd>${escapeHtml(item.target)}</dd><dt>Logic</dt><dd>${escapeHtml(item.logic)}</dd></dl>`;
}
async function toggleSelectedCase(id, selected) {
  const panel = document.getElementById('detailPanel');
  try {
    const res = await fetch(`/api/cases/${encodeURIComponent(id)}/benchmark-selection`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({selected})});
    const data = await res.json();
    if (!res.ok) throw new Error((data.errors || [data.error || '更新选中状态失败']).join('\n'));
    const index = allCases.findIndex(item => item.id === data.case.id);
    if (index >= 0) allCases[index] = data.case;
    selectedId = data.case.id;
    render();
  } catch (error) {
    panel.insertAdjacentHTML('afterbegin', `<div class="errors">${escapeHtml(error.message)}</div>`);
  }
}
function benchmarkButton(item) {
  const selected = Boolean(item.benchmark_selected);
  return `<div class="benchmark-action"><button type="button" class="${selected ? 'selected' : ''}" onclick="toggleSelectedCase('${escapeAttr(item.id)}', ${selected ? 'false' : 'true'})">${selected ? '取消选中 benchmark' : '选中进入 benchmark'}</button></div>`;
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
