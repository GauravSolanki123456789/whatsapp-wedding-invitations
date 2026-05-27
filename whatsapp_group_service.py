"""Create WhatsApp groups from the guest list (auto on laptop, quick on phone)."""

from __future__ import annotations

from dataclasses import dataclass, field

from constants import WHATSAPP_MAX_GROUP_PARTICIPANTS
from whatsapp_selenium import WhatsAppSession, friendly_error
from whatsapp_service import get_active_session, start_send_session, stop_send_session


@dataclass
class GroupCreateResult:
    group_name: str
    success: bool
    added_count: int
    skipped_numbers: list[str] = field(default_factory=list)
    detail: str = ""


def validate_group_request(
    mobile_numbers: list[str],
    group_name: str,
    invalid_count: int,
) -> str | None:
    if not group_name.strip():
        return "Enter a group name."
    if not mobile_numbers:
        return "Add guest numbers in step 2 first."
    if invalid_count:
        return (
            f"{invalid_count} number(s) are invalid. "
            "Fix them before creating a group."
        )
    if len(mobile_numbers) > WHATSAPP_MAX_GROUP_PARTICIPANTS:
        return (
            f"WhatsApp allows up to {WHATSAPP_MAX_GROUP_PARTICIPANTS} members when "
            f"creating a group. You have {len(mobile_numbers)} guests — remove some or "
            "create two smaller groups."
        )
    return None


def create_whatsapp_group(group_name: str, mobile_numbers: list[str]) -> GroupCreateResult:
    """Auto-create a group in the automation Chrome window."""
    try:
        start_send_session()
        session = _require_session()
        stats = session.create_group(group_name.strip(), mobile_numbers)
        added = len(stats["added"])
        skipped = stats["skipped"]
        if added == 0:
            return GroupCreateResult(
                group_name=group_name,
                success=False,
                added_count=0,
                skipped_numbers=skipped,
                detail=(
                    "Could not add any guests. Numbers must exist on WhatsApp — "
                    "try Quick Group on your phone (import contacts first)."
                ),
            )
        detail = f"Created group **{group_name}** with **{added}** member(s)."
        if skipped:
            detail += f" {len(skipped)} could not be found (not saved on WhatsApp Web)."
        return GroupCreateResult(
            group_name=group_name,
            success=True,
            added_count=added,
            skipped_numbers=skipped,
            detail=detail,
        )
    except Exception as exc:
        return GroupCreateResult(
            group_name=group_name,
            success=False,
            added_count=0,
            detail=friendly_error(exc),
        )
    finally:
        stop_send_session()


def _require_session() -> WhatsAppSession:
    session = get_active_session()
    if session is None or session.driver is None:
        raise RuntimeError("WhatsApp browser session is not started.")
    return session
