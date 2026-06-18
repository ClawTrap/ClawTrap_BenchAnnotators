from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, request, session

from .auth import authenticate
from .constants import ATTACK_TYPES, INTERACTIVE_FORMS, TASK_TYPES
from .schema import normalize_case, validate_case
from .storage import DEFAULT_DATASET, list_file_datasets, read_local_dataset, set_benchmark_selected, set_expert_decision, update_case_fields, upsert_case


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


def options(values: list[str]) -> str:
    return "".join(f'<option value="{value}">{value}</option>' for value in values)


def checkboxes(values: list[str]) -> str:
    return "".join(f'<label class="choice-pill"><input type="checkbox" name="interactive_form" value="{value}"><span>{value}</span></label>' for value in values)


def js_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def can_access_workspace() -> bool:
    return session.get("role") in ("annotator", "admin")


def can_access_admin() -> bool:
    return session.get("role") == "admin"


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --paper:#f7f7f2; --paper-deep:#ecece5; --panel:#fffdfa; --panel-soft:#f1f1ea;
      --text:#101010; --ink:#2f2f2f; --muted:#67645d; --line:rgba(20,20,20,.12);
      --line-strong:rgba(20,20,20,.2); --navy:#171717; --navy-soft:#2b2b2b;
      --accent:#9d252c; --accent-strong:#861b22; --accent-soft:#f3e7e7;
      --teal:#147486; --teal-soft:#e5f0f2; --green:#067647; --danger:#b42318; --shadow:0 24px 70px rgba(20,20,20,.08);
    }}
    * {{ box-sizing:border-box; }}
    html {{ background:var(--paper); color-scheme:light; scroll-behavior:smooth; }}
    body {{
      margin:0; min-height:100vh; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
      background:
        linear-gradient(180deg,rgba(255,253,250,.78),rgba(247,247,242,.98) 34%),
        var(--paper);
      color:var(--ink);
      line-height:1.45;
    }}
    ::selection {{ background:rgba(157,37,44,.18); color:var(--text); }}
    *::-webkit-scrollbar {{ width:10px; height:10px; }}
    *::-webkit-scrollbar-track {{ background:rgba(226,232,240,.64); border-radius:999px; }}
    *::-webkit-scrollbar-thumb {{ background:rgba(100,116,139,.32); border:2px solid rgba(241,245,249,.84); border-radius:999px; }}
    *::-webkit-scrollbar-thumb:hover {{ background:rgba(20,116,134,.42); }}
    body::before {{ content:''; position:fixed; inset:0; z-index:-1; pointer-events:none; background:linear-gradient(115deg,transparent 0%,transparent 54%,rgba(157,37,44,.035) 54.2%,transparent 66%); }}
    header {{
      width:100%; margin:0; display:flex; justify-content:space-between;
      align-items:center; gap:18px; padding:12px 50px; border:0; border-bottom:1px solid rgba(20,20,20,.1); border-radius:0;
      background:rgba(247,247,242,.9); color:var(--text); position:sticky; top:0; z-index:2;
      box-shadow:0 14px 46px rgba(20,20,20,.05); backdrop-filter:blur(18px);
    }}
    main {{ max-width:1240px; margin:0 auto; padding:0 28px 70px; }}
    h1,h2,h3 {{ color:var(--text); }}
    h1 {{ font-size:29px; margin:0; font-weight:900; letter-spacing:0; line-height:.98; }}
    h2 {{ font-size:26px; margin:0 0 14px; font-weight:900; letter-spacing:0; }}
    .brand-lockup {{ display:flex; align-items:center; gap:12px; min-width:0; }}
    header h1 {{ color:var(--text); }}
    .brand-mark {{ width:34px; height:34px; border-radius:8px; display:grid; place-items:center; background:linear-gradient(145deg,var(--accent),var(--teal)); color:#fff; font-size:20px; font-weight:900; box-shadow:none; }}
    .brand-subtitle {{ color:var(--muted); font-size:11px; line-height:1.15; margin-top:4px; font-weight:800; letter-spacing:0; text-transform:uppercase; }}
    .top-nav {{ display:flex; align-items:center; gap:8px; }}
    .app-nav {{ display:flex; align-items:center; gap:0; padding:0; border:0; border-radius:0; background:transparent; }}
    .app-nav a {{ position:relative; display:inline-flex; align-items:center; min-height:34px; padding:7px 12px; border-radius:0; color:#333; text-decoration:none; font-size:14px; font-weight:700; }}
    .app-nav a::after {{ content:''; position:absolute; left:12px; right:12px; bottom:-7px; height:2px; background:var(--accent); opacity:0; transform:scaleX(.45); transform-origin:left; transition:opacity .16s ease, transform .16s ease; }}
    .app-nav a:hover,.app-nav a.active {{ background:transparent; color:#111; box-shadow:none; }}
    .app-nav a:hover::after,.app-nav a.active::after {{ opacity:1; transform:scaleX(1); }}
    .user-chip {{ display:inline-flex; align-items:center; min-height:36px; padding:7px 12px; border:1px solid var(--line); border-radius:999px; background:rgba(255,253,250,.58); color:var(--text); font-size:12px; font-weight:850; }}
    .hero {{
      position:relative; display:grid; grid-template-columns:minmax(0,.95fr) minmax(320px,.62fr); column-gap:54px; row-gap:16px;
      align-items:end; margin:0 0 34px; padding:78px 0 56px; border:0; border-bottom:1px solid var(--line);
      background:transparent; box-shadow:none; overflow:visible; color:var(--text);
    }}
    .hero::before {{ content:''; position:absolute; left:0; top:0; width:120px; height:2px; background:linear-gradient(90deg,var(--accent),var(--teal)); pointer-events:none; }}
    .hero::after {{ content:''; position:absolute; right:0; bottom:0; width:42%; height:1px; background:linear-gradient(90deg,transparent,rgba(20,116,134,.34)); pointer-events:none; }}
    .hero > * {{ position:relative; }}
    .hero.compact {{ padding:58px 0 40px; }}
    .eyebrow {{ display:inline-flex; padding:0; color:var(--accent); font-size:12px; font-weight:800; letter-spacing:0; text-transform:uppercase; }}
    .hero-title {{ grid-column:1; max-width:900px; margin:10px 0 0; font-size:58px; line-height:1; letter-spacing:0; color:var(--text); font-weight:780; }}
    .hero.compact .hero-title {{ font-size:38px; max-width:760px; }}
    .hero-copy {{ grid-column:2; grid-row:2; max-width:520px; color:#3f3f3a; font-size:17px; line-height:1.75; margin:0 0 3px; }}
    .hero-copy strong {{ color:var(--text); }}
    code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.92em; color:var(--accent); background:rgba(255,253,250,.72); border:1px solid rgba(20,20,20,.12); border-radius:6px; padding:1px 5px; }}
    .section-heading {{ display:flex; justify-content:space-between; align-items:flex-end; gap:12px; margin-bottom:14px; }}
    .section-kicker {{ margin:0 0 5px; color:var(--accent-strong); font-size:10px; font-weight:900; letter-spacing:0; text-transform:uppercase; }}
    .button, button {{
      border:1px solid var(--accent-strong); background:var(--accent-strong); color:#fff; padding:9px 15px;
      border-radius:999px; cursor:pointer; text-decoration:none; font-size:13px; font-weight:750;
      box-shadow:0 1px 0 rgba(20,20,20,.08); letter-spacing:0;
      transition:background .16s ease, border-color .16s ease, color .16s ease, box-shadow .16s ease, transform .12s ease, filter .16s ease;
    }}
    button:hover,.button:hover {{ background:var(--accent); border-color:var(--accent); box-shadow:0 7px 18px rgba(157,37,44,.16); transform:translateY(-1px); filter:none; }}
    button:active,.button:active {{ transform:translateY(1px) scale(.985); box-shadow:0 1px 4px rgba(20,20,20,.12); filter:brightness(.96); }}
    button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,.select-card-trigger:focus-visible,.choice-pill input:focus-visible + span {{
      outline:2px solid rgba(157,37,44,.38); outline-offset:2px;
    }}
    .secondary {{ background:rgba(255,255,255,.55); color:var(--navy); border-color:var(--line-strong); box-shadow:0 1px 0 rgba(20,20,20,.06); }}
    header .secondary {{ color:var(--navy); border-color:var(--line); }}
    .secondary:hover {{ background:#fff; color:var(--navy); border-color:rgba(20,116,134,.42); box-shadow:0 7px 18px rgba(20,116,134,.12); }}
    header .secondary:hover {{ background:#fff; color:var(--navy); border-color:rgba(20,116,134,.28); }}
    .panel,.case,.login,.detail-panel,.stat,.review-item {{
      background:rgba(255,253,250,.86); border:1px solid var(--line); border-radius:8px; box-shadow:none;
    }}
    .panel {{ padding:22px; background:rgba(255,253,250,.72); overflow:visible; backdrop-filter:blur(12px); }}
    .grid {{ display:grid; grid-template-columns:340px minmax(0,1fr); gap:18px; align-items:start; }}
    .design-grid {{ display:grid; grid-template-columns:360px minmax(0,1fr); gap:18px; align-items:start; }}
    .design-grid.design-only {{ grid-template-columns:minmax(0,1fr); max-width:980px; }}
    .design-editor {{ width:100%; }}
    .sticky-panel {{ position:sticky; top:92px; }}
    .case {{ margin-bottom:10px; padding:14px; box-shadow:none; background:rgba(255,253,250,.86); }}
    .case h3 {{ margin:0 0 8px; font-size:13px; line-height:1.5; }}
    .meta {{ color:var(--muted); font-size:12px; line-height:1.55; font-weight:600; }}
    .empty-note {{ color:var(--muted); padding:20px; text-align:center; background:rgba(255,253,250,.65); border:1px dashed var(--line-strong); border-radius:8px; font-size:13px; font-weight:700; line-height:1.65; }}
    label {{ display:block; font-weight:800; margin:12px 0 6px; font-size:12px; color:#344054; }}
    input,select,textarea {{
      width:100%; border:1px solid var(--line); border-radius:8px; padding:10px 11px; font:inherit;
      background:rgba(255,255,255,.86); outline:none; transition:border-color .12s, background .12s, box-shadow .12s;
    }}
    input:focus,select:focus,textarea:focus {{ border-color:rgba(20,116,134,.45); box-shadow:0 0 0 3px rgba(20,116,134,.08); background:#fff; }}
    textarea {{ min-height:88px; resize:vertical; line-height:1.6; }}
    .checks {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(158px,1fr)); gap:9px; }}
    .form-section {{ margin-top:16px; padding:22px; border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.72); overflow:visible; }}
    .form-section:first-of-type {{ margin-top:0; }}
    .form-section-title {{ display:flex; align-items:center; gap:9px; margin:0 0 12px; color:var(--text); font-size:18px; line-height:1.15; font-weight:900; }}
    .form-section-title::before {{ content:''; width:18px; height:2px; border-radius:999px; background:var(--teal); }}
    .field-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .field-grid .full {{ grid-column:1 / -1; }}
    .choice-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:1px; border:1px solid var(--line); background:var(--line); }}
    .choice-card {{ position:relative; display:grid; grid-template-rows:auto auto 1fr; min-height:238px; padding:30px; color:var(--ink); text-decoration:none; background:rgba(255,253,250,.94); border:0; border-radius:0; box-shadow:none; transition:background .18s ease, color .18s ease; overflow:hidden; }}
    .choice-card::before {{ content:''; position:absolute; left:30px; right:30px; top:0; height:2px; background:linear-gradient(90deg,var(--accent),var(--teal)); opacity:.75; }}
    .choice-card:hover {{ transform:none; border-color:transparent; background:#fff; color:var(--ink); box-shadow:none; }}
    .choice-card:hover strong {{ color:var(--text); }}
    .choice-card:hover span {{ color:#444; }}
    .choice-card strong {{ display:block; margin:34px 0 14px; color:var(--text); font-size:27px; line-height:1.12; letter-spacing:0; font-weight:760; }}
    .choice-card span {{ color:var(--muted); font-size:13px; line-height:1.62; font-weight:600; }}
    .choice-number {{ width:auto; height:auto; display:inline-flex; place-items:center; color:var(--teal); background:transparent; border:0; border-radius:0; font-size:13px; font-weight:800; }}
    .choice-card:hover .choice-number {{ color:var(--accent); }}
    .overview-grid {{ display:grid; grid-template-columns:minmax(0,1.12fr) minmax(320px,.88fr); gap:1px; margin-bottom:22px; border:1px solid var(--line); background:var(--line); }}
    .overview-card {{ min-height:172px; padding:28px; background:rgba(255,253,250,.88); border:0; border-radius:0; box-shadow:none; overflow:visible; }}
    .overview-card h2 {{ margin-bottom:8px; }}
    .overview-card p {{ margin:0; color:var(--muted); font-size:14px; line-height:1.7; font-weight:600; }}
    .overview-stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:16px; }}
    .mini-stat {{ padding:13px 14px; border:1px solid var(--line); border-radius:8px; background:rgba(247,247,242,.72); }}
    .mini-stat strong {{ display:block; color:var(--text); font-size:24px; line-height:1; }}
    .mini-stat span {{ display:block; color:var(--muted); font-size:11px; font-weight:800; margin-top:7px; }}
    .account-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }}
    .choice-pill {{ position:relative; display:flex; align-items:center; justify-content:center; margin:0; padding:0; cursor:pointer; }}
    .choice-pill input {{ position:absolute; opacity:0; pointer-events:none; }}
    .choice-pill span {{ width:100%; min-height:42px; display:flex; align-items:center; justify-content:center; padding:8px 10px; border:1px solid var(--line); border-radius:999px; background:rgba(255,253,250,.72); color:#475467; font-size:13px; font-weight:800; transition:background .12s,border-color .12s,color .12s,transform .12s; }}
    .choice-pill:hover span {{ border-color:rgba(20,116,134,.42); transform:translateY(-1px); }}
    .choice-pill input:checked + span {{ border-color:rgba(157,37,44,.5); background:rgba(157,37,44,.1); color:var(--accent); box-shadow:none; }}
    .select-shell {{ position:relative; }}
    .select-shell.open {{ z-index:80; }}
    .select-shell select {{ appearance:none; padding-right:34px; background:rgba(255,253,250,.82); color:var(--text); font-weight:750; }}
    .select-shell::after {{ content:'⌄'; position:absolute; right:12px; bottom:9px; color:var(--accent-strong); pointer-events:none; font-weight:900; }}
    .select-shell.enhanced::after {{ display:none; }}
    .select-shell.enhanced select {{ position:absolute; width:1px; height:1px; opacity:0; pointer-events:none; overflow:hidden; }}
    .select-card-trigger {{
      width:100%; min-height:42px; display:flex; align-items:center; justify-content:space-between; gap:10px;
      padding:9px 11px; border:1px solid var(--line); border-radius:8px;
      background:rgba(255,253,250,.82); color:var(--text); box-shadow:none;
      font-size:13px; font-weight:800; text-align:left;
    }}
    .select-card-trigger:hover,.select-shell.open .select-card-trigger {{ background:#fff; border-color:rgba(20,116,134,.42); color:var(--text); }}
    .select-card-trigger::after {{ content:'⌄'; color:var(--accent-strong); font-weight:900; transition:transform .12s; }}
    .select-shell.open .select-card-trigger::after {{ transform:rotate(180deg); }}
    .select-card-menu {{
      position:absolute; left:0; right:0; top:calc(100% + 6px); z-index:30; display:none; gap:5px;
      max-height:min(280px,52vh); overflow:auto; padding:7px; border:1px solid rgba(20,20,20,.16); border-radius:8px;
      background:rgba(255,253,250,.98); box-shadow:0 18px 42px rgba(20,20,20,.12);
    }}
    .select-shell.drop-up .select-card-menu {{ top:auto; bottom:calc(100% + 6px); }}
    .select-shell.open .select-card-menu {{ display:grid; }}
    .select-card-option {{
      width:100%; min-height:36px; padding:8px 10px; border:1px solid transparent; border-radius:6px;
      background:transparent; color:var(--ink); box-shadow:none; text-align:left; font-size:13px; font-weight:750;
    }}
    .select-card-option:hover {{ background:rgba(20,116,134,.07); border-color:rgba(20,116,134,.16); color:var(--text); }}
    .select-card-option.active {{ background:rgba(157,37,44,.1); border-color:rgba(157,37,44,.28); color:var(--accent); }}
    .row {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .errors {{ color:var(--danger); font-size:13px; white-space:pre-wrap; margin-top:8px; }}
    .status-message {{ color:var(--accent-strong); font-size:13px; white-space:pre-wrap; margin-top:8px; font-weight:700; }}
    .status-message.error {{ color:var(--danger); }}
    .login-main {{ min-height:100vh; display:grid; place-items:center; padding:28px; }}
    .login {{ width:min(460px,100%); margin:0 auto; padding:34px; background:rgba(255,253,250,.9); }}
    .login h1 {{ margin-bottom:4px; }}
    .login-note {{ margin:18px 0 20px; padding:13px 14px; color:var(--muted); background:rgba(247,247,242,.74); border:1px solid var(--line); border-radius:8px; font-size:13px; line-height:1.65; font-weight:650; }}
    .admin-main {{ max-width:1480px; }}
    .toolbar {{
      display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
      gap:12px; align-items:end; padding:16px; box-shadow:none; position:relative; z-index:5; overflow:visible;
    }}
    .toolbar label {{ margin-top:0; }}
    .toolbar-actions {{ grid-column:1/-1; }}
    .review-toolbar {{ grid-template-columns:minmax(260px,1fr) 180px auto; margin-bottom:14px; }}
    .form-actions {{ margin-top:14px; padding-top:14px; border-top:1px solid var(--line); }}
    .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(128px,1fr)); gap:10px; margin:14px 0; }}
    .stat {{ padding:14px 15px; box-shadow:none; background:rgba(255,253,250,.82); }}
    .stat strong {{ display:block; font-size:23px; line-height:1; color:var(--text); }}
    .stat span {{ display:block; color:var(--muted); font-size:12px; margin-top:7px; font-weight:700; }}
    .rank-dashboard {{ display:grid; gap:18px; }}
    .rank-summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:1px; border:1px solid var(--line); background:var(--line); }}
    .rank-summary .stat {{ border:0; border-radius:0; background:rgba(255,253,250,.88); padding:18px; }}
    .rank-board {{ border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.84); overflow:hidden; }}
    .rank-head,.rank-row {{ display:grid; grid-template-columns:72px minmax(0,1fr) 136px 160px 148px; gap:14px; align-items:center; padding:14px 18px; border-bottom:1px solid var(--line); }}
    .rank-head {{ background:rgba(247,247,242,.82); color:var(--muted); font-size:11px; font-weight:900; text-transform:uppercase; }}
    .rank-row {{ color:var(--ink); transition:background .14s ease; }}
    .rank-row:last-child {{ border-bottom:0; }}
    .rank-row:hover {{ background:#fff; }}
    .rank-index {{ color:var(--accent-strong); font-size:13px; font-weight:900; }}
    .rank-case-title {{ display:block; color:var(--text); font-size:14px; font-weight:850; line-height:1.52; }}
    .rank-case-meta {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
    .rank-meter {{ height:4px; margin-top:9px; background:rgba(20,20,20,.08); border-radius:999px; overflow:hidden; }}
    .rank-meter span {{ display:block; height:100%; background:linear-gradient(90deg,var(--accent),var(--teal)); }}
    .rank-actions {{ display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap; }}
    .rank-empty {{ padding:34px 20px; color:var(--muted); text-align:center; font-weight:800; }}
    .bench-toast {{
      position:fixed; z-index:999; right:22px; bottom:22px; width:min(330px,calc(100vw - 32px)); overflow:hidden;
      border:1px solid rgba(15,118,110,.24); border-radius:8px; background:rgba(255,253,250,.96); color:var(--text);
      box-shadow:0 18px 44px rgba(20,20,20,.12); animation:benchToastIn .18s ease-out forwards, benchToastOut .2s ease-in 1.9s forwards;
    }}
    .bench-toast-inner {{ display:grid; grid-template-columns:34px minmax(0,1fr); gap:10px; align-items:center; padding:13px 14px 12px; }}
    .bench-toast-icon {{ width:28px; height:28px; border-radius:999px; display:grid; place-items:center; color:#fff; background:var(--green); font-size:15px; font-weight:900; box-shadow:0 0 0 5px rgba(15,118,110,.1); }}
    .bench-toast-title {{ display:block; font-size:13px; font-weight:900; color:var(--text); }}
    .bench-toast-copy {{ display:block; margin-top:2px; color:var(--muted); font-size:12px; font-weight:700; }}
    .bench-toast-bar {{ height:2px; background:var(--green); transform-origin:left; animation:benchToastBar 2s linear forwards; }}
    @keyframes benchToastIn {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:translateY(0); }} }}
    @keyframes benchToastOut {{ to {{ opacity:0; transform:translateY(6px); }} }}
    @keyframes benchToastBar {{ from {{ transform:scaleX(1); }} to {{ transform:scaleX(0); }} }}
    .review-layout {{ display:grid; grid-template-columns:minmax(390px,.92fr) minmax(560px,1.35fr); gap:15px; align-items:start; }}
    .review-focus {{ max-width:1440px; }}
    .review-focus .hero {{ margin-bottom:16px; }}
    .review-focus .hero-title {{ max-width:760px; }}
    .review-focus .hero-copy {{ max-width:720px; }}
    .review-focus .review-toolbar {{ grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); padding:12px; margin-bottom:12px; }}
    .review-focus .review-layout {{ display:block; }}
    .review-poolbar {{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:16px; padding:12px 14px; border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.72); box-shadow:none; }}
    .review-nav-actions {{ display:flex; align-items:flex-end; gap:8px; justify-content:flex-end; flex-wrap:wrap; }}
    .review-case-picker {{ display:flex; align-items:center; gap:10px; margin-bottom:0; }}
    .review-pool-label {{ color:var(--muted); font-size:12px; font-weight:900; text-transform:uppercase; letter-spacing:0; }}
    .pool-count {{ display:inline-flex; align-items:center; min-height:42px; padding:9px 11px; border:1px solid var(--line); border-radius:999px; background:rgba(247,247,242,.74); color:var(--muted); font-size:12px; font-weight:850; white-space:nowrap; }}
    .review-stage {{ max-width:none; width:100%; margin:0; }}
    .review-context-line {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:10px; }}
    .review-column {{ min-width:0; }}
    .result-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin:0 0 9px; padding:0 2px; }}
    .result-heading h2 {{ margin:0; font-size:22px; }}
    .result-heading span {{ color:var(--muted); font-size:12px; font-weight:800; }}
    .review-list {{ max-height:calc(100vh - 120px); overflow:auto; padding:3px; }}
    .review-list {{ display:flex; flex-direction:column; gap:9px; }}
    .review-item {{
      position:relative; width:100%; text-align:left; color:var(--text); padding:15px 15px 15px 18px; cursor:pointer; box-shadow:none; background:rgba(255,253,250,.9);
      transition:border-color .18s ease, background .18s ease, color .18s ease;
    }}
    .review-item::before {{ content:''; position:absolute; left:-1px; top:10px; bottom:10px; width:3px; border-radius:999px; background:transparent; transition:background .18s ease; }}
    .review-item:hover {{ border-color:rgba(20,116,134,.36); transform:none; box-shadow:none; background:#fff; }}
    .review-item.active {{ border-color:rgba(157,37,44,.42); background:rgba(157,37,44,.06); color:var(--text); box-shadow:none; transform:none; }}
    .review-item.active .review-item-title {{ color:var(--text); }}
    .review-item.active .review-item-attack,.review-item.active .meta {{ color:#444; }}
    .review-item.active::before {{ top:8px; bottom:8px; background:var(--accent); }}
    .review-item-title {{ display:block; font-size:14px; font-weight:800; line-height:1.52; }}
    .review-item-attack {{
      display:-webkit-box; margin-top:8px; color:var(--muted); font-size:12px; line-height:1.55; font-weight:600;
      -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
    }}
    .review-tags {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }}
    .review-focus .review-item {{ padding:13px 13px 13px 16px; background:rgba(255,253,250,.86); }}
    .review-focus .review-item-title {{ font-size:13px; -webkit-line-clamp:3; display:-webkit-box; -webkit-box-orient:vertical; overflow:hidden; }}
    .review-focus .review-item-attack,.review-focus .review-item .meta,.review-focus .review-item .review-tags {{ display:none; }}
    .review-focus .rank-line {{ margin-top:8px; }}
    .review-focus .rank-badge {{ min-width:38px; padding:4px 7px; }}
    .pill {{ flex:none; border:1px solid var(--line); border-radius:999px; padding:4px 8px; font-size:11px; color:var(--muted); background:rgba(255,253,250,.72); font-weight:800; }}
    .pill.strong {{ color:var(--accent-strong); border-color:rgba(157,37,44,.28); background:var(--accent-soft); }}
    .pill.selected-mark {{ color:#0f5f59; border-color:rgba(15,118,110,.32); background:rgba(15,118,110,.1); }}
    .pill.decision-accepted {{ color:#0f5f59; border-color:rgba(15,118,110,.32); background:rgba(15,118,110,.1); }}
    .pill.decision-discarded {{ color:#9b2c22; border-color:rgba(180,35,24,.24); background:rgba(255,241,242,.9); }}
    .pill.decision-needs_discussion {{ color:#9a5b13; border-color:rgba(217,119,6,.26); background:rgba(255,251,235,.9); }}
    .rank-line {{ display:flex; align-items:center; gap:8px; margin:9px 0 0; }}
    .rank-badge {{ min-width:46px; display:inline-flex; align-items:center; justify-content:center; padding:5px 9px; border-radius:999px; background:var(--navy); color:#fff; font-size:12px; font-weight:900; }}
    .benchmark-action {{ width:100%; margin-top:15px; display:flex; justify-content:center; }}
    .benchmark-action button {{ width:100%; }}
    .benchmark-action .selected {{ background:rgba(255,255,255,.72); color:#0f5f59; border-color:rgba(15,118,110,.35); box-shadow:none; }}
    .detail-panel {{ position:sticky; top:82px; padding:22px; max-height:calc(100vh - 108px); overflow:auto; background:rgba(255,253,250,.9); border-top:2px solid rgba(20,116,134,.42); }}
    .detail-panel h2 {{ font-size:21px; line-height:1.38; margin:0 0 9px; }}
    .detail-empty {{ color:var(--muted); padding:42px 28px; text-align:center; background:var(--panel-soft); border:1px dashed var(--line-strong); border-radius:8px; font-weight:700; }}
    .review-focus .detail-panel {{ position:static; padding:0; background:transparent; border:0; box-shadow:none; max-height:none; overflow:visible; }}
    .focus-case {{ display:grid; gap:10px; }}
    .focus-card {{ border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.86); box-shadow:none; padding:18px; }}
    .focus-header {{ border-top:2px solid rgba(20,116,134,.48); background:rgba(255,253,250,.9); color:var(--text); }}
    .focus-title {{ margin:0; color:var(--text); font-size:22px; line-height:1.25; letter-spacing:0; font-weight:900; }}
    .focus-header .focus-title {{ color:var(--text); }}
    .focus-header .meta {{ color:var(--muted); }}
    .focus-meta {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:9px; }}
    .focus-header .review-edit-form {{ margin-top:14px; }}
    .focus-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .focus-block {{ border:1px solid var(--line); border-radius:8px; background:rgba(247,247,242,.74); padding:16px; }}
    .focus-block.full {{ grid-column:1 / -1; }}
    .focus-label {{ display:block; margin-bottom:7px; color:var(--accent-strong); font-size:10px; font-weight:900; letter-spacing:0; text-transform:uppercase; }}
    .focus-text {{ margin:0; color:var(--ink); font-size:15px; line-height:1.72; font-weight:650; }}
    .focus-attack {{ border-color:rgba(157,37,44,.22); background:rgba(255,248,248,.76); }}
    .focus-attack .focus-label {{ color:var(--accent); }}
    .review-edit-form {{ display:grid; gap:10px; }}
    .review-edit-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .review-edit-grid .full {{ grid-column:1 / -1; }}
    .review-edit-field {{ display:grid; gap:5px; }}
    .review-edit-field label {{ margin:0; color:var(--accent-strong); font-size:10px; font-weight:900; letter-spacing:0; text-transform:uppercase; }}
    .review-edit-field textarea {{ min-height:82px; background:rgba(255,253,250,.78); line-height:1.45; }}
    .review-edit-field.compact textarea {{ min-height:54px; }}
    .review-edit-field.tall textarea {{ min-height:98px; }}
    .review-edit-field.short textarea {{ min-height:66px; }}
    .review-edit-actions {{ display:flex; justify-content:space-between; align-items:center; gap:12px; padding-top:2px; flex-wrap:wrap; }}
    .review-edit-actions .meta {{ max-width:640px; }}
    .judgement-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .judgement {{ min-height:150px; border:1px solid var(--line); border-radius:8px; padding:16px 16px 14px; background:rgba(255,253,250,.86); box-shadow:none; }}
    .judgement.success {{ border-color:rgba(15,118,110,.26); background:rgba(247,255,251,.84); }}
    .judgement.failure {{ border-color:rgba(157,37,44,.24); background:rgba(255,248,248,.84); }}
    .judgement h3 {{ margin:0 0 10px; font-size:13px; letter-spacing:0; text-transform:uppercase; }}
    .judgement.success h3 {{ color:#0f5f59; }}
    .judgement.failure h3 {{ color:#9b2c22; }}
    .judgement ul,.metadata-list {{ margin:0; padding-left:19px; color:var(--ink); font-size:14px; line-height:1.65; }}
    .metadata-strip {{ display:flex; flex-wrap:wrap; gap:7px; }}
    .metadata-token {{ display:inline-flex; max-width:100%; padding:6px 9px; border:1px solid var(--line); border-radius:999px; background:rgba(255,253,250,.72); color:var(--muted); font-size:12px; font-weight:750; line-height:1.45; }}
    .decision-panel {{ display:grid; gap:12px; }}
    .decision-actions {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:9px; }}
    .decision-actions button {{ min-height:42px; }}
    .decision-actions .accept {{ background:var(--green); border-color:var(--green); }}
    .decision-actions .accept:hover {{ background:#0d6c66; border-color:#0d6c66; box-shadow:0 7px 18px rgba(15,118,110,.18); }}
    .decision-actions .discard {{ background:rgba(255,253,250,.72); color:var(--danger); border-color:rgba(180,35,24,.40); }}
    .decision-actions .discard:hover {{ background:rgba(255,241,242,.95); color:var(--danger); border-color:rgba(180,35,24,.58); box-shadow:0 7px 18px rgba(180,35,24,.12); }}
    .decision-actions .mark {{ background:rgba(255,253,250,.72); color:#9a5b13; border-color:rgba(217,119,6,.44); }}
    .decision-actions .mark:hover {{ background:rgba(255,251,235,.98); color:#8a4f0f; border-color:rgba(217,119,6,.62); box-shadow:0 7px 18px rgba(217,119,6,.12); }}
    .decision-actions .clear {{ background:rgba(255,253,250,.72); color:var(--muted); border-color:var(--line-strong); }}
    .decision-actions .clear:hover {{ background:#fff; color:var(--navy); border-color:rgba(20,116,134,.36); box-shadow:0 7px 18px rgba(20,116,134,.1); }}
    .button.danger, button.danger {{ background:rgba(255,253,250,.72); color:var(--danger); border-color:rgba(180,35,24,.34); box-shadow:0 1px 0 rgba(20,20,20,.06); }}
    .button.danger:hover, button.danger:hover {{ color:var(--danger); border-color:rgba(180,35,24,.58); background:rgba(255,241,242,.95); box-shadow:0 7px 18px rgba(180,35,24,.12); }}
    dl {{ margin:18px 0 0; display:grid; gap:12px; }}
    dt {{ font-size:10px; color:var(--accent-strong); font-weight:900; text-transform:uppercase; letter-spacing:0; margin:0; }}
    dd {{ margin:5px 0 0; font-size:13px; line-height:1.66; background:rgba(247,247,242,.72); border:1px solid var(--line); border-radius:8px; padding:11px 12px; }}
    dd ul {{ margin:0; padding-left:18px; }}
    @media (prefers-reduced-motion: reduce) {{
      .button,button {{ transition:background .12s ease, border-color .12s ease, color .12s ease, box-shadow .12s ease; }}
      button:hover,.button:hover,button:active,.button:active {{ transform:none; }}
    }}
    @media (max-width:980px) {{
      .grid,.design-grid,.design-grid.design-only,.toolbar,.review-layout,.choice-grid,.overview-grid,.overview-stats,.field-grid,.rank-head,.rank-row {{ grid-template-columns:1fr; max-width:none; }}
      header {{ width:100%; padding:10px 14px; align-items:flex-start; border-radius:0; flex-direction:column; }}
      main {{ padding:16px; }}
      .top-nav,.app-nav {{ width:100%; flex-wrap:wrap; }}
      .hero {{ grid-template-columns:1fr; padding-top:44px; }}
      .hero-title,.hero-copy {{ grid-column:1; grid-row:auto; max-width:none; }}
      .hero-title {{ font-size:34px; }}
      .hero.compact .hero-title {{ font-size:30px; }}
      .select-card-menu {{ max-height:42vh; }}
      .toolbar-actions {{ grid-column:auto; }} .detail-panel,.sticky-panel {{ position:static; max-height:none; }}
      .focus-header,.focus-grid,.judgement-grid,.review-focus .review-layout,.review-focus .review-toolbar,.review-poolbar,.review-case-picker,.decision-actions,.review-edit-grid {{ grid-template-columns:1fr; }}
      .review-nav-actions {{ justify-content:flex-start; }}
      .rank-head {{ display:none; }}
      .rank-actions {{ justify-content:flex-start; }}
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
        if not can_access_workspace():
            return redirect("/login")
        return menu_page(session["username"])

    @app.get("/design")
    def design():
        if not can_access_workspace():
            return redirect("/login")
        return design_page(session["username"])

    @app.get("/review")
    def review():
        if not can_access_workspace():
            return redirect("/login")
        return review_page(session["username"])

    @app.get("/scenes")
    def scenes():
        if not can_access_workspace():
            return redirect("/login")
        return scenes_page(session["username"])

    @app.get("/benchmark")
    def benchmark():
        if not can_access_workspace():
            return redirect("/login")
        return benchmark_page(session["username"])

    @app.get("/login")
    def login_page():
        return render_login()

    @app.post("/login")
    def login():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            account = authenticate(username, password)
        except ValueError:
            return render_login("账户配置错误，请联系管理员"), 500
        if not account:
            return render_login("账号或密码不正确"), 401
        session.clear()
        session["role"] = account.role
        session["username"] = account.username
        return redirect("/")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/admin")
    def admin():
        if not can_access_admin():
            return redirect("/admin/login")
        return admin_page(session["username"])

    @app.get("/admin/login")
    def admin_login_page():
        return render_admin_login()

    @app.post("/admin/login")
    def admin_login():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            account = authenticate(username, password)
        except ValueError:
            return render_admin_login("账户配置错误，请联系管理员"), 500
        if not account or account.role != "admin":
            return render_admin_login("管理员账号或密码不正确"), 401
        session.clear()
        session["role"] = account.role
        session["username"] = account.username
        return redirect("/admin")

    @app.get("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect("/admin/login")

    @app.get("/api/cases")
    def api_cases():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        username = session["username"]
        cases = [case for case in read_local_dataset(DEFAULT_DATASET) if case.get("owner") in (username, "llm_seed")]
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases})

    @app.post("/api/cases")
    def save_case():
        if not can_access_workspace():
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
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        cases = read_local_dataset(DEFAULT_DATASET)
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases})

    @app.get("/api/benchmark-cases")
    def api_benchmark_cases():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        cases = [case for case in read_local_dataset(DEFAULT_DATASET) if case.get("benchmark_selected")]
        cases.sort(key=lambda item: item.get("benchmark_selected_at") or item.get("expert_decision_at") or item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases})

    @app.post("/api/cases/<case_id>/reviews")
    def save_review(case_id: str):
        return jsonify({"error": "score reviews are disabled; use expert decisions instead"}), 410

    @app.post("/api/cases/<case_id>/expert-decision")
    def save_expert_decision(case_id: str):
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        try:
            saved = set_expert_decision(
                case_id,
                str(raw.get("decision", "")).strip(),
                decided_by=session["username"],
                comment=str(raw.get("comment", "")).strip(),
            )
        except KeyError:
            return jsonify({"error": "case not found"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({"case": saved})

    @app.patch("/api/cases/<case_id>/expert-edit")
    def save_expert_edit(case_id: str):
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        try:
            saved = update_case_fields(case_id, raw, edited_by=session["username"])
        except KeyError:
            return jsonify({"error": "case not found"}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({"case": saved})

    @app.post("/api/cases/<case_id>/benchmark-selection")
    def save_benchmark_selection(case_id: str):
        if not can_access_workspace():
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
        if not can_access_admin():
            return jsonify({"error": "admin login required"}), 401
        datasets = list_file_datasets() or [DEFAULT_DATASET]
        dataset = request.args.get("dataset") or (DEFAULT_DATASET if DEFAULT_DATASET in datasets else datasets[0])
        if dataset not in datasets:
            return jsonify({"error": "unknown dataset"}), 400
        cases = read_local_dataset(dataset)
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"dataset": dataset, "datasets": datasets, "cases": cases})

    return app


def render_login(error: str = "") -> str:
    error_html = f'<div class="errors">{error}</div>' if error else ""
    return page("ClawTrap 登录", f"""
<main class="login-main"><section class="login">
  <div class="brand-lockup" style="margin-bottom:18px">
    <div class="brand-mark">C</div>
    <div><h1>ClawTrap</h1><div class="brand-subtitle">Benchmark annotation workspace</div></div>
  </div>
  <div class="login-note">请输入已分配的账号 ID 和密码。未配置在账户表中的 ID 不能进入标注或审核工作台。</div>
  <form method="post" action="/login">
    <label>账号 ID</label><input name="username" required autocomplete="username" autofocus>
    <label>密码</label><input name="password" type="password" required autocomplete="current-password">
    {error_html}
    <div class="row form-actions"><button type="submit">进入工作台</button></div>
  </form>
</section></main>""")


def render_admin_login(error: str = "") -> str:
    error_html = f'<div class="errors">{error}</div>' if error else ""
    return page("ClawTrap 管理员登录", f"""
<main class="login-main"><section class="login">
  <div class="brand-lockup" style="margin-bottom:18px">
    <div class="brand-mark">C</div>
    <div><h1>ClawTrap</h1><div class="brand-subtitle">Administrator review console</div></div>
  </div>
  <div class="login-note">管理员入口只接受 role=admin 的账号。管理员账号也可以进入普通标注、审核和总览页面。</div>
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
    admin_link = '<a href="/admin">管理台</a>' if can_access_admin() else ""
    return f"""
<header>
  <div class="brand-lockup"><div class="brand-mark">C</div><div><h1>ClawTrap</h1><div class="brand-subtitle">{subtitle}</div></div></div>
  <div class="top-nav">
    <nav class="app-nav">
      <a class="{active_class('menu')}" href="/">菜单</a>
      <a class="{active_class('review')}" href="/review">审核</a>
      <a class="{active_class('scenes')}" href="/scenes">原始库</a>
      <a class="{active_class('benchmark')}" href="/benchmark">Benchmark</a>
      {admin_link}
    </nav>
    <span class="user-chip">{user}</span>
    <a class="button secondary" href="/logout">退出</a>
  </div>
</header>"""


def menu_page(user: str) -> str:
    role = session.get("role", "annotator")
    return page("ClawTrap 工作台", f"""
{app_header(user, "Benchmark annotation workspace", "menu")}
<main>
<section class="hero">
  <div class="eyebrow">Workspace</div>
  <h2 class="hero-title">ClawTrap 场景标注工作台</h2>
  <p class="hero-copy">当前账户：<strong>{user}</strong>。这里负责从本地 case 池中审阅、筛选并维护 ClawTrap Benchmark。</p>
</section>
<section class="overview-grid">
  <article class="overview-card">
    <p class="section-kicker">Account</p>
    <h2>当前标注员</h2>
  <p>账户名和当前工作空间会显示在每个页面顶部。审核裁决、Mark notes 和后续查询都会关联到当前账户。</p>
    <div class="account-row"><span class="pill strong">{user}</span><span class="pill">{role}</span></div>
  </article>
  <article class="overview-card">
    <p class="section-kicker">Dataset</p>
    <h2>数据概览</h2>
    <p>进入审核或检查页面前，可以先确认当前本地 case 池的大致规模。</p>
    <div class="overview-stats" id="menuStats">
      <div class="mini-stat"><strong>-</strong><span>全部场景</span></div>
      <div class="mini-stat"><strong>-</strong><span>待审核</span></div>
      <div class="mini-stat"><strong>-</strong><span>已选 benchmark</span></div>
    </div>
  </article>
</section>
<section class="choice-grid">
  <a class="choice-card" href="/review"><div class="choice-number">01</div><strong>审核</strong><span>逐条查看本地 case，执行保留、Discard、Mark notes 或 Skip。</span></a>
  <a class="choice-card" href="/scenes"><div class="choice-number">02</div><strong>检查原始数据库</strong><span>只读检查本地 JSON case 池的任务类型、攻击类型和字段完整性。</span></a>
  <a class="choice-card" href="/benchmark"><div class="choice-number">03</div><strong>检查 ClawTrap Bench</strong><span>查看当前已入选 benchmark 的场景集合、类型分布和详细内容。</span></a>
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
    const pending = cases.filter(item => !item.expert_decision).length;
    const selected = cases.filter(item => item.benchmark_selected).length;
    el.innerHTML = [
      stat(cases.length, '全部场景'),
      stat(pending, '待审核'),
      stat(selected, '已选 benchmark')
    ].join('');
  } catch (error) {
    el.innerHTML = [
      stat('-', '全部场景'),
      stat('-', '待审核'),
      stat('-', '已选 benchmark')
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
    readonly = request.args.get("mode") == "view"
    hero_title = "Benchmark 场景详情" if readonly else "逐条审阅本地场景，决定是否进入 Benchmark"
    hero_copy = "此页面只用于查看已入选 benchmark 的场景内容，不提供保留、Discard 或 Mark notes 操作。" if readonly else "当前审核只显示未完成处理或存疑的 case。保留进 Benchmark 或 Discard 后会自动进入下一条。"
    return page("ClawTrap 场景审核", f"""
{app_header(user, "Case review", "review")}
<main class="admin-main review-focus">
  <section class="hero compact">
    <div class="eyebrow">Review</div>
    <h2 class="hero-title">{hero_title}</h2>
    <p class="hero-copy">{hero_copy}</p>
  </section>
  <section class="panel toolbar review-toolbar">
    <div><label>搜索</label><input id="reviewSearch"></div>
    <div><label>裁决状态</label><div class="select-shell"><select id="reviewDecisionFilter"><option value="">全部</option><option value="none">未裁决</option><option value="needs_discussion">存疑 Mark</option></select></div></div>
    <div><label>任务类型</label><div class="select-shell"><select id="reviewTaskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>攻击类型</label><div class="select-shell"><select id="reviewAttackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>植入形式</label><div class="select-shell"><select id="reviewFormFilter"><option value="">全部</option>{options(INTERACTIVE_FORMS)}</select></div></div>
  </section>
  <section class="review-poolbar">
    <div class="review-case-picker">
      <span class="review-pool-label">当前待审核池</span>
      <span class="pool-count" id="reviewCount">-</span>
    </div>
    <div class="review-nav-actions">
      <button type="button" class="secondary" onclick="goReviewCase(-1)">上一条</button>
      <button type="button" onclick="goReviewCase(1)">下一条</button>
      <button type="button" class="secondary" onclick="loadReviewCases()">刷新</button>
    </div>
  </section>
  <section class="review-layout review-stage">
    <aside class="detail-panel" id="detailPanel"></aside>
  </section>
</main>
<script>window.CLAWTRAP_REVIEWER = {js_value(user)};</script>
<script>{review_js()}</script>""")


def scenes_page(user: str) -> str:
    return page("ClawTrap 原始数据库", f"""
{app_header(user, "Raw local database", "scenes")}
<main class="admin-main">
  <section class="hero compact">
    <div class="eyebrow">Raw Database</div>
    <h2 class="hero-title">检查本地 JSON 原始 case 池</h2>
    <p class="hero-copy">这里只读取本地数据文件，不区分云端与本地来源。用于快速检查原始 case 的类型、裁决状态和字段内容。</p>
  </section>
  <section class="panel toolbar">
    <div><label>Benchmark</label><div class="select-shell"><select id="selectedFilter"><option value="">全部</option><option value="selected">已选中</option><option value="unselected">未选中</option></select></div></div>
    <div><label>裁决状态</label><div class="select-shell"><select id="decisionFilter"><option value="">全部</option><option value="none">未裁决</option><option value="accepted">已保留</option><option value="discarded">Discard</option><option value="needs_discussion">存疑 Mark</option></select></div></div>
    <div><label>攻击类型</label><div class="select-shell"><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>任务类型</label><div class="select-shell"><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>搜索</label><input id="search"></div>
    <div class="row toolbar-actions"><button type="button" onclick="loadCases()">刷新</button></div>
  </section>
  <section class="rank-dashboard">
    <section class="rank-summary" id="stats"></section>
    <section class="rank-board">
      <div class="rank-head"><span>#</span><span>Case</span><span>Decision</span><span>Status</span><span></span></div>
      <div id="rankRows"></div>
    </section>
  </section>
</main>
<script>{scenes_js()}</script>""")


def benchmark_page(user: str) -> str:
    return page("ClawTrap Bench", f"""
{app_header(user, "ClawTrap Bench", "benchmark")}
<main class="admin-main">
  <section class="hero compact">
    <div class="eyebrow">Benchmark</div>
    <h2 class="hero-title">当前 ClawTrap Bench 入选集合</h2>
    <p class="hero-copy">这里专门展示已保留进 benchmark 的 case。审核页做裁决，这里检查最终集合的规模、类型分布和具体内容。</p>
  </section>
  <section class="panel toolbar">
    <div><label>攻击类型</label><div class="select-shell"><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>任务类型</label><div class="select-shell"><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>搜索</label><input id="search"></div>
    <div class="row toolbar-actions"><button type="button" onclick="loadCases()">刷新</button></div>
  </section>
  <section class="rank-dashboard">
    <section class="rank-summary" id="stats"></section>
    <section class="rank-board">
      <div class="rank-head"><span>#</span><span>Benchmark Case</span><span>Attack</span><span>Task</span><span></span></div>
      <div id="rankRows"></div>
    </section>
  </section>
</main>
<script>{benchmark_js()}</script>""")


def admin_page(admin: str) -> str:
    return page("ClawTrap 数据审阅", f"""
<header>
  <div class="brand-lockup"><div class="brand-mark">C</div><div><h1>ClawTrap</h1><div class="brand-subtitle">Benchmark data review</div></div></div>
  <div class="top-nav"><span class="meta">admin: {admin}</span><a class="button secondary" href="/admin/logout">退出</a></div>
</header>
<main class="admin-main">
  <section class="hero compact">
    <div class="eyebrow">Review Console</div>
    <h2 class="hero-title">Inspect local MITM benchmark cases.</h2>
    <p class="hero-copy">管理页保留数据集切换与完整字段查看，但不再显示评分排序或云端/本地来源区分。</p>
  </section>
  <section class="panel toolbar">
    <div><label>数据集</label><div class="select-shell"><select id="dataset"></select></div></div>
    <div><label>状态</label><div class="select-shell"><select id="statusFilter"><option value="">全部</option><option value="draft">draft</option><option value="submitted">submitted</option></select></div></div>
    <div><label>Benchmark</label><div class="select-shell"><select id="selectedFilter"><option value="">全部</option><option value="selected">已选中</option><option value="unselected">未选中</option></select></div></div>
    <div><label>裁决状态</label><div class="select-shell"><select id="decisionFilter"><option value="">全部</option><option value="none">未裁决</option><option value="accepted">已保留</option><option value="discarded">Discard</option><option value="needs_discussion">存疑 Mark</option></select></div></div>
    <div><label>攻击类型</label><div class="select-shell"><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>任务类型</label><div class="select-shell"><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>植入形式</label><div class="select-shell"><select id="formFilter"><option value="">全部</option>{options(INTERACTIVE_FORMS)}</select></div></div>
    <div><label>搜索</label><input id="search"></div>
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
  return `${decisionLabel(item.expert_decision)} · ${item.benchmark_selected ? '已入选 benchmark' : '未入选 benchmark'}`;
}
function applyRanks(items) {
  return [...items];
}
function decisionLabel(decision) {
  return ({accepted:'已保留', discarded:'Discard', needs_discussion:'存疑 Mark', clear:'未裁决'})[decision] || '未裁决';
}
function decisionPill(item) {
  const decision = item.expert_decision || '';
  if (!decision) return '<span class="pill">未裁决</span>';
  return `<span class="pill decision-${escapeHtml(decision)}">${escapeHtml(decisionLabel(decision))}</span>`;
}
function caseTags(item) {
  const selected = item.benchmark_selected ? '<span class="pill selected-mark">已选入 benchmark</span>' : '';
  return `${selected}${decisionPill(item)}<span class="pill strong">${escapeHtml(item.status || 'draft')}</span><span class="pill">${escapeHtml(item.task_type)}</span><span class="pill">${escapeHtml(item.attack_type)}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span>`;
}
function groupedCaseList(onClickName='selectCase') {
  return filteredCases.map((item, index) => `<button class="review-item ${item.id === selectedId ? 'active' : ''}" data-case-id="${escapeHtml(item.id)}" type="button" onclick="${onClickName}('${escapeAttr(item.id)}')"><span class="review-item-title">${escapeHtml(item.task || '(未命名任务)')}</span><span class="review-item-attack">${escapeHtml(item.attack_method || '')}</span><span class="meta">#${index + 1} · ${escapeHtml(summaryText(item))}</span><span class="review-tags">${caseTags(item)}</span></button>`).join('');
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
  return `<dl><dt>Attack Method</dt><dd>${escapeHtml(item.attack_method)}</dd><dt>Target</dt><dd>${escapeHtml(item.target)}</dd><dt>Success States</dt><dd>${listText(item.success_states)}</dd><dt>Failure States</dt><dd>${listText(item.failure_states)}</dd><dt>Metadata</dt><dd>${listText(item.metadata)}</dd><dt>Logic</dt><dd>${escapeHtml(item.logic)}</dd></dl>`;
}
function baseDetail(item) {
  return `<h2>${escapeHtml(item.task || '(未命名任务)')}</h2><div class="review-tags">${caseTags(item)}<span class="pill">${escapeHtml(summaryText(item))}</span></div>`;
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
  return `<span class="pill strong">${escapeHtml(item.task_type || '-')}</span><span class="pill">${escapeHtml(item.attack_type || '-')}</span><span class="pill">${escapeHtml((item.interactive_form || []).join(' / ') || '-')}</span>`;
}
function currentReviewer() {
  return window.CLAWTRAP_REVIEWER || '';
}
function lineText(items) {
  return Array.isArray(items) ? items.join('\n') : String(items || '');
}
function splitLines(value) {
  return String(value || '').split('\n').map(line => line.trim()).filter(Boolean);
}
function escapeTextarea(value) {
  return escapeHtml(value);
}
function editField(name, label, value, className='') {
  const readonly = typeof readOnlyReview !== 'undefined' && readOnlyReview;
  return `<div class="review-edit-field ${className}"><label>${escapeHtml(label)}</label><textarea name="${escapeAttr(name)}" required ${readonly ? 'readonly' : ''}>${escapeTextarea(value || '')}</textarea></div>`;
}
function focusedReviewDetail(item) {
  return `<div class="focus-case">
    <section class="focus-card focus-header">
      <div>
        <h2 class="focus-title">${escapeHtml(item.task || '(未命名任务)')}</h2>
        <div class="focus-meta">${compactTags(item)}</div>
      </div>
      <form id="expertEditForm" class="review-edit-form">
        <div class="review-edit-grid">
          ${editField('task', '用户任务 task', item.task, 'tall')}
          ${editField('target', '期望目标 target', item.target, 'tall')}
          ${editField('attack_method', 'MITM 攻击植入 attack_method', item.attack_method)}
          ${editField('logic', '攻击逻辑 logic', item.logic)}
          ${editField('success_states', '成功判定 success_states（每行一条）', lineText(item.success_states), 'short')}
          ${editField('failure_states', '失败判定 failure_states（每行一条）', lineText(item.failure_states), 'short')}
          ${editField('metadata', '实现提示 metadata（每行一条）', lineText(item.metadata), 'full compact')}
        </div>
        <div class="errors" id="editErrors"></div>
        <div class="review-edit-actions" ${typeof readOnlyReview !== 'undefined' && readOnlyReview ? 'style="display:none"' : ''}>
          <span class="meta">修改会保存到当前 case；直接执行保留、Discard 或 Mark notes 时也会先自动保存。</span>
          <button type="button" onclick="saveExpertEdit()">保存修改</button>
        </div>
      </form>
    </section>
  </div>`;
}
function expertDecisionPanel(item) {
  return `<section class="focus-card decision-panel">
    <div class="section-heading"><div><p class="section-kicker">Expert Decision</p><h2>专家裁决</h2></div><span>${decisionPill(item)}</span></div>
    <textarea id="decisionComment" placeholder="Mark notes 或裁决备注。保留和 Discard 可不填；Mark notes 建议写明需要其他人确认的点。">${escapeTextarea(item.expert_decision_comment || '')}</textarea>
    <div class="errors" id="decisionErrors"></div>
    <div class="decision-actions">
      <button type="button" class="accept" onclick="submitDecision('accepted')">保留进 Benchmark</button>
      <button type="button" class="discard" onclick="submitDecision('discarded')">Discard</button>
      <button type="button" class="mark" onclick="submitDecision('needs_discussion')">Mark notes</button>
      <button type="button" class="clear" onclick="skipCase()">Skip</button>
    </div>
  </section>`;
}
function listText(items) { return Array.isArray(items) ? `<ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : escapeHtml(items || ''); }
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
function escapeAttr(value) { return String(value ?? '').replace(/[\'\\]/g, ch => ch === '\\' ? '\\\\' : "\\'"); }
"""


def review_js() -> str:
    return shared_case_js() + r"""
const reviewParams = new URLSearchParams(window.location.search);
const reviewMode = reviewParams.get('mode') || 'review';
const requestedCaseId = reviewParams.get('case');
const readOnlyReview = reviewMode === 'view';
async function loadReviewCases() {
  const res = await fetch('/api/all-cases');
  const data = await res.json();
  allCases = data.cases || [];
  if (readOnlyReview) {
    document.querySelector('.review-toolbar')?.remove();
    document.querySelector('.review-poolbar')?.remove();
    filteredCases = requestedCaseId ? allCases.filter(item => item.id === requestedCaseId) : [];
    selectedId = filteredCases[0]?.id || null;
    renderDetail();
    return;
  }
  if (requestedCaseId && allCases.some(item => item.id === requestedCaseId)) selectedId = requestedCaseId;
  filterReviewCases();
}
function filterReviewCases() {
  const q = (document.getElementById('reviewSearch')?.value || '').trim().toLowerCase();
  const decision = document.getElementById('reviewDecisionFilter')?.value || '';
  const attack = document.getElementById('reviewAttackFilter')?.value || '';
  const task = document.getElementById('reviewTaskFilter')?.value || '';
  const form = document.getElementById('reviewFormFilter')?.value || '';
  filteredCases = allCases.filter(item => isReviewCandidate(item) && matchesDecisionStatus(item, decision) && (!attack || item.attack_type === attack) && (!task || item.task_type === task) && (!form || (item.interactive_form || []).includes(form)) && (!q || JSON.stringify(item).toLowerCase().includes(q)));
  if (!filteredCases.some(item => item.id === selectedId)) selectedId = filteredCases[0]?.id || null;
  renderReviewPicker();
  renderDetail();
}
function isReviewCandidate(item) {
  if (item.benchmark_selected) return false;
  return !['accepted', 'discarded'].includes(item.expert_decision || '');
}
function matchesDecisionStatus(item, decision) {
  if (!decision) return true;
  if (decision === 'none') return !item.expert_decision;
  return item.expert_decision === decision;
}
function renderReviewPicker() {
  const count = document.getElementById('reviewCount');
  const index = filteredCases.findIndex(item => item.id === selectedId);
  if (count) count.textContent = filteredCases.length ? `${index + 1} / ${filteredCases.length}` : '0 / 0';
}
function selectCase(id) { selectedId = id; renderReviewPicker(); renderDetail(); }
function goReviewCase(delta) {
  if (!filteredCases.length) return;
  const index = Math.max(0, filteredCases.findIndex(item => item.id === selectedId));
  const nextIndex = (index + delta + filteredCases.length) % filteredCases.length;
  selectedId = filteredCases[nextIndex].id;
  renderReviewPicker();
  renderDetail();
}
function renderDetail() {
  const panel = document.getElementById('detailPanel');
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  if (!item) { panel.innerHTML = `<div class="detail-empty">${readOnlyReview ? '没有找到对应场景' : '当前筛选池没有可审核场景'}</div>`; return; }
  panel.innerHTML = `${focusedReviewDetail(item)}
    ${readOnlyReview ? '' : expertDecisionPanel(item)}`;
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
function mergeUpdatedCase(updated) {
  const index = allCases.findIndex(item => item.id === updated.id);
  if (index >= 0) allCases[index] = updated;
  selectedId = updated.id;
}
async function submitDecision(decision) {
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  const currentIndex = Math.max(0, filteredCases.findIndex(candidate => candidate.id === selectedId));
  const nextCandidate = filteredCases.length > 1 ? filteredCases[(currentIndex + 1) % filteredCases.length] : null;
  const errorEl = document.getElementById('decisionErrors');
  if (!item) return;
  if (errorEl) errorEl.textContent = '';
  const scrollTop = window.scrollY;
  const scrollLeft = window.scrollX;
  const editSaved = await saveCurrentEdit({rerender:false});
  if (!editSaved) return;
  const comment = document.getElementById('decisionComment')?.value || '';
  const res = await fetch(`/api/cases/${encodeURIComponent(item.id)}/expert-decision`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({decision, comment})});
  const data = await res.json();
  if (!res.ok) {
    if (errorEl) errorEl.textContent = (data.errors || [data.error || '裁决失败']).join('\n');
    return;
  }
  if (decision === 'accepted') showBenchmarkAnimation();
  const index = allCases.findIndex(candidate => candidate.id === data.case.id);
  if (index >= 0) allCases[index] = data.case;
  selectedId = nextCandidate?.id || data.case.id;
  filterReviewCases();
  requestAnimationFrame(() => window.scrollTo({top: scrollTop, left: scrollLeft, behavior: 'auto'}));
}
function skipCase() {
  goReviewCase(1);
}
function showBenchmarkAnimation() {
  const node = document.createElement('div');
  document.querySelectorAll('.bench-toast').forEach(item => item.remove());
  node.className = 'bench-toast';
  node.innerHTML = `<div class="bench-toast-inner"><span class="bench-toast-icon">✓</span><span><strong class="bench-toast-title">已加入 ClawTrap Bench</strong><span class="bench-toast-copy">正在进入下一条审核</span></span></div><div class="bench-toast-bar"></div>`;
  document.body.appendChild(node);
  window.setTimeout(() => node.remove(), 2300);
}
async function saveExpertEdit() {
  await saveCurrentEdit({rerender:true});
}
async function saveCurrentEdit({rerender=true} = {}) {
  const item = filteredCases.find(candidate => candidate.id === selectedId);
  const form = document.getElementById('expertEditForm');
  const errorEl = document.getElementById('editErrors');
  if (!item || !form) return false;
  if (errorEl) errorEl.textContent = '';
  const payload = Object.fromEntries(new FormData(form).entries());
  payload.success_states = splitLines(form.success_states.value);
  payload.failure_states = splitLines(form.failure_states.value);
  payload.metadata = splitLines(form.metadata.value);
  const res = await fetch(`/api/cases/${encodeURIComponent(item.id)}/expert-edit`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const data = await res.json();
  if (!res.ok) {
    if (errorEl) errorEl.textContent = (data.errors || [data.error || '保存修改失败']).join('\n');
    return false;
  }
  mergeUpdatedCase(data.case);
  if (rerender) filterReviewCases();
  return true;
}
document.getElementById('reviewSearch')?.addEventListener('input', filterReviewCases);
document.getElementById('reviewDecisionFilter')?.addEventListener('input', filterReviewCases);
document.getElementById('reviewAttackFilter')?.addEventListener('input', filterReviewCases);
document.getElementById('reviewTaskFilter')?.addEventListener('input', filterReviewCases);
document.getElementById('reviewFormFilter')?.addEventListener('input', filterReviewCases);
loadReviewCases();
"""


def scenes_js() -> str:
    return shared_case_js() + r"""
const controls = ['selectedFilter','decisionFilter','attackFilter','taskFilter','search'].map(id => document.getElementById(id));
async function loadCases() {
  const res = await fetch('/api/all-cases');
  const data = await res.json();
  allCases = data.cases || [];
  render();
}
function render() {
  const selected = document.getElementById('selectedFilter').value;
  const decision = document.getElementById('decisionFilter').value;
  const attack = document.getElementById('attackFilter').value;
  const task = document.getElementById('taskFilter').value;
  const q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = allCases.filter(item =>
    (!selected || (selected === 'selected') === Boolean(item.benchmark_selected)) &&
    matchesDecision(item, decision) &&
    (!attack || item.attack_type === attack) &&
    (!task || item.task_type === task) &&
    (!q || [item.id, item.owner, item.task].join(' ').toLowerCase().includes(q))
  );
  renderStats();
  renderRankRows();
}
function matchesDecision(item, decision) {
  if (!decision) return true;
  if (decision === 'none') return !item.expert_decision;
  return item.expert_decision === decision;
}
function renderStats() {
  document.getElementById('stats').innerHTML = [
    stat('当前筛选', filteredCases.length),
    stat('已选 benchmark', filteredCases.filter(c => c.benchmark_selected).length),
    stat('已保留', filteredCases.filter(c => c.expert_decision === 'accepted').length),
    stat('Discard', filteredCases.filter(c => c.expert_decision === 'discarded').length),
    stat('存疑', filteredCases.filter(c => c.expert_decision === 'needs_discussion').length),
    stat('未裁决', filteredCases.filter(c => !c.expert_decision).length)
  ].join('');
}
function stat(label, value) { return `<article class="stat"><strong>${value}</strong><span>${escapeHtml(label)}</span></article>`; }
function renderRankRows() {
  const rows = document.getElementById('rankRows');
  if (!filteredCases.length) {
    rows.innerHTML = '<div class="rank-empty">没有匹配的数据</div>';
    return;
  }
  rows.innerHTML = filteredCases.map((item, index) => rankRow(item, index)).join('');
}
function overviewTags(item) {
  const selected = item.benchmark_selected ? '<span class="pill selected-mark">已选入 benchmark</span>' : '';
  return `${selected}<span class="pill strong">${escapeHtml(item.task_type || '-')}</span><span class="pill">${escapeHtml(item.attack_type || '-')}</span>`;
}
function rankRow(item, index) {
  return `<article class="rank-row">
    <div class="rank-index">#${index + 1}</div>
    <div>
      <span class="rank-case-title">${escapeHtml(item.task || '(未命名任务)')}</span>
      <div class="rank-case-meta">${overviewTags(item)}</div>
    </div>
    <div>${decisionPill(item)}</div>
    <div><span class="pill">${escapeHtml(item.status || 'draft')}</span></div>
    <div class="rank-actions"><a class="button secondary" href="/review?case=${encodeURIComponent(item.id)}">去审核</a></div>
  </article>`;
}
controls.forEach(el => el.addEventListener('input', render));
loadCases();
"""


def benchmark_js() -> str:
    return shared_case_js() + r"""
const controls = ['attackFilter','taskFilter','search'].map(id => document.getElementById(id));
async function loadCases() {
  const res = await fetch('/api/benchmark-cases');
  const data = await res.json();
  allCases = data.cases || [];
  render();
}
function render() {
  const attack = document.getElementById('attackFilter').value;
  const task = document.getElementById('taskFilter').value;
  const q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = allCases.filter(item =>
    (!attack || item.attack_type === attack) &&
    (!task || item.task_type === task) &&
    (!q || [item.id, item.owner, item.task].join(' ').toLowerCase().includes(q))
  );
  renderStats();
  renderRows();
}
function renderStats() {
  document.getElementById('stats').innerHTML = [
    stat('当前筛选', filteredCases.length),
    stat('全部入选', allCases.length),
    stat('攻击类型数', new Set(filteredCases.map(c => c.attack_type || '')).size),
    stat('任务类型数', new Set(filteredCases.map(c => c.task_type || '')).size)
  ].join('');
}
function stat(label, value) { return `<article class="stat"><strong>${value}</strong><span>${escapeHtml(label)}</span></article>`; }
function renderRows() {
  const rows = document.getElementById('rankRows');
  if (!filteredCases.length) {
    rows.innerHTML = '<div class="rank-empty">当前筛选下没有已入选 benchmark 的 case</div>';
    return;
  }
  rows.innerHTML = filteredCases.map((item, index) => `<article class="rank-row">
    <div class="rank-index">#${index + 1}</div>
    <div>
      <span class="rank-case-title">${escapeHtml(item.task || '(未命名任务)')}</span>
      <div class="rank-case-meta"><span class="pill selected-mark">已选入 benchmark</span><span class="pill">${escapeHtml(item.id || '')}</span></div>
    </div>
    <div><span class="pill">${escapeHtml(item.attack_type || '-')}</span></div>
    <div><span class="pill strong">${escapeHtml(item.task_type || '-')}</span></div>
    <div class="rank-actions"><a class="button secondary" href="/review?mode=view&case=${encodeURIComponent(item.id)}">查看</a><button type="button" class="danger" onclick="removeFromBenchmark('${escapeAttr(item.id)}')">移除</button></div>
  </article>`).join('');
}
async function removeFromBenchmark(id) {
  const item = allCases.find(candidate => candidate.id === id);
  const ok = window.confirm(`确认从 ClawTrap Bench 移除这条 case？\n\n${item?.task || id}`);
  if (!ok) return;
  try {
    await toggleBenchmarkSelection(id, false);
    allCases = allCases.filter(candidate => candidate.id !== id);
    render();
  } catch (error) {
    window.alert(error.message || '移除失败');
  }
}
controls.forEach(el => el.addEventListener('input', render));
loadCases();
"""


def admin_js() -> str:
    return r"""
let allCases = []; let filteredCases = []; let selectedId = null;
const dataset = document.getElementById('dataset');
const controls = ['statusFilter','selectedFilter','decisionFilter','attackFilter','taskFilter','formFilter','search'].map(id => document.getElementById(id));
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
  const status = document.getElementById('statusFilter').value, selected = document.getElementById('selectedFilter').value, decision = document.getElementById('decisionFilter').value, attack = document.getElementById('attackFilter').value, task = document.getElementById('taskFilter').value, form = document.getElementById('formFilter').value, q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = allCases.filter(item => (!status || item.status === status) && (!selected || (selected === 'selected') === Boolean(item.benchmark_selected)) && matchesDecision(item, decision) && (!attack || item.attack_type === attack) && (!task || item.task_type === task) && (!form || (item.interactive_form || []).includes(form)) && (!q || JSON.stringify(item).toLowerCase().includes(q)));
  filteredCases.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
  renderStats(); renderList(); renderDetail();
}
function matchesDecision(item, decision) {
  if (!decision) return true;
  if (decision === 'none') return !item.expert_decision;
  return item.expert_decision === decision;
}
function renderStats() {
  document.getElementById('stats').innerHTML = [
    stat('当前筛选', filteredCases.length), stat('全部数据', allCases.length),
    stat('已选 benchmark', filteredCases.filter(c => c.benchmark_selected).length),
    stat('已保留', filteredCases.filter(c => c.expert_decision === 'accepted').length),
    stat('Discard', filteredCases.filter(c => c.expert_decision === 'discarded').length),
    stat('存疑', filteredCases.filter(c => c.expert_decision === 'needs_discussion').length),
    stat('submitted', filteredCases.filter(c => c.status === 'submitted').length),
    stat('draft', filteredCases.filter(c => c.status === 'draft').length)
  ].join('');
}
function stat(label, value) { return `<article class="stat"><strong>${value}</strong><span>${escapeHtml(label)}</span></article>`; }
function decisionLabel(decision) {
  return ({accepted:'已保留', discarded:'Discard', needs_discussion:'存疑 Mark', clear:'未裁决'})[decision] || '未裁决';
}
function decisionPill(item) {
  const decision = item.expert_decision || '';
  if (!decision) return '<span class="pill">未裁决</span>';
  return `<span class="pill decision-${escapeHtml(decision)}">${escapeHtml(decisionLabel(decision))}</span>`;
}
function adminTags(item) {
  const selected = item.benchmark_selected ? '<span class="pill selected-mark">已选入 benchmark</span>' : '';
  return `${selected}${decisionPill(item)}<span class="pill strong">${escapeHtml(item.status || 'draft')}</span><span class="pill">${escapeHtml(item.task_type)}</span><span class="pill">${escapeHtml(item.attack_type)}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span>`;
}
function renderList() {
  if (!filteredCases.some(item => item.id === selectedId)) selectedId = filteredCases[0]?.id || null;
  const countEl = document.getElementById('resultCount');
  if (countEl) countEl.textContent = `${filteredCases.length} 条`;
  const list = document.getElementById('reviewList');
  list.innerHTML = filteredCases.map((item, index) => `<button class="review-item ${item.id === selectedId ? 'active' : ''}" data-case-id="${escapeHtml(item.id)}" type="button" onclick="selectCase('${escapeAttr(item.id)}')"><span class="review-item-title">${escapeHtml(item.task || '(未命名任务)')}</span><span class="review-item-attack">${escapeHtml(item.attack_method || '')}</span><span class="rank-line"><span class="rank-badge">#${index + 1}</span><span class="pill">${escapeHtml(decisionLabel(item.expert_decision))}</span></span><span class="review-tags">${adminTags(item)}</span></button>`).join('') || '<div class="detail-empty">没有匹配的数据</div>';
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
  panel.innerHTML = `<h2>${escapeHtml(item.task || '(未命名任务)')}</h2><div class="review-tags">${adminTags(item)}</div>${benchmarkButton(item)}<dl><dt>Attack Method</dt><dd>${escapeHtml(item.attack_method)}</dd><dt>Success States</dt><dd>${listText(item.success_states)}</dd><dt>Failure States</dt><dd>${listText(item.failure_states)}</dd><dt>Metadata</dt><dd>${listText(item.metadata)}</dd><dt>Target</dt><dd>${escapeHtml(item.target)}</dd><dt>Logic</dt><dd>${escapeHtml(item.logic)}</dd></dl>`;
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
