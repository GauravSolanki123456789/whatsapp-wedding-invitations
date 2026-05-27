"""Helpers for creating WhatsApp groups on phone (vCard import) and in the app."""

from __future__ import annotations

from constants import GROUP_CONTACT_NAME_PREFIX, MOBILE_NUMBER_COLUMN
from utils import phone_for_wa_link


def guest_contact_name(index: int) -> str:
    return f"{GROUP_CONTACT_NAME_PREFIX} {index}"


def build_guest_vcard(mobile_numbers: list[str]) -> str:
    """Build a vCard file body for importing all guests as phone contacts."""
    blocks: list[str] = []
    for index, mobile_number in enumerate(mobile_numbers, start=1):
        name = guest_contact_name(index)
        blocks.extend(
            [
                "BEGIN:VCARD",
                "VERSION:3.0",
                f"FN:{name}",
                f"N:;{name};;;",
                f"TEL;TYPE=CELL:{mobile_number}",
                "END:VCARD",
            ]
        )
    return "\r\n".join(blocks) + "\r\n"


def numbers_for_clipboard(mobile_numbers: list[str]) -> str:
    """One number per line — easy to copy on phone or laptop."""
    return "\n".join(mobile_numbers)


def group_creation_summary_rows(
    added: list[str],
    skipped: list[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for number in added:
        rows.append({MOBILE_NUMBER_COLUMN: number, "status": "Added"})
    for number in skipped:
        rows.append({MOBILE_NUMBER_COLUMN: number, "status": "Not found in WhatsApp"})
    return rows
