"""Gift functions, QR tokens, scanning, and reports."""

from __future__ import annotations

import io
import uuid
from typing import Any

import pandas as pd

from database import _utc_now, db_connection, init_database, row_to_dict
from constants import (
    GIFT_QUANTITY_COLUMN,
    GUEST_NAME_COLUMN,
    MOBILE_NUMBER_COLUMN,
    QR_TOKEN_PREFIX,
)
from utils import normalize_mobile_number


def list_functions(family_id: int) -> list[dict]:
    init_database()
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT ef.id, ef.name, ef.created_at,
                   COUNT(gg.id) AS guest_count
            FROM event_function ef
            LEFT JOIN gift_guest gg ON gg.event_function_id = ef.id
            WHERE ef.family_id = ?
            GROUP BY ef.id
            ORDER BY ef.name
            """,
            (family_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]  # type: ignore[misc]


def create_function(family_id: int, name: str) -> tuple[int | None, str | None]:
    name = name.strip()
    if not name:
        return None, "Function name is required."
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO event_function (family_id, name, created_at) VALUES (?, ?, ?)",
                (family_id, name, _utc_now()),
            )
            return int(cursor.lastrowid), None
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return None, f"Function '{name}' already exists."
        return None, str(exc)


def delete_function(function_id: int) -> None:
    with db_connection() as connection:
        connection.execute("DELETE FROM event_function WHERE id = ?", (function_id,))


def _new_qr_token() -> str:
    return f"{QR_TOKEN_PREFIX}{uuid.uuid4().hex[:16]}"


def import_gift_guests_from_excel(
    function_id: int,
    file_bytes: bytes,
    country_code: str,
    replace_existing: bool = False,
) -> tuple[int, str | None]:
    buffer = io.BytesIO(file_bytes)
    dataframe = pd.read_excel(buffer, engine="openpyxl", header=0)
    guests = _parse_gift_excel(dataframe, country_code)
    if not guests:
        return 0, "No valid guests found. Use the sample Excel format."

    with db_connection() as connection:
        if replace_existing:
            connection.execute(
                "DELETE FROM gift_guest WHERE event_function_id = ?",
                (function_id,),
            )
        now = _utc_now()
        added = 0
        for guest in guests:
            token = _new_qr_token()
            try:
                connection.execute(
                    """
                    INSERT INTO gift_guest
                        (event_function_id, guest_name, mobile_number,
                         gift_quantity, qr_token, gifts_given, created_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        function_id,
                        guest[GUEST_NAME_COLUMN],
                        guest[MOBILE_NUMBER_COLUMN],
                        guest[GIFT_QUANTITY_COLUMN],
                        token,
                        now,
                    ),
                )
                added += 1
            except Exception:
                continue
    return added, None


def _parse_gift_excel(dataframe: pd.DataFrame, country_code: str) -> list[dict[str, Any]]:
    name_col = _find_col(dataframe, ["guest_name", "name", "guest"])
    mobile_col = _find_col(dataframe, ["mobile_number", "mobile", "phone", "number"])
    qty_col = _find_col(dataframe, ["gift_quantity", "quantity", "gifts", "qty"])

    guests: list[dict[str, Any]] = []
    if mobile_col:
        for _, row in dataframe.iterrows():
            mobile = normalize_mobile_number(row[mobile_col], country_code)
            if not mobile:
                continue
            name = ""
            if name_col and pd.notna(row[name_col]):
                name = str(row[name_col]).strip()
                if name.lower() in {"nan", "none"}:
                    name = ""
            qty = 1
            if qty_col and pd.notna(row[qty_col]):
                try:
                    qty = max(1, int(float(row[qty_col])))
                except (TypeError, ValueError):
                    qty = 1
            guests.append(
                {
                    GUEST_NAME_COLUMN: name,
                    MOBILE_NUMBER_COLUMN: mobile,
                    GIFT_QUANTITY_COLUMN: qty,
                }
            )
    elif dataframe.shape[1] >= 2:
        for _, row in dataframe.iterrows():
            raw_name = row.iloc[0]
            raw_mobile = row.iloc[1]
            mobile = normalize_mobile_number(raw_mobile, country_code)
            if not mobile:
                continue
            name = str(raw_name).strip() if pd.notna(raw_name) else ""
            if name.lower() in {"nan", "none"}:
                name = ""
            qty = 1
            if dataframe.shape[1] >= 3 and pd.notna(row.iloc[2]):
                try:
                    qty = max(1, int(float(row.iloc[2])))
                except (TypeError, ValueError):
                    qty = 1
            guests.append(
                {
                    GUEST_NAME_COLUMN: name,
                    MOBILE_NUMBER_COLUMN: mobile,
                    GIFT_QUANTITY_COLUMN: qty,
                }
            )
    return guests


