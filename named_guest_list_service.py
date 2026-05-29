"""Named guest lists per family (Ranka Invitations, Solanki Invitations, etc.)."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from database import _utc_now, db_connection, invalidate_guest_lists_cache, row_to_dict
from constants import GUEST_NAME_COLUMN, GIFT_QUANTITY_COLUMN, MOBILE_NUMBER_COLUMN
from utils import normalize_mobile_number


def _fetch_guest_lists(family_id: int) -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT gl.id, gl.name, gl.created_at,
                   COUNT(glm.id) AS member_count
            FROM guest_list gl
            LEFT JOIN guest_list_member glm ON glm.guest_list_id = gl.id
            WHERE gl.family_id = ?
            GROUP BY gl.id
            ORDER BY gl.name
            """,
            (family_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]  # type: ignore[misc]


def list_guest_lists(family_id: int) -> list[dict]:
    import streamlit as st

    cache_key = f"guest_lists_cache_{family_id}"
    cached = st.session_state.get(cache_key)
    if cached is not None:
        return cached
    lists = _fetch_guest_lists(family_id)
    st.session_state[cache_key] = lists
    return lists


def create_guest_list(family_id: int, name: str) -> tuple[int | None, str | None]:
    name = name.strip()
    if not name:
        return None, "List name is required."
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO guest_list (family_id, name, created_at) VALUES (?, ?, ?)",
                (family_id, name, _utc_now()),
            )
            invalidate_guest_lists_cache(family_id)
            return int(cursor.lastrowid), None
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return None, f"List '{name}' already exists for this family."
        return None, str(exc)


def delete_guest_list(guest_list_id: int, family_id: int | None = None) -> None:
    with db_connection() as connection:
        connection.execute("DELETE FROM guest_list WHERE id = ?", (guest_list_id,))
    if family_id is not None:
        invalidate_guest_lists_cache(family_id)
    else:
        invalidate_guest_lists_cache()


def get_guest_list_members(guest_list_id: int) -> pd.DataFrame:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT guest_name, mobile_number
            FROM guest_list_member
            WHERE guest_list_id = ?
            ORDER BY id
            """,
            (guest_list_id,),
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=[GUEST_NAME_COLUMN, MOBILE_NUMBER_COLUMN])
    return pd.DataFrame(
        {
            GUEST_NAME_COLUMN: [row["guest_name"] for row in rows],
            MOBILE_NUMBER_COLUMN: [row["mobile_number"] for row in rows],
        }
    )


def replace_guest_list_members(
    guest_list_id: int,
    members: list[dict[str, str]],
) -> None:
    with db_connection() as connection:
        connection.execute(
            "DELETE FROM guest_list_member WHERE guest_list_id = ?",
            (guest_list_id,),
        )
        now = _utc_now()
        for member in members:
            connection.execute(
                """
                INSERT INTO guest_list_member
                    (guest_list_id, guest_name, mobile_number, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    guest_list_id,
                    member.get(GUEST_NAME_COLUMN, "") or "",
                    member[MOBILE_NUMBER_COLUMN],
                    now,
                ),
            )


def import_excel_to_guest_list(
    guest_list_id: int,
    file_bytes: bytes,
    country_code: str,
    family_id: int | None = None,
) -> tuple[int, str | None]:
    from utils import parse_guest_rows_from_excel

    members, error = parse_guest_rows_from_excel(file_bytes, country_code)
    if error:
        return 0, error

    replace_guest_list_members(guest_list_id, members)
    invalidate_guest_lists_cache(family_id)
    return len(members), None


def members_to_mobile_numbers(members_df: pd.DataFrame, country_code: str) -> list[str]:
    numbers: list[str] = []
    seen: set[str] = set()
    if members_df is None or members_df.empty:
        return numbers
    for _, row in members_df.iterrows():
        raw = row.get(MOBILE_NUMBER_COLUMN, "")
        normalized = normalize_mobile_number(raw, country_code) or str(raw).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            numbers.append(normalized)
    return numbers

