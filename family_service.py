"""CRUD for wedding families (multi-tenant)."""

from __future__ import annotations

from database import _utc_now, db_connection, ensure_default_family, init_database, row_to_dict


def list_families() -> list[dict]:
    init_database()
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, created_at FROM family ORDER BY name"
        ).fetchall()
    return [row_to_dict(row) for row in rows]  # type: ignore[misc]


def create_family(name: str) -> tuple[int | None, str | None]:
    name = name.strip()
    if not name:
        return None, "Family name is required."
    init_database()
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO family (name, created_at) VALUES (?, ?)",
                (name, _utc_now()),
            )
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
    return None


def get_family(family_id: int) -> dict | None:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT id, name, created_at FROM family WHERE id = ?",
            (family_id,),
        ).fetchone()
    return row_to_dict(row)


def get_or_create_family_id(family_id: int | None) -> int:
    if family_id:
        family = get_family(family_id)
        if family:
            return family_id
    return ensure_default_family()
