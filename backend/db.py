"""Accounts, workspaces and the activity log for Pension Helper (SQLite in backend/data/, never committed).

- Every person signs up with an email and a password (stored only as a salted PBKDF2 hash).
- Every account owns one private workspace. Its key (for example "w12") is the `dataset` value on
  all of that workspace's rows in the n8n Data Tables, so nobody ever sees another workspace's data.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(os.getenv("PH_DB_PATH") or (Path(__file__).resolve().parent / "data" / "pension_helper_v2.db"))
ITERATIONS = 240_000
MAX_FAILED = 5
LOCK_SECONDS = 10 * 60

_lock = threading.Lock()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_con = sqlite3.connect(DB_PATH, check_same_thread=False)
_con.row_factory = sqlite3.Row
_con.execute("PRAGMA foreign_keys = ON")


def init() -> None:
    with _lock, _con:
        _con.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                kind TEXT NOT NULL CHECK (kind IN ('office', 'family')),
                name TEXT NOT NULL DEFAULT '',
                details TEXT NOT NULL DEFAULT '{}',
                consent_at TEXT,
                consent_by TEXT,
                onboarding_step INTEGER NOT NULL DEFAULT 1,
                onboarding_done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('office', 'family')),
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                pw_salt TEXT NOT NULL,
                pw_hash TEXT NOT NULL,
                pw_iter INTEGER NOT NULL,
                token_version INTEGER NOT NULL DEFAULT 1,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,
                workspace_id INTEGER,
                email TEXT,
                action TEXT NOT NULL,
                detail TEXT
            );
            -- Family status check: a one-way fingerprint (HMAC) of PPO number + date of birth -> pensioner.
            -- Neither the full PPO number nor the date of birth is stored anywhere.
            CREATE TABLE IF NOT EXISTS family_lookup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL,
                workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
                pensioner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (workspace_id, pensioner_id)
            );
            CREATE INDEX IF NOT EXISTS family_lookup_fp ON family_lookup (fingerprint);
            -- Wrong status-check attempts per device (IP address): 5 wrong -> wait 10 minutes.
            CREATE TABLE IF NOT EXISTS lookup_attempts (
                client TEXT PRIMARY KEY,
                failed INTEGER NOT NULL DEFAULT 0,
                locked_until REAL NOT NULL DEFAULT 0
            );
            """
        )


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------------------------------------------------------- passwords


def _hash(password: str) -> tuple[str, str, int]:
    salt = os.urandom(16)
    return salt.hex(), hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS).hex(), ITERATIONS


def _verify(row: sqlite3.Row | None, password: str) -> bool:
    salt = bytes.fromhex(row["pw_salt"]) if row else b"\0" * 16
    iters = int(row["pw_iter"]) if row else ITERATIONS
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iters).hex()
    return row is not None and hmac.compare_digest(digest, row["pw_hash"])


# ---------------------------------------------------------------- accounts + workspaces


def email_taken(email: str) -> bool:
    return _con.execute("SELECT 1 FROM accounts WHERE email = ?", (email,)).fetchone() is not None


def sign_up(email: str, password: str, role: str, display_name: str) -> tuple[dict, dict]:
    salt, digest, iters = _hash(password)
    with _lock, _con:
        # Random key, so workspaces from different databases (e.g. tests) can never share data in n8n.
        while True:
            key = f"w{secrets.randbelow(900_000_000) + 100_000_000}"
            if not _con.execute("SELECT 1 FROM workspaces WHERE key = ?", (key,)).fetchone():
                break
        ws_id = _con.execute("INSERT INTO workspaces (key, kind, name, created_at) VALUES (?, ?, ?, ?)", (key, role, "", now())).lastrowid
        acc_id = _con.execute(
            "INSERT INTO accounts (email, display_name, role, workspace_id, pw_salt, pw_hash, pw_iter, created_at, last_login_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (email, display_name, role, ws_id, salt, digest, iters, now(), now()),
        ).lastrowid
    return get_account(acc_id), get_workspace(ws_id)


def check_login(email: str, password: str) -> tuple[dict | None, str | None]:
    """(account, None) on success, else (None, 'wrong' | 'locked'). 5 wrong passwords lock the account for 10 minutes."""
    with _lock:
        row = _con.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
        t = time.time()
        if row and row["locked_until"] > t:
            _verify(None, password)
            return None, "locked"
        if not _verify(row, password):
            if row:
                failed = row["failed_attempts"] + 1
                locked = t + LOCK_SECONDS if failed >= MAX_FAILED else 0
                with _con:
                    _con.execute("UPDATE accounts SET failed_attempts = ?, locked_until = ? WHERE id = ?", (0 if locked else failed, locked, row["id"]))
            return None, "wrong"
        with _con:
            _con.execute("UPDATE accounts SET failed_attempts = 0, locked_until = 0, last_login_at = ? WHERE id = ?", (now(), row["id"]))
        return dict(row), None


