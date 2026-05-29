"""CRUD for wedding families (multi-tenant)."""

from __future__ import annotations

import streamlit as st

from database import _utc_now, db_connection, invalidate_families_cache, row_to_dict


def _fetch_families() -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, created_at FROM family ORDER BY name"
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


def rename_family(family_id: int, name: str) -> str | None:
    name = name.strip()
    if not name:
        return "Family name is required."
    try:
        with db_connection() as connection:
            connection.execute(
                "UPDATE family SET name = ? WHERE id = ?",
                (name, family_id),
            )
        invalidate_families_cache()
        return None
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return f"Family '{name}' already exists."
        return str(exc)


def delete_family(family_id: int) -> str | None:
    families = list_families()
    if len(families) <= 1:
        return "Cannot delete the only family."
    with db_connection() as connection:
        connection.execute("DELETE FROM family WHERE id = ?", (family_id,))
    invalidate_families_cache()
    return None


def get_family(family_id: int) -> dict | None:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT id, name, created_at FROM family WHERE id = ?",
            (family_id,),
        ).fetchone()
    return row_to_dict(row)


def get_or_create_family_id(family_id: int | None) -> int:
    from database import ensure_default_family

    if family_id:
        family = get_family(family_id)
        if family:
            return family_id
    return ensure_default_family()
