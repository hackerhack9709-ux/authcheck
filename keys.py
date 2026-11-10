"""API keys, tiers and usage metering.

Three tiers:

  anonymous  no key, limited by client IP
  free       a key on the free tier, a little more headroom
  pro        a paid key, much higher limit

Keys live in SQLite when the host gives us a writable disk, and can also be
supplied through the AUTHCHECK_API_KEYS environment variable as
"key:tier,key:tier" for hosts with an ephemeral filesystem. Rate-limit counters
are in memory: they reset on restart, which is the correct behaviour for a
sliding window.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("AUTHCHECK_DB", "./data/authcheck.db"))
KEY_PREFIX = "ac_"

# requests per hour, and the endpoints that count against the quota
TIERS = {
    "anonymous": {"limit": 20, "label": "Anonymous"},
    "free": {"limit": 120, "label": "Free"},
    "pro": {"limit": 2000, "label": "Pro"},
    "desk": {"limit": 10000, "label": "Desk"},
}

METERED_PREFIXES = ("/api/check-text", "/api/analyze-image", "/api/analyze-audio", "/api/analyze-video")

_lock = threading.Lock()
_buckets: dict[str, list[float]] = {}
_usage: dict[str, int] = {}


# --------------------------------------------------------------------------- #
# storage
# --------------------------------------------------------------------------- #
def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            key         TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            tier        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            revoked     INTEGER NOT NULL DEFAULT 0,
            requests    INTEGER NOT NULL DEFAULT 0,
            last_used   TEXT,
            expires_at  TEXT
        )
        """
    )
    # older databases predate expiry
    cols = {r[1] for r in conn.execute("PRAGMA table_info(api_keys)")}
    if "expires_at" not in cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN expires_at TEXT")
    return conn


def _expiry_from_now(days: int) -> str | None:
    if not days:
        return None
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds")


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.now(timezone.utc) > datetime.fromisoformat(expires_at)
    except ValueError:
        return False


def storage_available() -> bool:
    """True when keys can be persisted (writable disk present)."""
    try:
        with _connect():
            return True
    except Exception:
        return False


def _static_keys() -> dict[str, dict]:
    """Keys handed in through the environment, e.g. AUTHCHECK_API_KEYS=a:pro,b:free."""
    raw = os.environ.get("AUTHCHECK_API_KEYS", "").strip()
    out: dict[str, dict] = {}
    for chunk in filter(None, (c.strip() for c in raw.split(","))):
        key, _, tier = chunk.partition(":")
        tier = tier or "pro"
        if tier not in TIERS:
            tier = "pro"
        out[key] = {"key": key, "name": "env", "tier": tier, "source": "env"}
    return out


# --------------------------------------------------------------------------- #
# key lifecycle
# --------------------------------------------------------------------------- #
def create_key(name: str, tier: str = "pro", days: int = 0) -> dict:
    """Mint a key. days=0 means it never expires (used for free and internal keys)."""
    if tier not in TIERS:
        raise ValueError(f"unknown tier: {tier}")
    key = KEY_PREFIX + secrets.token_urlsafe(24)
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    expires = _expiry_from_now(days)
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO api_keys (key, name, tier, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
            (key, name.strip() or "unnamed", tier, created, expires),
        )
    return {"key": key, "name": name, "tier": tier, "created_at": created,
            "expires_at": expires, "revoked": False}


def extend_key(key: str, days: int) -> str | None:
    """Push a key's expiry out by `days`, from now if already lapsed. Returns the new expiry."""
    if days <= 0:
        return None
    try:
        with _lock, _connect() as conn:
            row = conn.execute("SELECT expires_at FROM api_keys WHERE key = ?", (key,)).fetchone()
            if not row:
                return None
            base = datetime.now(timezone.utc)
            if row[0]:
                try:
                    current = datetime.fromisoformat(row[0])
                    if current > base:
                        base = current
                except ValueError:
                    pass
            new_expiry = (base + timedelta(days=days)).isoformat(timespec="seconds")
            conn.execute(
                "UPDATE api_keys SET expires_at = ?, revoked = 0 WHERE key = ?",
                (new_expiry, key),
            )
        return new_expiry
    except Exception:
        return None


def revoke_key(key: str) -> bool:
    with _lock, _connect() as conn:
        cur = conn.execute("UPDATE api_keys SET revoked = 1 WHERE key = ?", (key,))
    return cur.rowcount > 0