def get_account(account_id: int) -> dict | None:
    row = _con.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def set_password(account_id: int, password: str) -> None:
    salt, digest, iters = _hash(password)
    with _lock, _con:
        _con.execute("UPDATE accounts SET pw_salt = ?, pw_hash = ?, pw_iter = ?, token_version = token_version + 1,"
                     " failed_attempts = 0, locked_until = 0 WHERE id = ?", (salt, digest, iters, account_id))


def verify_password(account_id: int, password: str) -> bool:
    return _verify(_con.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone(), password)


def get_workspace(workspace_id: int) -> dict | None:
    row = _con.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if not row:
        return None
    ws = dict(row)
    ws["details"] = json.loads(ws["details"] or "{}")
    return ws


def update_workspace(workspace_id: int, **fields) -> dict:
    if "details" in fields:
        fields["details"] = json.dumps(fields["details"])
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _lock, _con:
        _con.execute(f"UPDATE workspaces SET {cols} WHERE id = ?", (*fields.values(), workspace_id))
    return get_workspace(workspace_id)


# ---------------------------------------------------------------- family status check


def set_lookup(workspace_id: int, pensioner_id: int, fingerprint: str) -> None:
    with _lock, _con:
        _con.execute("INSERT INTO family_lookup (fingerprint, workspace_id, pensioner_id, created_at) VALUES (?, ?, ?, ?)"
                     " ON CONFLICT (workspace_id, pensioner_id) DO UPDATE SET fingerprint = excluded.fingerprint, created_at = excluded.created_at",
                     (fingerprint, workspace_id, pensioner_id, now()))


def remove_lookup(workspace_id: int, pensioner_id: int) -> None:
    with _lock, _con:
        _con.execute("DELETE FROM family_lookup WHERE workspace_id = ? AND pensioner_id = ?", (workspace_id, pensioner_id))


def lookup_ids(workspace_id: int) -> set[int]:
    return {r[0] for r in _con.execute("SELECT pensioner_id FROM family_lookup WHERE workspace_id = ?", (workspace_id,))}


def find_lookup(fingerprint: str) -> list[dict]:
    """Newest first: the same pensioner may be listed by more than one office."""
    return [dict(r) for r in _con.execute(
        "SELECT l.workspace_id, l.pensioner_id, w.key AS workspace_key FROM family_lookup l JOIN workspaces w ON w.id = l.workspace_id"
        " WHERE l.fingerprint = ? AND w.kind = 'office' ORDER BY l.id DESC", (fingerprint,))]


def lookup_locked(client: str) -> float:
    """Seconds left on the lock for this device (0 if not locked)."""
    row = _con.execute("SELECT locked_until FROM lookup_attempts WHERE client = ?", (client,)).fetchone()
    return max(0.0, row["locked_until"] - time.time()) if row else 0.0


def lookup_failed(client: str) -> tuple[int, float]:
    """Counts a wrong attempt. Returns (attempts left, seconds locked)."""
    with _lock, _con:
        row = _con.execute("SELECT failed FROM lookup_attempts WHERE client = ?", (client,)).fetchone()
        failed = (row["failed"] if row else 0) + 1
        if failed >= MAX_FAILED:
            _con.execute("INSERT INTO lookup_attempts (client, failed, locked_until) VALUES (?, 0, ?)"
                         " ON CONFLICT (client) DO UPDATE SET failed = 0, locked_until = excluded.locked_until", (client, time.time() + LOCK_SECONDS))
            return 0, float(LOCK_SECONDS)
        _con.execute("INSERT INTO lookup_attempts (client, failed, locked_until) VALUES (?, ?, 0)"
                     " ON CONFLICT (client) DO UPDATE SET failed = excluded.failed, locked_until = 0", (client, failed))
        return MAX_FAILED - failed, 0.0


def lookup_ok(client: str) -> None:
    with _lock, _con:
        _con.execute("DELETE FROM lookup_attempts WHERE client = ?", (client,))


# ---------------------------------------------------------------- activity log (per workspace)


def audit(workspace_id: int | None, email: str | None, action: str, detail: str = "") -> None:
    with _lock, _con:
        _con.execute("INSERT INTO audit (at, workspace_id, email, action, detail) VALUES (?, ?, ?, ?, ?)",
                     (now(), workspace_id, email, action, detail[:500]))


def recent_audit(workspace_id: int, limit: int = 40) -> list[dict]:
    return [dict(r) for r in _con.execute(
        "SELECT at, email, action, detail FROM audit WHERE workspace_id = ? ORDER BY id DESC LIMIT ?", (workspace_id, limit))]
