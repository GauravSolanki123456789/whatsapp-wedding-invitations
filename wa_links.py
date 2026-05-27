"""Build WhatsApp deep links used across manual and automated sending."""

from __future__ import annotations

from urllib.parse import quote

from utils import phone_for_wa_link


def wa_me_link(mobile_number: str, message: str = "") -> str:
    """Mobile-friendly link — opens the WhatsApp app with pre-filled text."""
    phone = phone_for_wa_link(mobile_number)
    if message.strip():
        return f"https://wa.me/{phone}?text={quote(message)}"
    return f"https://wa.me/{phone}"


def whatsapp_web_link(mobile_number: str, message: str = "") -> str:
    """Desktop browser link — opens WhatsApp Web for a phone number."""
    phone = phone_for_wa_link(mobile_number)
    url = f"https://web.whatsapp.com/send?phone={phone}&type=phone_number&app_absent=0"
    if message.strip():
        url = f"{url}&text={quote(message)}"
    return url


def api_whatsapp_link(mobile_number: str, message: str = "") -> str:
    """Alternative link format that works in some mobile browsers."""
    phone = phone_for_wa_link(mobile_number)
    if message.strip():
        return f"https://api.whatsapp.com/send?phone={phone}&text={quote(message)}"
    return f"https://api.whatsapp.com/send?phone={phone}"
