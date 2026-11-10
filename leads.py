"""Inbound interest: people who asked for a free API key.

The /for-teams page posts here. A request is a lead, not an account: nothing is
issued automatically. An operator reviews the list in the control room and mints
a key by hand, which keeps the free tier from being farmed by a script.

Stored through db.py, so requests survive a redeploy the same way keys do.
"""
from __future__ import annotations

import re
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import db

_lock_guard = threading.Lock()

# Only these plans are offered on the request form.
WANTED_TIERS = {"free", "starter", "pro"}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_schema_engine: str | None = None


def _ensure_schema(conn) -> None:
    global _schema_engine
    engine = db.backend()
    if _schema_engine == engine:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS key_requests (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            org         TEXT,
            use_case    TEXT,
            wanted_tier TEXT NOT NULL,
            status      TEXT NOT NULL,
            issued_key  TEXT,
            created_at  TEXT NOT NULL
        )
        """
    )
    _schema_engine = engine


@contextmanager
def _connect():
    with db.connect() as conn:
        _ensure_schema(conn)
        yield conn


def _clean(value: str, limit: int) -> str:
    return (value or "").strip()[:limit]


def create_request(name: str, email: str, org: str = "", use_case: str = "",
                   wanted_tier: str = "free") -> dict:
    """Record a request for a free key. Returns {ok, id} or {ok: False, error}."""
    name = _clean(name, 120)
    email = _clean(email, 200).lower()
    org = _clean(org, 160)
    use_case = _clean(use_case, 600)
    tier = wanted_tier if wanted_tier in WANTED_TIERS else "free"

    if len(name) < 2:
        return {"ok": False, "error": "please give a name"}
    if not _EMAIL_RE.match(email):
        return {"ok": False, "error": "please give a valid email address"}

    request_id = uuid.uuid4().hex[:12]
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock_guard, _connect() as conn:
        conn.execute(
            "INSERT INTO key_requests "
            "(id, name, email, org, use_case, wanted_tier, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (request_id, name, email, org, use_case, tier, "new", created),
        )
    return {"ok": True, "id": request_id, "created_at": created}


def list_requests(limit: int = 100) -> list[dict]:
    try:
        with _lock_guard, _connect() as conn:
            rows = conn.execute(
                "SELECT id, name, email, org, use_case, wanted_tier, status, issued_key, created_at "
                "FROM key_requests ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except Exception:
        return []
    return [
        {"id": r[0], "name": r[1], "email": r[2], "org": r[3], "use_case": r[4],
         "wanted_tier": r[5], "status": r[6], "issued_key": r[7], "created_at": r[8]}
        for r in rows
    ]


def mark_issued(request_id: str, key: str) -> bool:
    with _lock_guard, _connect() as conn:
        cur = conn.execute(
            "UPDATE key_requests SET status = 'issued', issued_key = ? WHERE id = ?",
            (key, request_id),
        )
    return cur.rowcount > 0


def delete_request(request_id: str) -> bool:
    """Drop a request — used to clear spam that reaches the public form."""
    with _lock_guard, _connect() as conn:
        cur = conn.execute("DELETE FROM key_requests WHERE id = ?", (request_id,))
    return cur.rowcount > 0


def counts() -> dict:
    rows = list_requests(limit=500)
    return {
        "total": len(rows),
        "new": sum(1 for r in rows if r["status"] == "new"),
    }
