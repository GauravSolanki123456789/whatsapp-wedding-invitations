"""WhatsApp message sending through a single Selenium browser session."""

from __future__ import annotations

import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from constants import DELAY_MAX_SECONDS, DELAY_MIN_SECONDS
from utils import validate_attachment_for_whatsapp
from whatsapp_selenium import WhatsAppSession, attachment_kind, friendly_error

_active_session: WhatsAppSession | None = None
_delay_min_seconds = DELAY_MIN_SECONDS
_delay_max_seconds = DELAY_MAX_SECONDS


@dataclass
class SendResult:
    mobile_number: str
    success: bool
    detail: str


def configure_delays(min_seconds: int, max_seconds: int) -> None:
    global _delay_min_seconds, _delay_max_seconds
    _delay_min_seconds = min_seconds
    _delay_max_seconds = max(max_seconds, min_seconds + 1)


def start_send_session() -> None:
    global _active_session
    if _active_session is None:
        _active_session = WhatsAppSession()
        _active_session.start()


def stop_send_session() -> None:
    global _active_session
    if _active_session is not None:
        _active_session.stop()
        _active_session = None


def _detail_for_attachment(attachment_path: str) -> str:
    kind = attachment_kind(attachment_path)
    return {
        "image": "Sent with image",
        "document": "Sent with document",
        "video": "Sent with video",
    }[kind]


def send_whatsapp_message(
    mobile_number: str,
    message: str,
    attachment_path: str | None = None,
) -> SendResult:
    """Send one WhatsApp message through the automation browser."""
    try:
        if attachment_path and not os.path.exists(attachment_path):
            raise FileNotFoundError(f"Attachment not found: {attachment_path}")

        if attachment_path:
            size_error = validate_attachment_for_whatsapp(attachment_path)
            if size_error:
                raise ValueError(size_error)

        if _active_session is None:
            start_send_session()

        _active_session.send(mobile_number, message, attachment_path)

        if attachment_path:
            detail = _detail_for_attachment(attachment_path)
        else:
            detail = "Sent"

        return SendResult(mobile_number=mobile_number, success=True, detail=detail)
    except Exception as exc:
        if _active_session is not None:
            try:
                _active_session.dismiss_stale_ui()
            except Exception:
                pass
        return SendResult(
            mobile_number=mobile_number,
            success=False,
            detail=friendly_error(exc),
        )


def delay_between_messages() -> float:
    return random.uniform(_delay_min_seconds, _delay_max_seconds)


def wait_with_countdown(
    seconds: float,
    on_tick: Callable[[int], None] | None = None,
) -> None:
    remaining = int(seconds)
    while remaining > 0:
        if on_tick:
            on_tick(remaining)
        time.sleep(1)
        remaining -= 1
