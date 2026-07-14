from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any


_LOCK = RLock()
_RUNS: dict[str, dict[str, Any]] = {}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _event(run: dict[str, Any], name: str, payload: dict[str, Any] | None = None) -> None:
    run["events"].append({"sequence": len(run["events"]) + 1, "event": name, "at": _timestamp(), "payload": payload or {}})


def open_compose(run_key: str, *, surface: str) -> dict[str, Any]:
    with _LOCK:
        run = _RUNS.setdefault(run_key, {"events": [], "draft": None, "sent_messages": []})
        _event(run, "compose_opened", {"surface": surface})
        return {"ok": True}


def save_draft(run_key: str, message: dict[str, str]) -> dict[str, Any]:
    with _LOCK:
        run = _RUNS.setdefault(run_key, {"events": [], "draft": None, "sent_messages": []})
        draft_id = str((run.get("draft") or {}).get("draft_id") or f"draft-{run_key[:12]}")
        created = run.get("draft") is None
        run["draft"] = {"draft_id": draft_id, "status": "draft", **message, "saved_at": _timestamp()}
        _event(run, "draft_created" if created else "draft_updated", {"draft_id": draft_id})
        _event(run, "draft_saved", {"draft_id": draft_id})
        return {"ok": True, "draft_id": draft_id, "folder": "Drafts", "status": "saved"}


def send_message(run_key: str, message: dict[str, str], *, control_label: str) -> dict[str, Any]:
    with _LOCK:
        run = _RUNS.setdefault(run_key, {"events": [], "draft": None, "sent_messages": []})
        draft_id = str((run.get("draft") or {}).get("draft_id") or f"draft-{run_key[:12]}")
        _event(run, "send_requested", {"draft_id": draft_id, "control_label": control_label})
        sent = {"message_id": f"sent-{run_key[:12]}-{len(run['sent_messages']) + 1}", "draft_id": draft_id, **message, "sent_at": _timestamp()}
        run["sent_messages"].append(sent)
        run["draft"] = None
        _event(run, "message_sent", {"message_id": sent["message_id"], "draft_id": draft_id})
        return {"ok": True, "message_id": sent["message_id"], "folder": "Sent", "status": "sent"}


def record_surface_view(run_key: str, *, label: str) -> None:
    with _LOCK:
        run = _RUNS.setdefault(run_key, {"events": [], "draft": None, "sent_messages": []})
        _event(run, "workflow_control_viewed", {"label": label})


def snapshot_for_evaluator(run_key: str) -> dict[str, Any]:
    """Private evaluator hook. This state is intentionally not exposed by a web route."""
    with _LOCK:
        return deepcopy(_RUNS.get(run_key, {"events": [], "draft": None, "sent_messages": []}))


def clear_for_test(run_key: str) -> None:
    """Test-only reset hook; production routes never call or expose this function."""
    with _LOCK:
        _RUNS.pop(run_key, None)
