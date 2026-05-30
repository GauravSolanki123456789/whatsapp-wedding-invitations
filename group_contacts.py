"""Helpers for creating WhatsApp groups on phone (vCard import) and in the app."""

from __future__ import annotations

import re

from constants import GROUP_CONTACT_NAME_PREFIX, GUEST_NAME_COLUMN, MOBILE_NUMBER_COLUMN


def _vcard_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def format_vcard_contact_name(guest_name: str, list_label: str, index: int) -> str:
    """
    Build the phone contact name shown after importing the .vcf file.

    Example: guest_name="INDRA BAI JI RANKA", list_label="Rankalist"
    → "INDRA BAI JI RANKA Rankalist"
    """
    base = (guest_name or "").strip()
    if not base:
        base = f"{GROUP_CONTACT_NAME_PREFIX} {index}"

    label = (list_label or "").strip()
    if label:
        return f"{base} {label}"
    return base


def build_guest_vcard(
    guests: list[dict[str, str]],
    list_label: str = "",
) -> str:
    """Build a vCard file for importing guests as phone contacts."""
    blocks: list[str] = []
    for index, guest in enumerate(guests, start=1):
        mobile_number = str(guest.get(MOBILE_NUMBER_COLUMN, "")).strip()
        if not mobile_number:
            continue
        name = format_vcard_contact_name(
            str(guest.get(GUEST_NAME_COLUMN, "") or ""),
            list_label,
            index,
        )
        safe_name = _vcard_escape(name)
        blocks.extend(
            [
                "BEGIN:VCARD",
                "VERSION:3.0",
                f"FN:{safe_name}",
                f"N:;{safe_name};;;",
                f"TEL;TYPE=CELL:{mobile_number}",
                "END:VCARD",
            ]
        )
    return "\r\n".join(blocks) + "\r\n"


def vcard_download_filename(list_label: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", (list_label or "guests").strip().lower()).strip("_")
    return f"{slug or 'guests'}_contacts.vcf"


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