def _find_col(dataframe: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in dataframe.columns:
        key = str(column).strip().lower().replace(" ", "_")
        if key in candidates or any(candidate in key for candidate in candidates):
            return column
    return None


def list_gift_guests(function_id: int) -> list[dict]:
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, guest_name, mobile_number, gift_quantity,
                   qr_token, gifts_given, created_at
            FROM gift_guest
            WHERE event_function_id = ?
            ORDER BY guest_name, mobile_number
            """,
            (function_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = row_to_dict(row)
        if item:
            item["gifts_pending"] = max(0, item["gift_quantity"] - item["gifts_given"])
            result.append(item)
    return result


def get_guest_by_token(qr_token: str) -> dict | None:
    token = qr_token.strip()
    if not token.startswith(QR_TOKEN_PREFIX):
        token = f"{QR_TOKEN_PREFIX}{token}" if token else token
    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT gg.*, ef.name AS function_name, f.name AS family_name
            FROM gift_guest gg
            JOIN event_function ef ON ef.id = gg.event_function_id
            JOIN family f ON f.id = ef.family_id
            WHERE gg.qr_token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        return None
    data = row_to_dict(row)
    if data:
        data["gifts_pending"] = max(0, data["gift_quantity"] - data["gifts_given"])
    return data


def record_gift_handout(
    gift_guest_id: int,
    gifts_to_give: int,
    scanned_by: str = "",
    notes: str = "",
) -> tuple[bool, str, dict | None]:
    """Atomic handout — safe when multiple staff scan the same QR on different phones."""
    if gifts_to_give < 1:
        return False, "Enter at least 1 gift.", None

    qr_token: str | None = None
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM gift_guest WHERE id = ?",
            (gift_guest_id,),
        ).fetchone()
        if not row:
            return False, "Guest not found.", None
        guest = row_to_dict(row)
        assert guest is not None
        qr_token = guest["qr_token"]
        pending = guest["gift_quantity"] - guest["gifts_given"]
        if pending <= 0:
            return False, "All gifts already given for this QR.", guest
        if gifts_to_give > pending:
            return (
                False,
                f"Only {pending} gift(s) remaining. Cannot give {gifts_to_give}.",
                guest,
            )

        updated = connection.execute(
            """
            UPDATE gift_guest
            SET gifts_given = gifts_given + ?
            WHERE id = ?
              AND gifts_given + ? <= gift_quantity
            """,
            (gifts_to_give, gift_guest_id, gifts_to_give),
        )
        if updated.rowcount == 0:
            fresh = connection.execute(
                "SELECT * FROM gift_guest WHERE id = ?",
                (gift_guest_id,),
            ).fetchone()
            fresh_guest = row_to_dict(fresh)
            remaining = 0
            if fresh_guest:
                remaining = max(0, fresh_guest["gift_quantity"] - fresh_guest["gifts_given"])
            if remaining <= 0:
                return False, "All gifts already given (another staff member just scanned).", fresh_guest
            return (
                False,
                f"Only {remaining} gift(s) left now — another phone may have scanned first.",
                fresh_guest,
            )

        connection.execute(
            """
            INSERT INTO gift_scan
                (gift_guest_id, gifts_given, scanned_at, scanned_by, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (gift_guest_id, gifts_to_give, _utc_now(), scanned_by.strip(), notes.strip()),
        )

    updated_guest = get_guest_by_token(qr_token) if qr_token else None
    return True, f"Recorded {gifts_to_give} gift(s).", updated_guest


def function_report(function_id: int) -> dict[str, Any]:
    guests = list_gift_guests(function_id)
    total_guests = len(guests)
    total_allocated = sum(g["gift_quantity"] for g in guests)
    total_given = sum(g["gifts_given"] for g in guests)
    total_pending = sum(g["gifts_pending"] for g in guests)
    fully_done = sum(1 for g in guests if g["gifts_pending"] == 0)
    return {
        "total_guests": total_guests,
        "total_allocated": total_allocated,
        "total_given": total_given,
        "total_pending": total_pending,
        "fully_completed_guests": fully_done,
        "guests": guests,
    }


def regenerate_all_qr_tokens(function_id: int) -> int:
    """Assign new tokens to all guests (invalidates old QR images)."""
    with db_connection() as connection:
        rows = connection.execute(
            "SELECT id FROM gift_guest WHERE event_function_id = ?",
            (function_id,),
        ).fetchall()
        count = 0
        for row in rows:
            connection.execute(
                "UPDATE gift_guest SET qr_token = ?, gifts_given = 0 WHERE id = ?",
                (_new_qr_token(), row["id"]),
            )
            connection.execute(
                "DELETE FROM gift_scan WHERE gift_guest_id = ?",
                (row["id"],),
            )
            count += 1
    return count
