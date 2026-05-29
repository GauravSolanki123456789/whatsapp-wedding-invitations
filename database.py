"""SQLite persistence for families, guest lists, functions, and gift tracking."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from constants import DATABASE_FILE

_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_database_path() -> str:
    env_path = os.environ.get("DATABASE_URL", "").strip()
    if env_path.startswith("sqlite:///"):
        return env_path.replace("sqlite:///", "", 1)
    return DATABASE_FILE


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    path = get_database_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database() -> None:
    with db_connection() as connection:
        connection.executescript(
            """
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

            CREATE INDEX IF NOT EXISTS idx_guest_list_member_list
                ON guest_list_member(guest_list_id);
            CREATE INDEX IF NOT EXISTS idx_gift_guest_function
                ON gift_guest(event_function_id);
            CREATE INDEX IF NOT EXISTS idx_gift_guest_token
                ON gift_guest(qr_token);
            """
        )
        row = connection.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ).fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def ensure_default_family() -> int:
    """Return active family id, creating 'Default Family' if none exist."""
    init_database()
    with db_connection() as connection:
        row = connection.execute(
            "SELECT id FROM family ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            return int(row["id"])
        now = _utc_now()
        cursor = connection.execute(
            "INSERT INTO family (name, created_at) VALUES (?, ?)",
            ("Default Family", now),
        )
        return int(cursor.lastrowid)
