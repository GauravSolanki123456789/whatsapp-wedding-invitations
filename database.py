"""Shared database — SQLite locally, PostgreSQL (Supabase/Neon) for multi-device sync."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse, urlunparse

from constants import DATABASE_FILE, ENV_DATABASE_URL

_SCHEMA_VERSION = 1

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS family (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guest_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (family_id) REFERENCES family(id) ON DELETE CASCADE,
    UNIQUE (family_id, name)
);

CREATE TABLE IF NOT EXISTS guest_list_member (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_list_id INTEGER NOT NULL,
    guest_name TEXT NOT NULL DEFAULT '',
    mobile_number TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (guest_list_id) REFERENCES guest_list(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_function (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (family_id) REFERENCES family(id) ON DELETE CASCADE,
    UNIQUE (family_id, name)
);

CREATE TABLE IF NOT EXISTS gift_guest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_function_id INTEGER NOT NULL,
    guest_name TEXT NOT NULL DEFAULT '',
    mobile_number TEXT NOT NULL,
    gift_quantity INTEGER NOT NULL DEFAULT 1,
    qr_token TEXT NOT NULL UNIQUE,
    gifts_given INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (event_function_id) REFERENCES event_function(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gift_scan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gift_guest_id INTEGER NOT NULL,
    gifts_given INTEGER NOT NULL,
    scanned_at TEXT NOT NULL,
    scanned_by TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (gift_guest_id) REFERENCES gift_guest(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_guest_list_member_list ON guest_list_member(guest_list_id);
CREATE INDEX IF NOT EXISTS idx_gift_guest_function ON gift_guest(event_function_id);
CREATE INDEX IF NOT EXISTS idx_gift_guest_token ON gift_guest(qr_token);
"""

_POSTGRES_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS family (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS guest_list (
        id SERIAL PRIMARY KEY,
        family_id INTEGER NOT NULL REFERENCES family(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (family_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS guest_list_member (
        id SERIAL PRIMARY KEY,
        guest_list_id INTEGER NOT NULL REFERENCES guest_list(id) ON DELETE CASCADE,
        guest_name TEXT NOT NULL DEFAULT '',
        mobile_number TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_function (
        id SERIAL PRIMARY KEY,
        family_id INTEGER NOT NULL REFERENCES family(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (family_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gift_guest (
        id SERIAL PRIMARY KEY,
        event_function_id INTEGER NOT NULL REFERENCES event_function(id) ON DELETE CASCADE,
        guest_name TEXT NOT NULL DEFAULT '',
        mobile_number TEXT NOT NULL,
        gift_quantity INTEGER NOT NULL DEFAULT 1,
        qr_token TEXT NOT NULL UNIQUE,
        gifts_given INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gift_scan (
        id SERIAL PRIMARY KEY,
        gift_guest_id INTEGER NOT NULL REFERENCES gift_guest(id) ON DELETE CASCADE,
        gifts_given INTEGER NOT NULL,
        scanned_at TEXT NOT NULL,
        scanned_by TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_guest_list_member_list ON guest_list_member(guest_list_id)",
    "CREATE INDEX IF NOT EXISTS idx_gift_guest_function ON gift_guest(event_function_id)",
    "CREATE INDEX IF NOT EXISTS idx_gift_guest_token ON gift_guest(qr_token)",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if parsed.scheme.startswith("postgresql") and "sslmode" not in query:
        query["sslmode"] = ["require"]
        new_query = "&".join(f"{key}={values[0]}" for key, values in query.items())
        parsed = parsed._replace(query=new_query)
        url = urlunparse(parsed)
    return url


def get_database_url() -> str | None:
    url = os.environ.get(ENV_DATABASE_URL, "").strip()
    if not url:
        return None
    if url.startswith("sqlite:///"):
        return url
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return _normalize_postgres_url(url)
    return None


def is_cloud_database() -> bool:
    url = get_database_url()
    return bool(url and url.startswith("postgresql://"))


def is_sqlite_database() -> bool:
    return not is_cloud_database()


def get_database_status() -> dict[str, str]:
    if is_cloud_database():
        return {
            "level": "ok",
            "label": "Cloud DB — all phones synced",
            "detail": "Families, lists, and scans update live across every device.",
        }
    from hosting import is_cloud_host

    if is_cloud_host():
        return {
            "level": "warn",
            "label": "Local DB only — phones may not sync",
            "detail": "Add DATABASE_URL in Streamlit Secrets (see GUIDE.md) for shared data.",
        }
    return {
        "level": "info",
        "label": "Local DB — single computer",
        "detail": "Set DATABASE_URL to Supabase/Postgres for multi-phone scanning.",
    }


def get_sqlite_path() -> str:
    url = get_database_url()
    if url and url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    return DATABASE_FILE


class ExecuteResult:
    """Unified cursor result for SQLite and PostgreSQL."""

    def __init__(self, cursor: Any, postgres: bool, insert_returning: bool = False) -> None:
        self._cursor = cursor
        self._postgres = postgres
        self._insert_id: int | None = None
        if postgres and insert_returning:
            row = cursor.fetchone()
            if row is not None:
                self._insert_id = int(row[0] if isinstance(row, (list, tuple)) else row["id"])

    @property
    def lastrowid(self) -> int | None:
        if self._postgres:
            return self._insert_id
        return self._cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()


class DbConnection:
    """Database connection wrapper — SQL always uses ? placeholders."""

    def __init__(self, raw_connection: Any, postgres: bool) -> None:
        self._conn = raw_connection
        self._postgres = postgres

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> ExecuteResult:
        adapted_sql = sql
        insert_returning = False
        if self._postgres:
            adapted_sql = sql.replace("?", "%s")
            stripped = sql.strip().upper()
            if stripped.startswith("INSERT") and "RETURNING" not in stripped:
                adapted_sql = adapted_sql.rstrip().rstrip(";") + " RETURNING id"
                insert_returning = True
        cursor = self._conn.cursor()
        cursor.execute(adapted_sql, tuple(params))
        return ExecuteResult(cursor, self._postgres, insert_returning)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


@contextmanager
def db_connection() -> Iterator[DbConnection]:
    postgres = is_cloud_database()
    raw: Any
    if postgres:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        url = get_database_url()
        assert url is not None
        raw = psycopg2.connect(url, cursor_factory=RealDictCursor)
    else:
        path = get_sqlite_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(path, check_same_thread=False)
        raw.row_factory = sqlite3.Row

    connection = DbConnection(raw, postgres)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        raw.close()


def init_database() -> None:
    with db_connection() as connection:
        if is_cloud_database():
            for statement in _POSTGRES_STATEMENTS:
                connection.execute(statement)
        else:
            connection._conn.executescript(_SQLITE_SCHEMA)  # noqa: SLF001

        row = connection.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )


def row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def ensure_default_family() -> int:
    init_database()
    with db_connection() as connection:
        row = connection.execute("SELECT id FROM family ORDER BY id LIMIT 1").fetchone()
        if row:
            return int(row["id"])
        now = _utc_now()
        cursor = connection.execute(
            "INSERT INTO family (name, created_at) VALUES (?, ?)",
            ("Default Family", now),
        )
        new_id = cursor.lastrowid
        assert new_id is not None
        return int(new_id)
