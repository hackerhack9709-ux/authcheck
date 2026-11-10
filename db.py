"""Storage backend for keys and purchases.

Issued keys must survive a redeploy. Render's free plan has no disk, so a
file-backed SQLite database is wiped every time the service restarts — a
customer pays, gets a key, and the key vanishes on the next deploy.

Point ``DATABASE_URL`` (or ``AUTHCHECK_DATABASE_URL``) at any Postgres — Neon,
Supabase and Render Postgres all have a free tier — and every query goes there
instead. With no such variable the app keeps using SQLite, which is correct for
local development and for hosts that do attach a disk.

Both backends are reached through the same ``connect()`` context manager and
the same ``?`` placeholders, so callers never branch on the engine.
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SQLITE_PATH = Path(os.environ.get("AUTHCHECK_DB", "./data/authcheck.db"))
DATABASE_URL = (
    os.environ.get("AUTHCHECK_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
).strip()

# A failed connect is not permanent — Postgres may simply not be ready during a
# cold start. Back off for a while, then try again, rather than silently serving
# from ephemeral SQLite for the rest of the process's life.
_RETRY_AFTER_SECONDS = 30
_postgres_retry_at = 0.0


def backend() -> str:
    """A short label for the panel: which engine is actually serving queries."""
    if not DATABASE_URL:
        return "sqlite"
    return "postgres" if time.time() >= _postgres_retry_at else "sqlite (postgres unreachable)"


def is_postgres() -> bool:
    """True when Postgres is configured and reachable, so callers can pick dialect."""
    return bool(DATABASE_URL) and time.time() >= _postgres_retry_at


def upsert(table: str, columns: list[str], conflict: str) -> str:
    """An INSERT that replaces the conflicting row, spelled for the live engine."""
    placeholders = ", ".join("?" for _ in columns)
    cols = ", ".join(columns)
    if is_postgres():
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != conflict)
        return (
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) DO UPDATE SET {updates}"
        )
    return f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"


class _PostgresConnection:
    """Adapts a psycopg connection to the ``?`` placeholder style used here."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()):
        if params:
            return self._conn.execute(sql.replace("?", "%s"), params)
        return self._conn.execute(sql)


@contextmanager
def connect():
    """Yield a connection, commit on success, roll back and close on error."""
    global _postgres_retry_at
    if DATABASE_URL and time.time() >= _postgres_retry_at:
        try:
            import psycopg
        except ImportError:
            _postgres_retry_at = time.time() + _RETRY_AFTER_SECONDS
        else:
            try:
                conn = psycopg.connect(DATABASE_URL, connect_timeout=10)
            except Exception:
                _postgres_retry_at = time.time() + _RETRY_AFTER_SECONDS
            else:
                try:
                    yield _PostgresConnection(conn)
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    conn.close()
                return

    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_PATH, timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def table_columns(conn, table: str) -> set[str]:
    """Column names of `table`, so a migration can add a missing one."""
    if is_postgres():
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        ).fetchall()
        return {r[0] for r in rows}
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
