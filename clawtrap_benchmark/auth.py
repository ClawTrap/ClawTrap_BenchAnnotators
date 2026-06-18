from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from typing import Mapping

from werkzeug.security import check_password_hash


VALID_ROLES = {"annotator", "admin"}


@dataclass(frozen=True)
class Account:
    username: str
    role: str
    password: str | None = None
    password_hash: str | None = None


def load_accounts(environ: Mapping[str, str] | None = None) -> dict[str, Account]:
    env = environ or os.environ
    accounts: dict[str, Account] = {}

    for key in ("CLAWTRAP_ACCOUNTS_JSON", "ACCOUNTS_JSON"):
        raw = env.get(key, "").strip()
        if raw:
            accounts.update(_parse_accounts_json(raw))

    accounts.update(_parse_credential_pairs(env.get("ANNOTATOR_ACCOUNTS", ""), "annotator"))

    for username_key, password_key in (
        ("ADMIN_USERNAME", "ADMIN_PASSWORD"),
        ("ADMIN_USERNAME_2", "ADMIN_PASSWORD_2"),
        ("ADMIN2_USERNAME", "ADMIN2_PASSWORD"),
    ):
        username = env.get(username_key, "").strip()
        password = env.get(password_key, "")
        if username and password:
            accounts[username] = Account(username=username, role="admin", password=password)

    if not accounts and env.get("VERCEL") != "1":
        accounts["admin"] = Account(username="admin", role="admin", password="admin")
        accounts["admin2"] = Account(username="admin2", role="admin", password="admin2")

    return accounts


def authenticate(username: str, password: str, environ: Mapping[str, str] | None = None) -> Account | None:
    username = username.strip()
    if not username or not password:
        return None
    account = load_accounts(environ).get(username)
    if not account:
        return None
    if account.password_hash:
        try:
            return account if check_password_hash(account.password_hash, password) else None
        except (TypeError, ValueError):
            return None
    if account.password is not None:
        return account if secrets.compare_digest(password, account.password) else None
    return None


def _parse_accounts_json(raw: str) -> dict[str, Account]:
    data = json.loads(raw)
    accounts: dict[str, Account] = {}
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = []
        for username, payload in data.items():
            if isinstance(payload, str):
                entries.append({"username": username, "password": payload})
            elif isinstance(payload, dict):
                entries.append({"username": username, **payload})
            else:
                raise ValueError("account payload must be a string or object")
    else:
        raise ValueError("accounts json must be an object or array")

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("account entry must be an object")
        username = str(entry.get("username", "")).strip()
        role = str(entry.get("role", "annotator")).strip()
        password = entry.get("password")
        password_hash = entry.get("password_hash")
        if not username:
            raise ValueError("account username is required")
        if role not in VALID_ROLES:
            raise ValueError(f"invalid role for {username}: {role}")
        if not password and not password_hash:
            raise ValueError(f"password or password_hash is required for {username}")
        accounts[username] = Account(
            username=username,
            role=role,
            password=str(password) if password is not None else None,
            password_hash=str(password_hash) if password_hash is not None else None,
        )
    return accounts


def _parse_credential_pairs(raw: str, role: str) -> dict[str, Account]:
    accounts: dict[str, Account] = {}
    for chunk in raw.replace("\n", ",").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk:
            username, password = chunk.split(":", 1)
        elif "=" in chunk:
            username, password = chunk.split("=", 1)
        else:
            raise ValueError("credential pairs must use username:password")
        username = username.strip()
        if not username or not password:
            raise ValueError("credential username and password are required")
        accounts[username] = Account(username=username, role=role, password=password)
    return accounts
