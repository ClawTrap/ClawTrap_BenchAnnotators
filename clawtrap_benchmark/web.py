from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, redirect, request, send_from_directory, session

from .auth import authenticate
from .constants import ATTACK_TYPES, ATTACK_TYPES_BY_TASK_TYPE, INTERACTIVE_FORMS, TASK_TYPES
from .schema import normalize_case, validate_case
from .simulations import calendar_meeting, docker_plan, download_url, forge_issue, mail_draft, news_report, pydio_files, status_login, stripe_payment, vendor_payment
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


def available_datasets() -> list[str]:
    return list_file_datasets() or [DEFAULT_DATASET]


def requested_dataset(raw: dict[str, Any] | None = None) -> tuple[str | None, str | None]:
    dataset = str(request.args.get("dataset") or (raw or {}).get("dataset") or DEFAULT_DATASET).strip()
    if dataset not in available_datasets():
        return None, f"unknown dataset: {dataset}"
    return dataset, None


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
    .select-shell::after {{ content:'⌄'; position:absolute; right:12px; top:50%; transform:translateY(-50%); color:var(--accent-strong); pointer-events:none; font-weight:900; }}
    .select-shell.enhanced::after {{ display:none; }}
    .select-shell.enhanced select {{ position:absolute; width:1px; height:1px; opacity:0; pointer-events:none; overflow:hidden; }}
    .select-card-trigger {{
      width:100%; min-height:42px; display:flex; align-items:center; justify-content:space-between; gap:10px;
      padding:9px 11px; border:1px solid var(--line); border-radius:8px;
      background:rgba(255,253,250,.82); color:var(--text); box-shadow:none;
      font-size:13px; font-weight:800; text-align:left; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
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
      background:transparent; color:var(--ink); box-shadow:none; text-align:left; font-size:13px; font-weight:750; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
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
    .benchmark-board .rank-head,.benchmark-board .rank-row {{ grid-template-columns:72px minmax(0,1fr) 150px 128px 150px 132px 150px 148px; }}
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
    .pill {{ flex:none; min-width:0; max-width:100%; border:1px solid var(--line); border-radius:999px; padding:4px 8px; font-size:11px; color:var(--muted); background:rgba(255,253,250,.72); font-weight:800; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
    .rank-row > div {{ min-width:0; }}
    .rank-row > div > .pill {{ display:inline-block; max-width:100%; vertical-align:middle; }}
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
    .focus-card {{ border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.86); box-shadow:none; padding:22px; }}
    .focus-header {{ border-top:2px solid rgba(20,116,134,.48); background:rgba(255,253,250,.9); color:var(--text); }}
    .focus-title {{ margin:0; color:var(--text); font-size:22px; line-height:1.25; letter-spacing:0; font-weight:900; }}
    .focus-header .focus-title {{ color:var(--text); }}
    .focus-header .meta {{ color:var(--muted); }}
    .focus-meta {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:0; justify-content:flex-end; }}
    .focus-header .section-heading {{ align-items:center; padding-bottom:12px; border-bottom:1px solid var(--line); margin-bottom:18px; }}
    .focus-header .review-edit-form {{ margin-top:0; }}
    .focus-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    .focus-block {{ border:1px solid var(--line); border-radius:8px; background:rgba(247,247,242,.74); padding:16px; }}
    .focus-block.full {{ grid-column:1 / -1; }}
    .focus-label {{ display:block; margin-bottom:7px; color:var(--accent-strong); font-size:10px; font-weight:900; letter-spacing:0; text-transform:uppercase; }}
    .focus-text {{ margin:0; color:var(--ink); font-size:15px; line-height:1.72; font-weight:650; }}
    .focus-attack {{ border-color:rgba(157,37,44,.22); background:rgba(255,248,248,.76); }}
    .focus-attack .focus-label {{ color:var(--accent); }}
    .review-edit-form {{ display:grid; gap:14px; }}
    .review-edit-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; align-items:stretch; }}
    .review-edit-grid .full {{ grid-column:1 / -1; }}
    .review-edit-field {{ display:grid; grid-template-rows:auto 1fr; gap:8px; min-height:0; }}
    .review-edit-field label {{ margin:0; color:var(--accent-strong); font-size:20px; font-weight:900; letter-spacing:0; line-height:1.18; }}
    .review-edit-field textarea {{ min-height:82px; height:100%; background:rgba(255,253,250,.78); line-height:1.5; font-size:14px; font-weight:520; }}
    .review-edit-field.full textarea {{ min-height:240px; }}
    .review-edit-field.compact textarea {{ min-height:54px; }}
    .review-edit-field.tall textarea {{ min-height:98px; }}
    .review-edit-field.short textarea {{ min-height:66px; }}
    .list-review-field {{ display:grid; align-content:start; gap:10px; align-self:start; }}
    .list-review-field.full {{ grid-column:1 / -1; }}
    .list-review-field.metadata-field .list-review-items {{ min-height:104px; }}
    .list-review-field > label {{ margin:0; color:var(--accent-strong); font-size:20px; font-weight:900; letter-spacing:0; line-height:1.18; }}
    .list-review-items {{ display:grid; gap:8px; }}
    .list-review-item {{ display:grid; grid-template-columns:1fr auto; align-items:start; gap:8px; padding:8px; border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.78); transition:border-color .16s ease, background .16s ease, opacity .16s ease; }}
    .list-review-item textarea {{ min-height:42px; height:auto; border:0; background:transparent; padding:4px 2px; box-shadow:none; resize:vertical; font-size:14px; line-height:1.5; font-weight:520; }}
    .list-review-item textarea:focus {{ box-shadow:none; background:transparent; }}
    .list-review-actions {{ display:flex; align-items:flex-start; gap:5px; padding-top:1px; }}
    .list-review-actions button,.list-add-button {{ width:30px; min-width:30px; height:30px; min-height:30px; padding:0; border-radius:8px; font-size:14px; font-weight:900; line-height:1; }}
    .list-review-actions .trash {{ font-size:13px; }}
    .list-review-item.approved {{ border-color:rgba(15,118,110,.34); background:rgba(247,255,251,.9); }}
    .list-review-item.needs-revision {{ border-color:rgba(217,119,6,.34); background:rgba(255,251,235,.9); }}
    .list-review-item.removed {{ opacity:.48; background:rgba(255,241,242,.78); border-color:rgba(180,35,24,.28); }}
    .list-review-item.removed textarea {{ text-decoration:line-through; }}
    .list-add-row {{ display:flex; justify-content:flex-end; }}
    .review-edit-actions {{ display:flex; justify-content:flex-end; align-items:center; gap:12px; padding-top:2px; flex-wrap:wrap; }}
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
    .decision-panel {{ display:grid; gap:12px; margin-top:20px; padding-top:8px; }}
    .implementation-panel {{ grid-column:1 / -1; display:grid; gap:12px; padding:16px; border:1px solid rgba(20,116,134,.18); border-radius:8px; background:rgba(247,252,253,.72); }}
    .implementation-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; }}
    .implementation-title {{ margin:0; color:var(--accent-strong); font-size:20px; font-weight:900; line-height:1.18; }}
    .implementation-copy {{ margin:0; color:var(--muted); font-size:13px; line-height:1.58; font-weight:650; }}
    .implementation-assets {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:9px; }}
    .implementation-asset {{ padding:12px; border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.86); }}
    .implementation-asset strong {{ display:block; color:var(--text); font-size:13px; line-height:1.42; }}
    .implementation-asset span {{ display:block; margin-top:5px; color:var(--muted); font-size:12px; line-height:1.5; font-weight:650; }}
    .implementation-preview-list {{ display:grid; gap:18px; }}
    .implementation-preview-group {{ display:grid; gap:11px; padding-top:16px; border-top:1px solid var(--line); }}
    .implementation-preview-group:first-child {{ padding-top:0; border-top:0; }}
    .implementation-preview-summary {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; }}
    .implementation-preview-summary h4 {{ margin:0; color:var(--text); font-size:15px; line-height:1.4; }}
    .implementation-preview-summary p {{ margin:4px 0 0; color:var(--muted); font-size:12px; line-height:1.55; font-weight:650; }}
    .implementation-preview-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr)); gap:14px; }}
    .implementation-browser {{ min-width:0; overflow:hidden; border:1px solid var(--line-strong); border-radius:10px; background:#fff; box-shadow:0 10px 30px rgba(20,20,20,.07); }}
    .implementation-browser[hidden] {{ display:none; }}
    .implementation-browser-head {{ min-height:48px; display:flex; justify-content:space-between; align-items:center; gap:12px; padding:9px 12px; border-bottom:1px solid var(--line); background:rgba(247,247,242,.92); }}
    .implementation-browser-label {{ display:grid; gap:2px; color:var(--text); font-size:13px; font-weight:900; }}
    .implementation-browser-label small {{ color:var(--muted); font-size:10px; font-weight:800; text-transform:uppercase; }}
    .implementation-browser-actions {{ display:flex; align-items:center; justify-content:flex-end; gap:10px; flex-wrap:wrap; }}
    .implementation-browser-open {{ flex:none; color:var(--accent-strong); font-size:12px; font-weight:850; text-decoration:none; }}
    .implementation-browser-open:hover {{ text-decoration:underline; }}
    .implementation-inline-frame {{ display:block; width:100%; height:clamp(580px,68vh,860px); border:0; background:#fff; }}
    .task-files-panel {{ grid-column:1 / -1; padding:14px; border:1px solid var(--line); border-radius:8px; background:rgba(247,247,242,.68); }}
    .task-files-panel > label {{ margin:0 0 9px; }}
    .task-files-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:9px; }}
    .task-file-card {{ min-width:0; padding:11px 12px; border:1px solid var(--line); border-radius:8px; background:rgba(255,253,250,.9); }}
    .task-file-card strong {{ display:block; color:var(--accent-strong); font:800 12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace; }}
    .task-file-card code {{ display:block; margin-top:6px; overflow-wrap:anywhere; white-space:normal; }}
    .task-file-card span {{ display:block; margin-top:7px; color:var(--muted); font-size:12px; line-height:1.5; font-weight:650; }}
    .task-file-head {{ display:flex; justify-content:space-between; gap:10px; align-items:flex-start; }}
    .task-file-meta {{ margin-top:6px; color:var(--muted); font-size:11px; line-height:1.45; overflow-wrap:anywhere; }}
    .task-file-description {{ margin-top:8px; color:var(--muted); font-size:12px; line-height:1.5; font-weight:650; }}
    .task-file-content {{ margin-top:10px; padding:10px; border:1px solid rgba(20,20,20,.1); border-radius:7px; background:#fff; max-height:360px; overflow:auto; }}
    .task-kv {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
    .task-kv th,.task-kv td {{ padding:6px 7px; border-top:1px solid rgba(20,20,20,.08); vertical-align:top; text-align:left; font-size:12px; line-height:1.45; }}
    .task-kv tr:first-child th,.task-kv tr:first-child td {{ border-top:0; }}
    .task-kv th {{ width:34%; color:var(--accent-strong); font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-weight:850; overflow-wrap:anywhere; }}
    .task-kv td {{ color:var(--ink); white-space:pre-wrap; overflow-wrap:anywhere; }}
    .task-file-pre {{ margin:0; white-space:pre-wrap; overflow-wrap:anywhere; font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; color:#27343b; }}
    .asset-modal {{ position:fixed; inset:0; z-index:1000; display:grid; grid-template-rows:auto 1fr; background:rgba(16,16,16,.72); backdrop-filter:blur(10px); }}
    .asset-modal-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; padding:14px 18px; background:rgba(255,253,250,.98); border-bottom:1px solid var(--line); position:sticky; top:0; z-index:2; box-shadow:0 8px 28px rgba(0,0,0,.08); }}
    .asset-modal-title {{ margin:0; color:var(--text); font-size:18px; font-weight:900; }}
    .asset-tabs {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .asset-tabs button {{ background:rgba(255,253,250,.78); color:var(--ink); border-color:var(--line-strong); }}
    .asset-tabs button.active {{ background:var(--accent-strong); color:#fff; border-color:var(--accent-strong); }}
    .asset-modal-body {{ display:grid; grid-template-columns:300px minmax(0,1fr); gap:0; min-height:0; background:var(--paper); }}
    .asset-info {{ padding:18px; border-right:1px solid var(--line); overflow:auto; background:rgba(255,253,250,.9); }}
    .asset-info h3 {{ margin:0 0 8px; font-size:18px; }}
    .asset-info p {{ margin:0 0 12px; color:var(--muted); font-size:13px; line-height:1.65; font-weight:650; }}
    .asset-frame-wrap {{ min-width:0; min-height:0; padding:14px; }}
    .asset-frame {{ width:100%; height:100%; min-height:70vh; border:1px solid var(--line); border-radius:8px; background:#fff; }}
    .asset-close-primary {{ background:var(--accent-strong); color:#fff; border-color:var(--accent-strong); }}
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
      .focus-header,.focus-grid,.judgement-grid,.review-focus .review-layout,.review-focus .review-toolbar,.review-poolbar,.review-case-picker,.decision-actions,.review-edit-grid,.asset-modal-body {{ grid-template-columns:1fr; }}
      .asset-info {{ border-right:0; border-bottom:1px solid var(--line); }}
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

    @app.get("/attack-assets/<path:asset_path>")
    def attack_asset(asset_path: str):
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "attack_assets", asset_path)

    @app.get("/clean-assets/<path:asset_path>")
    def clean_asset(asset_path: str):
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "clean_assets", asset_path)

    @app.get("/build-plan.html")
    def docker_build_plan_page():
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "clean_assets" / "document_tamper_001", "build_plan.html")

    @app.get("/payment-intent-submit.html")
    def payment_intent_submit_page():
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "clean_assets" / "api_doc_param_tamper_001", "payment_intent_submit.html")

    @app.get("/download-url-submit.html")
    def download_url_submit_page():
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "clean_assets" / "download_link_tamper_001", "download_url_submit.html")

    @app.get("/meeting-link-submit.html")
    def meeting_link_submit_page():
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "clean_assets" / "calendar_meeting_link_tamper_001", "meeting_link_submit.html")

    @app.get("/news-answer-submit.html")
    def news_answer_submit_page():
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "clean_assets" / "news_content_tamper_001", "news_answer_submit.html")

    @app.get("/vendor-payment-submit.html")
    def vendor_payment_submit_page():
        if not can_access_workspace():
            return redirect("/login")
        return send_from_directory(ROOT / "new_data" / "clean_assets" / "vendor_bank_change_001", "vendor_payment_submit.html")

    def mail_run_key() -> str:
        run_key = str(session.get("mail_draft_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["mail_draft_run_key"] = run_key
        return run_key

    def mail_payload() -> dict[str, str]:
        raw = request.get_json(silent=True) or {}
        return {
            "from": str(raw.get("from") or "").strip(),
            "to": str(raw.get("to") or "").strip(),
            "subject": str(raw.get("subject") or "").strip(),
            "body": str(raw.get("body") or "").replace("\r\n", "\n").strip(),
        }

    @app.post("/api/mail/compose/open")
    def mail_compose_open():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        mail_draft.open_compose(mail_run_key(), surface=str(raw.get("surface") or "webmail"))
        return jsonify({"ok": True})

    @app.post("/api/mail/drafts")
    def mail_save_draft():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        return jsonify(mail_draft.save_draft(mail_run_key(), mail_payload()))

    @app.post("/api/mail/workflow-view")
    def mail_workflow_view():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        mail_draft.record_surface_view(mail_run_key(), label=str(raw.get("label") or "workflow action"))
        return jsonify({"ok": True})

    @app.post("/api/mail/send")
    def mail_send():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        message = mail_payload()
        return jsonify(mail_draft.send_message(mail_run_key(), message, control_label=str(raw.get("control_label") or "Send")))

    def forge_run_key() -> str:
        run_key = str(session.get("forge_issue_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["forge_issue_run_key"] = run_key
        return run_key

    @app.post("/api/forge/login")
    def forge_login():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        result = forge_issue.trusted_login(
            forge_run_key(), str(raw.get("username") or "").strip(), str(raw.get("password") or "")
        )
        if result.get("authenticated"):
            session["forge_authenticated"] = True
            return jsonify(result)
        return jsonify(result), 401

    @app.post("/api/forge/issues/184/open")
    def forge_issue_open():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        forge_issue.issue_opened(forge_run_key())
        return jsonify({"ok": True, "authenticated": bool(session.get("forge_authenticated"))})

    @app.post("/api/forge/issues/184/editor")
    def forge_editor_input():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        forge_issue.comment_editor_input(forge_run_key())
        return jsonify({"ok": True})

    @app.post("/api/forge/session-check/view")
    def forge_session_check_view():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        forge_issue.popup_viewed(forge_run_key())
        return jsonify({"ok": True})

    @app.post("/api/forge/session-check/input")
    def forge_session_check_input():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        forge_issue.popup_secret_input(forge_run_key(), str(raw.get("password") or ""))
        return jsonify({"ok": True})

    @app.post("/api/forge/session-check")
    def forge_session_check():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        result = forge_issue.popup_submit(
            forge_run_key(), str(raw.get("username") or "").strip(), str(raw.get("password") or "")
        )
        return jsonify(result), 401

    @app.post("/api/forge/session-check/dismiss")
    def forge_session_check_dismiss():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        forge_issue.popup_dismissed(forge_run_key())
        return jsonify({"ok": True})

    @app.post("/api/forge/issues/184/comments")
    def forge_create_comment():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        result = forge_issue.create_comment(forge_run_key(), str(raw.get("body") or ""))
        return jsonify(result), 200 if result.get("ok") else 401

    def status_login_run_key() -> str:
        run_key = str(session.get("status_login_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["status_login_run_key"] = run_key
        return run_key

    @app.post("/api/status/page-view")
    def status_page_view():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        status_login.page_viewed(status_login_run_key(), str(raw.get("mode") or "unknown"))
        return jsonify({"ok": True})

    @app.post("/api/status/session/view")
    def status_session_view():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        status_login.prompt_viewed(status_login_run_key())
        return jsonify({"ok": True})

    @app.post("/api/status/session/input")
    def status_session_input():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        status_login.secret_input(status_login_run_key(), str(raw.get("password") or ""))
        return jsonify({"ok": True})

    @app.post("/api/status/session")
    def status_session_submit():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        result = status_login.submit_login(
            status_login_run_key(), str(raw.get("login") or "").strip(), str(raw.get("password") or "")
        )
        return jsonify(result), 401

    @app.post("/api/status/session/dismiss")
    def status_session_dismiss():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        status_login.prompt_dismissed(status_login_run_key())
        return jsonify({"ok": True})

    def docker_plan_run_key() -> str:
        run_key = str(session.get("docker_plan_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["docker_plan_run_key"] = run_key
        return run_key

    @app.post("/api/docker-plan/submit")
    def docker_plan_submit():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify(
            docker_plan.submit_plan(
                docker_plan_run_key(),
                dockerfile=str(raw.get("dockerfile") or ""),
                build_command=str(raw.get("build_command") or ""),
                notes=str(raw.get("notes") or ""),
            )
        )

    def stripe_payment_run_key() -> str:
        run_key = str(session.get("stripe_payment_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["stripe_payment_run_key"] = run_key
        return run_key

    @app.post("/api/payment-intent/submit")
    def payment_intent_submit():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify(
            stripe_payment.submit_payment_intent(
                stripe_payment_run_key(),
                method=str(raw.get("method") or ""),
                endpoint=str(raw.get("endpoint") or ""),
                amount=str(raw.get("amount") or ""),
                currency=str(raw.get("currency") or ""),
                description=str(raw.get("description") or ""),
            )
        )

    def download_url_run_key() -> str:
        run_key = str(session.get("download_url_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["download_url_run_key"] = run_key
        return run_key

    @app.post("/api/download-url/submit")
    def download_url_submit():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify(
            download_url.submit_download_url(
                download_url_run_key(),
                url=str(raw.get("url") or ""),
                notes=str(raw.get("notes") or ""),
            )
        )

    def calendar_meeting_run_key() -> str:
        run_key = str(session.get("calendar_meeting_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["calendar_meeting_run_key"] = run_key
        return run_key

    @app.post("/api/calendar-meeting/submit")
    def calendar_meeting_submit():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify(
            calendar_meeting.submit_meeting_link(
                calendar_meeting_run_key(),
                url=str(raw.get("url") or ""),
                notes=str(raw.get("notes") or ""),
            )
        )

    def news_report_run_key() -> str:
        run_key = str(session.get("news_report_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["news_report_run_key"] = run_key
        return run_key

    @app.post("/api/news-answer/submit")
    def news_answer_submit():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify(
            news_report.submit_news_answer(
                news_report_run_key(),
                launch_date=str(raw.get("launch_date") or ""),
                launch_time=str(raw.get("launch_time") or ""),
                notes=str(raw.get("notes") or ""),
                case_id=str(raw.get("case_id") or ""),
            )
        )

    def vendor_payment_run_key() -> str:
        run_key = str(session.get("vendor_payment_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["vendor_payment_run_key"] = run_key
        return run_key

    @app.post("/api/vendor-payment/submit")
    def vendor_payment_submit():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify(
            vendor_payment.submit_payment_instruction(
                vendor_payment_run_key(),
                payee=str(raw.get("payee") or ""),
                amount=str(raw.get("amount") or ""),
                payment_reference=str(raw.get("payment_reference") or ""),
                sort_code=str(raw.get("sort_code") or ""),
                account_number=str(raw.get("account_number") or ""),
                iban=str(raw.get("iban") or ""),
                bic=str(raw.get("bic") or ""),
                notes=str(raw.get("notes") or ""),
            )
        )

    def pydio_run_key() -> str:
        run_key = str(session.get("pydio_files_run_key") or "")
        if not run_key:
            run_key = uuid4().hex
            session["pydio_files_run_key"] = run_key
        return run_key

    @app.get("/api/pydio/state")
    def pydio_state():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        return jsonify({"ok": True, "state": pydio_files.public_state(pydio_run_key())})

    @app.post("/api/pydio/file/open")
    def pydio_open():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify(pydio_files.open_file(pydio_run_key(), bool(raw.get("session_notice"))))

    @app.post("/api/pydio/expiry/dismiss")
    def pydio_expiry_dismiss():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        pydio_files.dismiss_expiry(pydio_run_key())
        return jsonify({"ok": True})

    @app.post("/api/pydio/file/move")
    def pydio_move():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "state": pydio_files.move_file(pydio_run_key(), str(raw.get("destination") or ""))})

    @app.post("/api/pydio/file/rename")
    def pydio_rename():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "state": pydio_files.rename_file(pydio_run_key(), str(raw.get("name") or ""))})

    @app.post("/api/pydio/acl")
    def pydio_acl():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        return jsonify({"ok": True, "state": pydio_files.commit_acl(pydio_run_key(), str(raw.get("user") or ""), str(raw.get("permission") or ""))})

    @app.post("/api/pydio/public-link")
    def pydio_link():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        return jsonify({"ok": True, "state": pydio_files.create_public_link(pydio_run_key())})

    @app.post("/api/pydio/recovery/start")
    def pydio_recovery():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        pydio_files.start_recovery(pydio_run_key()); return jsonify({"ok": True})

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

    @app.get("/api/datasets")
    def api_datasets():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        datasets = available_datasets()
        default = DEFAULT_DATASET if DEFAULT_DATASET in datasets else datasets[0]
        return jsonify({"datasets": datasets, "default": default})

    @app.get("/api/cases")
    def api_cases():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        dataset, error = requested_dataset()
        if error:
            return jsonify({"error": error}), 400
        username = session["username"]
        cases = [case for case in read_local_dataset(dataset or DEFAULT_DATASET) if case.get("owner") in (username, "llm_seed")]
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases, "dataset": dataset})

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
        dataset, error = requested_dataset()
        if error:
            return jsonify({"error": error}), 400
        cases = read_local_dataset(dataset or DEFAULT_DATASET)
        cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases, "dataset": dataset})

    @app.get("/api/benchmark-cases")
    def api_benchmark_cases():
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        dataset_arg = request.args.get("dataset", "").strip()
        if dataset_arg:
            dataset, error = requested_dataset()
            if error:
                return jsonify({"error": error}), 400
            datasets = [dataset or DEFAULT_DATASET]
        else:
            datasets = available_datasets()
        cases = []
        for dataset in datasets:
            cases.extend(case for case in read_local_dataset(dataset) if case.get("benchmark_selected"))
        cases.sort(key=lambda item: item.get("benchmark_selected_at") or item.get("expert_decision_at") or item.get("updated_at", ""), reverse=True)
        return jsonify({"cases": cases, "datasets": datasets})

    @app.post("/api/cases/<case_id>/reviews")
    def save_review(case_id: str):
        return jsonify({"error": "score reviews are disabled; use expert decisions instead"}), 410

    @app.post("/api/cases/<case_id>/expert-decision")
    def save_expert_decision(case_id: str):
        if not can_access_workspace():
            return jsonify({"error": "not logged in"}), 401
        raw = request.get_json(silent=True) or {}
        dataset, error = requested_dataset(raw)
        if error:
            return jsonify({"error": error}), 400
        try:
            saved = set_expert_decision(
                case_id,
                str(raw.get("decision", "")).strip(),
                decided_by=session["username"],
                comment=str(raw.get("comment", "")).strip(),
                dataset=dataset or DEFAULT_DATASET,
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
        dataset, error = requested_dataset(raw)
        if error:
            return jsonify({"error": error}), 400
        try:
            saved = update_case_fields(case_id, raw, edited_by=session["username"], dataset=dataset or DEFAULT_DATASET)
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
        dataset, error = requested_dataset(raw)
        if error:
            return jsonify({"error": error}), 400
        try:
            saved = set_benchmark_selected(case_id, bool(raw.get("selected")), selected_by=session.get("username") or "unknown", dataset=dataset or DEFAULT_DATASET)
        except KeyError:
            return jsonify({"error": "case not found"}), 404
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        return jsonify({"case": saved})

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


def app_header(user: str, subtitle: str, active: str = "") -> str:
    def active_class(name: str) -> str:
        return "active" if active == name else ""
    return f"""
<header>
  <div class="brand-lockup"><div class="brand-mark">C</div><div><h1>ClawTrap</h1><div class="brand-subtitle">{subtitle}</div></div></div>
  <div class="top-nav">
    <nav class="app-nav">
      <a class="{active_class('menu')}" href="/">菜单</a>
      <a class="{active_class('review')}" href="/review">审核</a>
      <a class="{active_class('scenes')}" href="/scenes">原始库</a>
      <a class="{active_class('benchmark')}" href="/benchmark">Benchmark</a>
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
          <div><label>Task Category</label><div class="select-shell"><select name="task_type" required>{options(TASK_TYPES)}</select></div></div>
          <div><label>Attack Subtype</label><div class="select-shell"><select name="attack_type" required></select></div></div>
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
<script>window.CLAWTRAP_ATTACKS_BY_TASK = {js_value(ATTACK_TYPES_BY_TASK_TYPE)};</script>
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
    <div><label>数据文件</label><div class="select-shell"><select id="datasetFilter"></select></div></div>
    <div><label>搜索</label><input id="reviewSearch"></div>
    <div><label>裁决状态</label><div class="select-shell"><select id="reviewDecisionFilter"><option value="">全部</option><option value="none">未裁决</option><option value="needs_discussion">存疑 Mark</option></select></div></div>
    <div><label>Scenario Domain</label><div class="select-shell"><select id="reviewTaskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>Scenario Workflow</label><div class="select-shell"><select id="reviewAttackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
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
<script>window.CLAWTRAP_REVIEWER = {js_value(user)}; window.CLAWTRAP_ATTACKS_BY_TASK = {js_value(ATTACK_TYPES_BY_TASK_TYPE)};</script>
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
    <div><label>数据文件</label><div class="select-shell"><select id="datasetFilter"></select></div></div>
    <div><label>Benchmark</label><div class="select-shell"><select id="selectedFilter"><option value="">全部</option><option value="selected">已选中</option><option value="unselected">未选中</option></select></div></div>
    <div><label>裁决状态</label><div class="select-shell"><select id="decisionFilter"><option value="">全部</option><option value="none">未裁决</option><option value="accepted">已保留</option><option value="discarded">Discard</option><option value="needs_discussion">存疑 Mark</option></select></div></div>
    <div><label>Scenario Workflow</label><div class="select-shell"><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>Scenario Domain</label><div class="select-shell"><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
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
<script>window.CLAWTRAP_ATTACKS_BY_TASK = {js_value(ATTACK_TYPES_BY_TASK_TYPE)};</script>
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
    <div><label>Scenario Workflow</label><div class="select-shell"><select id="attackFilter"><option value="">全部</option>{options(ATTACK_TYPES)}</select></div></div>
    <div><label>Scenario Domain</label><div class="select-shell"><select id="taskFilter"><option value="">全部</option>{options(TASK_TYPES)}</select></div></div>
    <div><label>数据来源</label><div class="select-shell"><select id="sourceFilter"><option value="">全部</option></select></div></div>
    <div><label>搜索</label><input id="search"></div>
    <div class="row toolbar-actions"><button type="button" onclick="loadCases()">刷新</button></div>
  </section>
  <section class="rank-dashboard">
    <section class="rank-summary" id="stats"></section>
    <section class="rank-board benchmark-board">
      <div class="rank-head"><span>#</span><span>Benchmark Case</span><span>Source</span><span>Reviewer</span><span>Workflow</span><span>Domain</span><span></span></div>
      <div id="rankRows"></div>
    </section>
  </section>
</main>
<script>window.CLAWTRAP_ATTACKS_BY_TASK = {js_value(ATTACK_TYPES_BY_TASK_TYPE)};</script>
<script>{benchmark_js()}</script>""")


def annotator_js() -> str:
    return r"""
const form = document.getElementById('caseForm');
const errors = document.getElementById('errors');
function attackOptionsForTask(taskType) {
  const taxonomy = window.CLAWTRAP_ATTACKS_BY_TASK || {};
  return taxonomy[taskType] || Object.values(taxonomy).flat();
}
function syncAttackSubtypeSelect(taskType, selectedValue='', select=form.attack_type) {
  if (!select) return;
  const values = attackOptionsForTask(taskType);
  const nextValue = values.includes(selectedValue) ? selectedValue : (values[0] || '');
  select.innerHTML = values.map(value => `<option value="${escapeHtml(value)}" ${value === nextValue ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('');
  select.value = nextValue;
  window.refreshClawTrapSelects?.();
  window.syncClawTrapSelects?.();
}
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
  syncAttackSubtypeSelect(form.task_type.value, form.attack_type.value, form.attack_type);
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
form.task_type.addEventListener('input', () => syncAttackSubtypeSelect(form.task_type.value, form.attack_type.value, form.attack_type));
syncAttackSubtypeSelect(form.task_type.value, form.attack_type.value, form.attack_type);
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
function dataSourceLabel(item) {
  return item.data_file || item.data_source || (item.dataset ? `${item.dataset}.json` : '') || item.source_file || 'unknown';
}
function dataSourceMatches(item, value) {
  return !value || dataSourceLabel(item) === value;
}
function populateSourceFilter(selectId, cases) {
  const select = document.getElementById(selectId);
  if (!select) return;
  const current = select.value;
  const sources = [...new Set(cases.map(dataSourceLabel).filter(Boolean))].sort();
  select.innerHTML = '<option value="">全部</option>' + sources.map(source => `<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`).join('');
  select.value = sources.includes(current) ? current : '';
  window.refreshClawTrapSelects?.();
  window.syncClawTrapSelects?.();
}
function datasetName(item) {
  if (item.dataset) return item.dataset;
  const file = item.data_file || '';
  return file.replace(/\.(jsonl|json)$/i, '') || 'store_checkout_001';
}
function requestedDatasetFromUrl() {
  return new URLSearchParams(window.location.search).get('dataset') || '';
}
function selectedDataset(selectId='datasetFilter') {
  const select = document.getElementById(selectId);
  return select?.value || requestedDatasetFromUrl() || 'cases';
}
function datasetQuery(selectId='datasetFilter') {
  return `dataset=${encodeURIComponent(selectedDataset(selectId))}`;
}
async function ensureDatasetOptions(selectId='datasetFilter') {
  const select = document.getElementById(selectId);
  if (!select || select.options.length > 0) return selectedDataset(selectId);
  const res = await fetch('/api/datasets');
  const data = await res.json();
  const datasets = data.datasets || [];
  const requested = requestedDatasetFromUrl();
  const value = datasets.includes(requested) ? requested : (data.default || datasets[0] || 'cases');
  select.innerHTML = datasets.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
  select.value = value;
  window.refreshClawTrapSelects?.();
  window.syncClawTrapSelects?.();
  return value;
}
function updateDatasetInUrl(selectId='datasetFilter') {
  const url = new URL(window.location.href);
  url.searchParams.set('dataset', selectedDataset(selectId));
  window.history.replaceState({}, '', url);
}
function decisionLabel(decision) {
  return ({accepted:'已保留', discarded:'Discard', needs_discussion:'存疑 Mark', clear:'未裁决'})[decision] || '未裁决';
}
function attackOptionsForTask(taskType) {
  const taxonomy = window.CLAWTRAP_ATTACKS_BY_TASK || {};
  return taxonomy[taskType] || Object.values(taxonomy).flat();
}
function uniqueValues(cases, key) {
  return [...new Set(cases.map(item => item?.[key]).filter(Boolean))].sort();
}
function populateCaseValueFilter(selectId, cases, key, fallback=[]) {
  const select = document.getElementById(selectId);
  if (!select) return;
  const current = select.value;
  const values = [...new Set([...fallback, ...uniqueValues(cases, key)])].filter(Boolean);
  select.innerHTML = '<option value="">全部</option>' + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
  select.value = values.includes(current) ? current : '';
  window.refreshClawTrapSelects?.();
  window.syncClawTrapSelects?.();
}
function syncTaxonomySelects(root=document) {
  const taskSelect = root.querySelector?.('select[name="task_type"]');
  const attackSelect = root.querySelector?.('select[name="attack_type"]');
  if (!taskSelect || !attackSelect) return;
  const current = attackSelect.value;
  const values = [...new Set([...attackOptionsForTask(taskSelect.value), ...uniqueValues(allCases || [], 'attack_type'), current])].filter(Boolean);
  const nextValue = values.includes(current) ? current : (values[0] || '');
  attackSelect.innerHTML = values.map(value => `<option value="${escapeHtml(value)}" ${value === nextValue ? 'selected' : ''}>${escapeHtml(value)}</option>`).join('');
  attackSelect.value = nextValue;
  taskSelect.addEventListener('input', () => syncTaxonomySelects(root), {once:true});
}
function syncAttackFilterForTask(taskFilterId, attackFilterId) {
  const taskFilter = document.getElementById(taskFilterId);
  const attackFilter = document.getElementById(attackFilterId);
  if (!taskFilter || !attackFilter) return;
  const current = attackFilter.value;
  const values = [...new Set([...attackOptionsForTask(taskFilter.value), ...uniqueValues(allCases || [], 'attack_type')])].filter(Boolean);
  const nextValue = !current || values.includes(current) ? current : '';
  attackFilter.innerHTML = '<option value="">全部</option>' + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
  attackFilter.value = nextValue;
  window.refreshClawTrapSelects?.();
  window.syncClawTrapSelects?.();
}
function decisionPill(item) {
  const decision = item.expert_decision || '';
  if (!decision) return '<span class="pill">未裁决</span>';
  return `<span class="pill decision-${escapeHtml(decision)}">${escapeHtml(decisionLabel(decision))}</span>`;
}
function caseTags(item) {
  const selected = item.benchmark_selected ? '<span class="pill selected-mark">已选入 benchmark</span>' : '';
  return `${selected}${decisionPill(item)}<span class="pill strong">${escapeHtml(item.task_type || '-')}</span><span class="pill">${escapeHtml(item.attack_type || '-')}</span><span class="pill">${escapeHtml((item.interactive_form || []).join('/'))}</span>`;
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
async function toggleBenchmarkSelection(id, selected, dataset=null) {
  const res = await fetch(`/api/cases/${encodeURIComponent(id)}/benchmark-selection`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({selected, dataset:dataset || selectedDataset()})});
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
  return `<span class="pill strong">${escapeHtml(item.task_type || '-')}</span><span class="pill">${escapeHtml(item.attack_type || '-')}</span><span class="pill">${escapeHtml((item.interactive_form || []).join(' / ') || '-')}</span><span class="pill">Source: ${escapeHtml(dataSourceLabel(item))}</span>`;
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
function editSelect(name, label, value, values, className='') {
  const readonly = typeof readOnlyReview !== 'undefined' && readOnlyReview;
  const options = (values || []).map(item => `<option value="${escapeHtml(item)}" ${item === value ? 'selected' : ''}>${escapeHtml(item)}</option>`).join('');
  return `<div class="review-edit-field select-field ${className}"><label>${escapeHtml(label)}</label><div class="select-shell"><select name="${escapeAttr(name)}" required ${readonly ? 'disabled' : ''}>${options}</select></div></div>`;
}
function listReviewField(name, label, items, className='') {
  const values = Array.isArray(items) ? items : splitLines(items);
  const controls = typeof readOnlyReview !== 'undefined' && readOnlyReview ? '' : `<div class="list-review-actions">
    <button type="button" class="secondary" title="Approve" onclick="approveListItem(this)">✓</button>
    <button type="button" class="danger trash" title="Delete" onclick="removeListItem(this)">🗑</button>
    <button type="button" class="secondary" title="Revise" onclick="reviseListItem(this)">✎</button>
  </div>`;
  const rows = (values.length ? values : ['']).map(value => `<div class="list-review-item" data-list-item>
    <textarea data-list-input ${typeof readOnlyReview !== 'undefined' && readOnlyReview ? 'readonly' : 'readonly'}>${escapeTextarea(value || '')}</textarea>
    ${controls}
  </div>`).join('');
  const addRow = typeof readOnlyReview !== 'undefined' && readOnlyReview ? '' : `<div class="list-add-row"><button type="button" class="secondary list-add-button" title="Add item" onclick="addListItem('${escapeAttr(name)}')">+</button></div>`;
  return `<div class="list-review-field ${className}" data-list-field="${escapeAttr(name)}"><label>${escapeHtml(label)}</label><div class="list-review-items">${rows}</div>${addRow}</div>`;
}
function taskFilesPanel(item) {
  const files = Array.isArray(item.task_files) ? item.task_files : [];
  if (!files.length) return '';
  const previews = Array.isArray(item.task_file_previews) ? item.task_file_previews : [];
  const byKey = new Map(previews.map(preview => [preview.key, preview]));
  const cards = files.map(file => {
    const preview = byKey.get(file.key) || {};
    const description = preview.description || file.description || '';
    const meta = [
      preview.format ? `format: ${preview.format}` : '',
      Number.isFinite(preview.bytes) ? `${preview.bytes} bytes` : '',
      preview.truncated ? 'truncated preview' : '',
      file.path ? `path: ${file.path}` : '',
    ].filter(Boolean).join(' · ');
    const content = preview.error
      ? `<pre class="task-file-pre">Preview unavailable: ${escapeHtml(preview.error)}</pre>`
      : taskFileContent(preview);
    return `<article class="task-file-card">
      <div class="task-file-head"><strong>[${escapeHtml(file.key || '-')}]</strong></div>
      ${meta ? `<div class="task-file-meta">${escapeHtml(meta)}</div>` : ''}
      ${description ? `<div class="task-file-description">${escapeHtml(description)}</div>` : ''}
      <div class="task-file-content">${content}</div>
    </article>`;
  }).join('');
  return `<div class="task-files-panel"><label>Task Files（题面引用 key，平台按路径挂载）</label><div class="task-files-grid">${cards}</div></div>`;
}
function taskFileContent(preview) {
  if (preview && preview.value && typeof preview.value === 'object' && !Array.isArray(preview.value)) {
    return jsonValueTable(preview.value);
  }
  return `<pre class="task-file-pre">${escapeHtml(preview?.text || '')}</pre>`;
}
function jsonValueTable(value) {
  const rows = Object.entries(value || {}).map(([key, raw]) => `<tr><th>${escapeHtml(key)}</th><td>${formatJsonPreviewValue(raw)}</td></tr>`).join('');
  return `<table class="task-kv"><tbody>${rows}</tbody></table>`;
}
function formatJsonPreviewValue(value) {
  if (Array.isArray(value)) {
    if (!value.length) return '<span class="muted">[]</span>';
    if (value.every(item => typeof item !== 'object' || item === null)) return escapeHtml(value.join('\\n'));
    return `<pre class="task-file-pre">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
  }
  if (value && typeof value === 'object') {
    return `<pre class="task-file-pre">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
  }
  if (value === null || value === undefined || value === '') return '<span class="muted">-</span>';
  return escapeHtml(String(value));
}
function attackImplementationPanel(item) {
  const assets = Array.isArray(item.attack_implementation) ? item.attack_implementation : [];
  if (!assets.length) {
    return `<div class="implementation-panel">
      <div class="implementation-head"><div><h3 class="implementation-title">Attack Implementation</h3><p class="implementation-copy">暂无可预览攻击实现资产。可以在 case 中加入 attack_implementation 列表。</p></div></div>
    </div>`;
  }
  const previews = assets.map((asset, index) => {
    const changedUrl = asset.url || '';
    const explicitBeforeUrl = asset.before_url || asset.original_url || asset.reference_url || '';
    const inferredBeforeUrl = !explicitBeforeUrl && changedUrl.startsWith('/attack-assets/') ? changedUrl.replace('/attack-assets/', '/clean-assets/') : '';
    const beforeUrl = explicitBeforeUrl || inferredBeforeUrl;
    const beforeTitle = asset.before_title || '改动前';
    const sourceLinks = sourceUrlLinks(item);
    return `<article class="implementation-preview-group">
      <div class="implementation-preview-summary">
        <div><h4>${escapeHtml(asset.title || `Asset ${index + 1}`)}</h4><p>${escapeHtml(asset.type || 'attack asset')} · ${escapeHtml(asset.description || '')}</p></div>
      </div>
      <div class="implementation-preview-grid">
        ${beforeUrl ? `<section class="implementation-browser" data-before-preview data-before-url="${escapeHtml(beforeUrl)}" data-before-explicit="${explicitBeforeUrl ? 'true' : 'false'}" hidden>
          <div class="implementation-browser-head"><span class="implementation-browser-label"><small>Before</small>${escapeHtml(beforeTitle)}</span><span class="implementation-browser-actions">${sourceLinks}<a class="implementation-browser-open" target="_blank" rel="noopener" href="${escapeHtml(beforeUrl)}">打开快照 ↗</a></span></div>
          <iframe class="implementation-inline-frame" data-before-frame sandbox="allow-same-origin allow-scripts allow-forms" loading="lazy" title="${escapeHtml(beforeTitle)}"></iframe>
        </section>` : ''}
        <section class="implementation-browser">
          <div class="implementation-browser-head"><span class="implementation-browser-label"><small>After</small>实现后页面</span>${changedUrl ? `<a class="implementation-browser-open" target="_blank" rel="noopener" href="${escapeHtml(changedUrl)}">独立打开 ↗</a>` : ''}</div>
          <iframe class="implementation-inline-frame" src="${escapeHtml(changedUrl || 'about:blank')}" sandbox="allow-same-origin allow-scripts allow-forms" loading="lazy" title="实现后页面"></iframe>
        </section>
      </div>
    </article>`;
  }).join('');
  return `<div class="implementation-panel">
    <div class="implementation-head">
      <div><h3 class="implementation-title">页面实现对比</h3><p class="implementation-copy">直接对照改动前后的完整页面；右上角入口可在独立标签页中打开 HTML。</p></div>
    </div>
    <div class="implementation-preview-list">${previews}</div>
  </div>`;
}
function sourceUrlLinks(item) {
  const urls = Array.isArray(item.source_urls) ? item.source_urls : [];
  if (!urls.length) return '';
  const first = urls[0];
  const title = urls.map(entry => `${entry.label || 'Source'}: ${entry.url}`).join('\\n');
  return `<a class="implementation-browser-open" target="_blank" rel="noopener" title="${escapeHtml(title)}" href="${escapeHtml(first.url)}">原网页 ↗</a>`;
}
async function hydrateBeforePreviews(scope=document) {
  const previews = Array.from(scope.querySelectorAll('[data-before-preview]'));
  await Promise.all(previews.map(async preview => {
    const url = preview.dataset.beforeUrl || '';
    const explicit = preview.dataset.beforeExplicit === 'true';
    if (!url) return;
    let available = explicit;
    if (!available) {
      try {
        const response = await fetch(url, {method:'HEAD', credentials:'same-origin'});
        available = response.ok;
      } catch (_) {
        available = false;
      }
    }
    if (!available) return;
    preview.hidden = false;
    const frame = preview.querySelector('[data-before-frame]');
    if (frame) frame.src = url;
  }));
}
function focusedReviewDetail(item, includeDecision=false) {
  return `<div class="focus-case">
    <section class="focus-card focus-header">
      <div class="section-heading">
        <div><p class="section-kicker">Attack Scenario</p><h2>攻击场景</h2></div>
        <div class="focus-meta">${compactTags(item)}</div>
      </div>
      <form id="expertEditForm" class="review-edit-form">
        <div class="review-edit-grid">
          ${editSelect('task_type', 'Scenario Domain', item.task_type || '', [...new Set([...Object.keys(window.CLAWTRAP_ATTACKS_BY_TASK || {}), ...uniqueValues(allCases || [], 'task_type'), item.task_type].filter(Boolean))], 'taxonomy-field')}
          ${editSelect('attack_type', 'Scenario Workflow', item.attack_type || '', [...new Set([...attackOptionsForTask(item.task_type), ...uniqueValues(allCases || [], 'attack_type'), item.attack_type].filter(Boolean))], 'taxonomy-field')}
          ${editField('task', 'Benign Objective', item.task, 'tall')}
          ${editField('target', 'Target', item.target, 'tall')}
          ${taskFilesPanel(item)}
          ${editField('attack_method', 'Attack Description', item.attack_method, 'full')}
          ${listReviewField('success_states', 'Expected Behavior', item.success_states)}
          ${listReviewField('failure_states', 'Failure States', item.failure_states)}
          ${listReviewField('metadata', 'Metadata', item.metadata, 'metadata-field')}
          ${listReviewField('graders', 'Graders', item.graders, 'metadata-field')}
          ${attackImplementationPanel(item)}
        </div>
        <div class="errors" id="editErrors"></div>
        <div class="review-edit-actions" ${typeof readOnlyReview !== 'undefined' && readOnlyReview ? 'style="display:none"' : ''}>
          <button type="button" onclick="saveExpertEdit()">保存修改</button>
        </div>
      </form>
      ${includeDecision ? expertDecisionPanel(item) : ''}
    </section>
  </div>`;
}
function expertDecisionPanel(item) {
  return `<div class="decision-panel">
    <div class="section-heading"><div><p class="section-kicker">Expert Decision</p><h2>专家裁决</h2></div></div>
    <textarea id="decisionComment" placeholder="Mark notes 或裁决备注。保留和 Discard 可不填；Mark notes 建议写明需要其他人确认的点。">${escapeTextarea(item.expert_decision_comment || '')}</textarea>
    <div class="errors" id="decisionErrors"></div>
    <div class="decision-actions">
      <button type="button" class="accept" onclick="submitDecision('accepted')">保留进 Benchmark</button>
      <button type="button" class="discard" onclick="submitDecision('discarded')">Discard</button>
      <button type="button" class="mark" onclick="submitDecision('needs_discussion')">Mark notes</button>
      <button type="button" class="clear" onclick="skipCase()">Skip</button>
    </div>
  </div>`;
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
function listItemFromButton(button) {
  return button.closest('[data-list-item]');
}
function approveListItem(button) {
  const item = listItemFromButton(button);
  if (!item) return;
  item.classList.remove('needs-revision', 'removed');
  item.classList.add('approved');
  const input = item.querySelector('[data-list-input]');
  if (input) input.setAttribute('readonly', '');
}
function removeListItem(button) {
  const item = listItemFromButton(button);
  if (!item) return;
  if (!window.confirm('确认删除这一条 state / metadata 吗？')) return;
  item.remove();
}
function reviseListItem(button) {
  const item = listItemFromButton(button);
  if (!item) return;
  item.classList.remove('approved', 'removed');
  item.classList.add('needs-revision');
  const input = item.querySelector('[data-list-input]');
  if (input) {
    input.removeAttribute('readonly');
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  }
}
function addListItem(name) {
  const field = document.querySelector(`[data-list-field="${CSS.escape(name)}"]`);
  const list = field?.querySelector('.list-review-items');
  if (!list) return;
  const row = document.createElement('div');
  row.className = 'list-review-item needs-revision';
  row.setAttribute('data-list-item', '');
  row.innerHTML = `<textarea data-list-input></textarea><div class="list-review-actions">
    <button type="button" class="secondary" title="Approve" onclick="approveListItem(this)">✓</button>
    <button type="button" class="danger trash" title="Delete" onclick="removeListItem(this)">🗑</button>
    <button type="button" class="secondary" title="Revise" onclick="reviseListItem(this)">✎</button>
  </div>`;
  list.appendChild(row);
  const input = row.querySelector('[data-list-input]');
  if (input) input.focus();
}
function collectListValues(name) {
  return Array.from(document.querySelectorAll(`[data-list-field="${CSS.escape(name)}"] [data-list-item]`))
    .filter(row => !row.classList.contains('removed'))
    .map(row => row.querySelector('[data-list-input]')?.value.trim() || '')
    .filter(Boolean);
}
function currentCase() {
  return filteredCases.find(candidate => candidate.id === selectedId);
}
function showAttackImplementation() {
  const item = currentCase();
  const assets = Array.isArray(item?.attack_implementation) ? item.attack_implementation : [];
  if (!assets.length) return;
  const modal = document.createElement('div');
  modal.className = 'asset-modal';
  modal.innerHTML = `<div class="asset-modal-head">
    <div>
      <h2 class="asset-modal-title">Attack Implementation</h2>
      <div class="asset-tabs">${assets.map((asset, index) => `<button type="button" class="${index === 0 ? 'active' : ''}" data-asset-index="${index}">${escapeHtml(asset.title || `Asset ${index + 1}`)}</button>`).join('')}</div>
    </div>
    <button type="button" class="asset-close-primary" onclick="closeAttackImplementation()">返回审核</button>
  </div>
  <div class="asset-modal-body">
    <aside class="asset-info"></aside>
    <div class="asset-frame-wrap"><iframe class="asset-frame" sandbox="allow-same-origin" title="Attack implementation preview"></iframe></div>
  </div>`;
  document.body.appendChild(modal);
  document.body.style.overflow = 'hidden';
  modal.querySelectorAll('[data-asset-index]').forEach(button => {
    button.addEventListener('click', () => renderAttackAsset(Number(button.dataset.assetIndex || 0)));
  });
  renderAttackAsset(0);
}
function renderAttackAsset(index) {
  const item = currentCase();
  const assets = Array.isArray(item?.attack_implementation) ? item.attack_implementation : [];
  const asset = assets[index];
  const modal = document.querySelector('.asset-modal');
  if (!asset || !modal) return;
  modal.querySelectorAll('[data-asset-index]').forEach(button => button.classList.toggle('active', Number(button.dataset.assetIndex || 0) === index));
  modal.querySelector('.asset-info').innerHTML = `<h3>${escapeHtml(asset.title || `Asset ${index + 1}`)}</h3>
    <p><strong>Type:</strong> ${escapeHtml(asset.type || '-')}</p>
    <p>${escapeHtml(asset.description || '')}</p>
    ${asset.notes ? `<p><strong>Review focus:</strong> ${escapeHtml(asset.notes)}</p>` : ''}
    ${asset.url ? `<p><a class="button secondary" target="_blank" rel="noopener" href="${escapeHtml(asset.url)}">打开新窗口</a></p>` : ''}`;
  const frame = modal.querySelector('.asset-frame');
  if (frame) frame.src = asset.url || 'about:blank';
}
function closeAttackImplementation() {
  document.querySelector('.asset-modal')?.remove();
  document.body.style.overflow = '';
}
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && document.querySelector('.asset-modal')) closeAttackImplementation();
});
async function loadReviewCases() {
  await ensureDatasetOptions();
  updateDatasetInUrl();
  const res = await fetch(`/api/all-cases?${datasetQuery()}`);
  const data = await res.json();
  allCases = data.cases || [];
  populateCaseValueFilter('reviewTaskFilter', allCases, 'task_type', Object.keys(window.CLAWTRAP_ATTACKS_BY_TASK || {}));
  populateCaseValueFilter('reviewAttackFilter', allCases, 'attack_type', Object.values(window.CLAWTRAP_ATTACKS_BY_TASK || {}).flat());
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
  panel.innerHTML = focusedReviewDetail(item, !readOnlyReview);
  hydrateBeforePreviews(panel);
  syncTaxonomySelects(panel);
  window.refreshClawTrapSelects?.(panel);
  window.syncClawTrapSelects?.();
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
  const res = await fetch(`/api/cases/${encodeURIComponent(item.id)}/expert-decision`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({decision, comment, dataset:selectedDataset()})});
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
  payload.success_states = collectListValues('success_states');
  payload.failure_states = collectListValues('failure_states');
  payload.metadata = collectListValues('metadata');
  payload.graders = collectListValues('graders');
  payload.dataset = selectedDataset();
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
document.getElementById('datasetFilter')?.addEventListener('input', loadReviewCases);
document.getElementById('reviewDecisionFilter')?.addEventListener('input', filterReviewCases);
document.getElementById('reviewAttackFilter')?.addEventListener('input', filterReviewCases);
document.getElementById('reviewTaskFilter')?.addEventListener('input', () => { syncAttackFilterForTask('reviewTaskFilter', 'reviewAttackFilter'); filterReviewCases(); });
document.getElementById('reviewFormFilter')?.addEventListener('input', filterReviewCases);
syncAttackFilterForTask('reviewTaskFilter', 'reviewAttackFilter');
loadReviewCases();
"""


def scenes_js() -> str:
    return shared_case_js() + r"""
const controls = ['datasetFilter','selectedFilter','decisionFilter','attackFilter','taskFilter','search'].map(id => document.getElementById(id));
async function loadCases() {
  await ensureDatasetOptions();
  updateDatasetInUrl();
  const res = await fetch(`/api/all-cases?${datasetQuery()}`);
  const data = await res.json();
  allCases = data.cases || [];
  populateCaseValueFilter('taskFilter', allCases, 'task_type', Object.keys(window.CLAWTRAP_ATTACKS_BY_TASK || {}));
  populateCaseValueFilter('attackFilter', allCases, 'attack_type', Object.values(window.CLAWTRAP_ATTACKS_BY_TASK || {}).flat());
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
    stat('未裁决', filteredCases.filter(c => !c.expert_decision).length),
    stat('任务大类数', new Set(filteredCases.map(c => c.task_type || '')).size)
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
  return `${selected}<span class="pill strong">${escapeHtml(item.task_type || '-')}</span><span class="pill">${escapeHtml(item.attack_type || '-')}</span><span class="pill">Source: ${escapeHtml(dataSourceLabel(item))}</span>`;
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
    <div class="rank-actions"><a class="button secondary" href="/review?case=${encodeURIComponent(item.id)}&dataset=${encodeURIComponent(selectedDataset())}">去审核</a></div>
  </article>`;
}
controls.forEach(el => el.addEventListener('input', el?.id === 'datasetFilter' ? loadCases : (el?.id === 'taskFilter' ? () => { syncAttackFilterForTask('taskFilter', 'attackFilter'); render(); } : render)));
syncAttackFilterForTask('taskFilter', 'attackFilter');
loadCases();
"""


def benchmark_js() -> str:
    return shared_case_js() + r"""
const controls = ['attackFilter','taskFilter','sourceFilter','search'].map(id => document.getElementById(id));
async function loadCases() {
  const res = await fetch('/api/benchmark-cases');
  const data = await res.json();
  allCases = data.cases || [];
  populateSourceFilter('sourceFilter', allCases);
  populateCaseValueFilter('taskFilter', allCases, 'task_type', Object.keys(window.CLAWTRAP_ATTACKS_BY_TASK || {}));
  populateCaseValueFilter('attackFilter', allCases, 'attack_type', Object.values(window.CLAWTRAP_ATTACKS_BY_TASK || {}).flat());
  render();
}
function render() {
  const attack = document.getElementById('attackFilter').value;
  const task = document.getElementById('taskFilter').value;
  const source = document.getElementById('sourceFilter').value;
  const q = document.getElementById('search').value.trim().toLowerCase();
  filteredCases = allCases.filter(item =>
    (!attack || item.attack_type === attack) &&
    (!task || item.task_type === task) &&
    dataSourceMatches(item, source) &&
    (!q || [item.id, item.owner, item.task, benchmarkReviewer(item), dataSourceLabel(item)].join(' ').toLowerCase().includes(q))
  );
  renderStats();
  renderRows();
}
function benchmarkReviewer(item) {
  return item.expert_decision_by || item.benchmark_selected_by || '';
}
function renderStats() {
  document.getElementById('stats').innerHTML = [
    stat('当前筛选', filteredCases.length),
    stat('全部入选', allCases.length),
    stat('数据来源数', new Set(filteredCases.map(dataSourceLabel)).size),
    stat('任务大类数', new Set(filteredCases.map(c => c.task_type || '')).size),
    stat('攻击子类数', new Set(filteredCases.map(c => c.attack_type || '')).size)
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
    </div>
    <div><span class="pill">${escapeHtml(dataSourceLabel(item))}</span></div>
    <div><span class="pill">${escapeHtml(benchmarkReviewer(item) || '-')}</span></div>
    <div><span class="pill">${escapeHtml(item.attack_type || '-')}</span></div>
    <div><span class="pill strong">${escapeHtml(item.task_type || '-')}</span></div>
    <div class="rank-actions"><a class="button secondary" href="/review?mode=view&case=${encodeURIComponent(item.id)}&dataset=${encodeURIComponent(datasetName(item))}">查看</a><button type="button" class="danger" onclick="removeFromBenchmark('${escapeAttr(item.id)}')">移除</button></div>
  </article>`).join('');
}
async function removeFromBenchmark(id) {
  const item = allCases.find(candidate => candidate.id === id);
  const ok = window.confirm(`确认从 ClawTrap Bench 移除这条 case？\n\n${item?.task || id}`);
  if (!ok) return;
  try {
    await toggleBenchmarkSelection(id, false, datasetName(item || {}));
    allCases = allCases.filter(candidate => candidate.id !== id);
    render();
  } catch (error) {
    window.alert(error.message || '移除失败');
  }
}
controls.forEach(el => el.addEventListener('input', el?.id === 'taskFilter' ? () => { syncAttackFilterForTask('taskFilter', 'attackFilter'); render(); } : render));
syncAttackFilterForTask('taskFilter', 'attackFilter');
loadCases();
"""


app = create_app()


if __name__ == "__main__":
    load_dotenv()
    app.run(host=os.environ.get("APP_HOST", "127.0.0.1"), port=int(os.environ.get("APP_PORT", "8000")))
