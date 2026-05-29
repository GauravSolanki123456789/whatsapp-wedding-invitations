"""Named guest lists per family (Ranka Invitations, Solanki Invitations, etc.)."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from database import _utc_now, db_connection, init_database, row_to_dict
from constants import GUEST_NAME_COLUMN, GIFT_QUANTITY_COLUMN, MOBILE_NUMBER_COLUMN
from utils import normalize_mobile_number


def list_guest_lists(family_id: int) -> list[dict]:
    init_database()
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
            return int(cursor.lastrowid), None
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return None, f"List '{name}' already exists for this family."
        return None, str(exc)


def delete_guest_list(guest_list_id: int) -> None:
    with db_connection() as connection:
        connection.execute("DELETE FROM guest_list WHERE id = ?", (guest_list_id,))


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
) -> tuple[int, str | None]:
    buffer = io.BytesIO(file_bytes)
    dataframe = pd.read_excel(buffer, engine="openpyxl", header=0)

    members: list[dict[str, str]] = []
    columns_lower = [str(column).strip().lower() for column in dataframe.columns]

    if MOBILE_NUMBER_COLUMN in columns_lower or "mobile" in " ".join(columns_lower):
        name_col = _find_column(dataframe, ["guest_name", "name", "guest"])
        mobile_col = _find_column(dataframe, ["mobile_number", "mobile", "phone", "number"])
        qty_col = _find_column(dataframe, ["gift_quantity", "quantity", "gifts", "qty"])
        for _, row in dataframe.iterrows():
            raw_mobile = row[mobile_col] if mobile_col else None
            mobile = normalize_mobile_number(raw_mobile, country_code)
            if not mobile:
                continue
            guest_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ""
            if guest_name.lower() in {"nan", "none"}:
                guest_name = ""
            members.append({GUEST_NAME_COLUMN: guest_name, MOBILE_NUMBER_COLUMN: mobile})
    else:
        if dataframe.shape[1] < 2:
            return 0, "Excel needs at least 2 columns (name optional in col 1, mobile in col 2)."
        for _, row in dataframe.iterrows():
            raw_name = row.iloc[0] if dataframe.shape[1] >= 2 else ""
            raw_mobile = row.iloc[1]
            mobile = normalize_mobile_number(raw_mobile, country_code)
            if not mobile:
                continue
            guest_name = str(raw_name).strip() if pd.notna(raw_name) else ""
            if guest_name.lower() in {"nan", "none"}:
                guest_name = ""
            members.append({GUEST_NAME_COLUMN: guest_name, MOBILE_NUMBER_COLUMN: mobile})

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for member in members:
        number = member[MOBILE_NUMBER_COLUMN]
        if number not in seen:
            seen.add(number)
            unique.append(member)

    replace_guest_list_members(guest_list_id, unique)
    return len(unique), None


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


def _find_column(dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in dataframe.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key in candidates or any(candidate in key for candidate in candidates):
            return column
    return None
