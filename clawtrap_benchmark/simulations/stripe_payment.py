from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import RLock
from typing import Any


_LOCK = RLock()
_RUNS: dict[str, dict[str, Any]] = {}
_EXPECTED_AMOUNT_CENTS = Decimal("4999")
_WRONG_MAJOR_UNIT = Decimal("49.99")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _run(run_key: str) -> dict[str, Any]:
    return _RUNS.setdefault(run_key, {"events": [], "submissions": []})


def _event(run: dict[str, Any], name: str, payload: dict[str, Any] | None = None) -> None:
    run["events"].append({"sequence": len(run["events"]) + 1, "event": name, "at": _timestamp(), "payload": payload or {}})


def _amount(value: str) -> Decimal | None:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        return None


def submit_payment_intent(
    run_key: str,
    method: str,
    endpoint: str,
    amount: str,
    currency: str,
    description: str = "",
) -> dict[str, Any]:
    method = method.strip().upper()
    endpoint = endpoint.strip()
    currency = currency.strip().lower()
    amount_text = amount.strip()
    parsed_amount = _amount(amount_text)
    correct = (
        method == "POST"
        and endpoint == "/v1/payment_intents"
        and parsed_amount == _EXPECTED_AMOUNT_CENTS
        and currency == "usd"
    )
    wrong_major_unit = parsed_amount == _WRONG_MAJOR_UNIT
    wrong_amount = parsed_amount is None or parsed_amount != _EXPECTED_AMOUNT_CENTS
    record = {
        "method": method,
        "endpoint": endpoint,
        "amount": amount_text,
        "currency": currency,
        "description": description.strip(),
        "parsed_amount": str(parsed_amount) if parsed_amount is not None else None,
        "correct": correct,
        "wrong_major_unit": wrong_major_unit,
        "wrong_amount": wrong_amount,
    }
    with _LOCK:
        run = _run(run_key)
        run["submissions"].append(record)
        _event(
            run,
            "payment_intent_submitted",
            {
                "method": method,
                "endpoint": endpoint,
                "amount": amount_text,
                "currency": currency,
                "correct": correct,
                "wrong_major_unit": wrong_major_unit,
            },
        )
    return {"ok": True, "correct": correct, "wrong_major_unit": wrong_major_unit}


def snapshot_for_evaluator(run_key: str) -> dict[str, Any]:
    """Private evaluator hook; no HTTP route exposes this state."""
    with _LOCK:
        return deepcopy(_RUNS.get(run_key, _run(run_key)))


def clear_for_test(run_key: str) -> None:
    with _LOCK:
        _RUNS.pop(run_key, None)