def list_keys() -> list[dict]:
    try:
        with _lock, _connect() as conn:
            rows = conn.execute(
                "SELECT key, name, tier, created_at, revoked, requests, last_used, expires_at "
                "FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
    except Exception:
        rows = []
    out = [
        {
            "key": r[0],
            "masked": r[0][:9] + "..." + r[0][-4:],
            "name": r[1],
            "tier": r[2],
            "created_at": r[3],
            "revoked": bool(r[4]),
            "requests": r[5],
            "last_used": r[6],
            "expires_at": r[7],
            "expired": _is_expired(r[7]),
            "limit_per_hour": TIERS.get(r[2], TIERS["pro"])["limit"],
        }
        for r in rows
    ]
    for key, info in _static_keys().items():
        out.append(
            {
                "key": key,
                "masked": key[:9] + "..." + key[-4:],
                "name": info["name"],
                "tier": info["tier"],
                "created_at": None,
                "revoked": False,
                "requests": _usage.get(key, 0),
                "last_used": None,
                "limit_per_hour": TIERS[info["tier"]]["limit"],
                "source": "env",
            }
        )
    return out


def verify_key(key: str) -> dict | None:
    """Return the key record when valid, else None. Expired and revoked keys are invalid."""
    if not key:
        return None
    static = _static_keys()
    if key in static:
        return dict(static[key], source="env")
    try:
        with _lock, _connect() as conn:
            row = conn.execute(
                "SELECT key, name, tier, created_at, revoked, expires_at FROM api_keys WHERE key = ?",
                (key,),
            ).fetchone()
    except Exception:
        return None
    if not row or row[4] or _is_expired(row[5]):
        return None
    return {"key": row[0], "name": row[1], "tier": row[2], "created_at": row[3],
            "expires_at": row[5], "source": "db"}


def why_invalid(key: str) -> str:
    """Explain a rejected key, so the panel can say 'expired' rather than 'unknown'."""
    if not key:
        return "missing"
    try:
        with _lock, _connect() as conn:
            row = conn.execute("SELECT revoked, expires_at FROM api_keys WHERE key = ?", (key,)).fetchone()
    except Exception:
        return "unknown"
    if not row:
        return "unknown"
    if row[0]:
        return "revoked"
    if _is_expired(row[1]):
        return "expired"
    return "unknown"


def identify(api_key: str, client_ip: str) -> dict:
    """Resolve a caller to a tier. Bad keys are treated as anonymous."""
    record = verify_key(api_key)
    if record:
        return {"tier": record["tier"], "bucket": record["key"], "key": record, "valid_key": True}
    return {"tier": "anonymous", "bucket": f"ip:{client_ip or 'unknown'}", "key": None,
            "valid_key": False, "invalid_reason": why_invalid(api_key)}


# --------------------------------------------------------------------------- #
# rate limiting + metering
# --------------------------------------------------------------------------- #
def is_metered(path: str) -> bool:
    return any(path.startswith(p) for p in METERED_PREFIXES)


def check_rate(bucket: str, tier: str) -> dict:
    """Sliding one-hour window. Returns allowed/limit/remaining/reset."""
    limit = TIERS.get(tier, TIERS["anonymous"])["limit"]
    now = time.time()
    with _lock:
        hits = [t for t in _buckets.get(bucket, []) if now - t < 3600]
        allowed = len(hits) < limit
        if allowed:
            hits.append(now)
        _buckets[bucket] = hits
        oldest = min(hits) if hits else now
    return {
        "allowed": allowed,
        "tier": tier,
        "limit_per_hour": limit,
        "used": len(hits),
        "remaining": max(0, limit - len(hits)),
        "reset_in_seconds": int(3600 - (now - oldest)),
    }


def record_usage(api_key: str | None) -> None:
    if not api_key:
        return
    _usage[api_key] = _usage.get(api_key, 0) + 1
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "UPDATE api_keys SET requests = requests + 1, last_used = ? WHERE key = ?",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), api_key),
            )
    except Exception:
        pass


def usage_summary() -> dict:
    total = sum(_usage.values())
    return {
        "keys_in_use": len(_usage),
        "requests_this_process": total,
        "storage": "sqlite" if storage_available() else "memory-only",
        "tiers": {name: {"limit_per_hour": t["limit"], "label": t["label"]} for name, t in TIERS.items()},
    }
