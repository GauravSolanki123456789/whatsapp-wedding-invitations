"""CRUD for wedding families (multi-tenant)."""

from __future__ import annotations

import streamlit as st

from database import _utc_now, apply_schema_migrations, db_connection, invalidate_families_cache, row_to_dict
from constants import WHATSAPP_APP_TYPE_COLUMN, WHATSAPP_SENDER_PHONE_COLUMN


def _fetch_families() -> list[dict]:
    with db_connection() as connection:
        apply_schema_migrations(connection)
        rows = connection.execute(
            f"""
            SELECT id, name, created_at,
                   {WHATSAPP_SENDER_PHONE_COLUMN}, {WHATSAPP_APP_TYPE_COLUMN}
            FROM family ORDER BY name
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]  # type: ignore[misc]


def list_families() -> list[dict]:
    cached = st.session_state.get("families_cache")
    if cached is not None:
        return cached
    families = _fetch_families()
    st.session_state["families_cache"] = families
    return families


def create_family(name: str) -> tuple[int | None, str | None]:
    name = name.strip()
    if not name:
        return None, "Family name is required."
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO family (name, created_at) VALUES (?, ?)",
                (name, _utc_now()),
            )
            invalidate_families_cache()
            return int(cursor.lastrowid), None
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return None, f"Family '{name}' already exists."
        return None, str(exc)


def delete_family(family_id: int) -> str | None:
    families = list_families()
    if len(families) <= 1:
        return "Cannot delete the only family."
    with db_connection() as connection:
        connection.execute("DELETE FROM family WHERE id = ?", (family_id,))
    invalidate_families_cache()
    return None


def get_family(family_id: int) -> dict | None:
    for family in list_families():
        if family["id"] == family_id:
            return family
    with db_connection() as connection:
        row = connection.execute(
            f"""
            SELECT id, name, created_at,
                   {WHATSAPP_SENDER_PHONE_COLUMN}, {WHATSAPP_APP_TYPE_COLUMN}
            FROM family WHERE id = ?
            """,
            (family_id,),
        ).fetchone()
    return row_to_dict(row)


def update_family_whatsapp_settings(
    family_id: int,
    sender_phone: str,
    app_type: str,
) -> str | None:
    try:
        with db_connection() as connection:
            connection.execute(
                f"""
                UPDATE family
                SET {WHATSAPP_SENDER_PHONE_COLUMN} = ?, {WHATSAPP_APP_TYPE_COLUMN} = ?
                WHERE id = ?
                """,
                (sender_phone.strip(), app_type.strip(), family_id),
            )
        invalidate_families_cache()
        return None
    except Exception as exc:
        return str(exc)


def get_or_create_family_id(family_id: int | None) -> int:
    from database import ensure_default_family

    if family_id:
        family = get_family(family_id)
        if family:
            return family_id
    return ensure_default_family()
