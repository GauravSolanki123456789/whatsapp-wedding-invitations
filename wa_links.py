"""Build WhatsApp deep links used across manual and automated sending."""

from __future__ import annotations

from urllib.parse import quote

from constants import WHATSAPP_APP_BUSINESS, WHATSAPP_APP_PERSONAL
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


def wa_personal_android_link(mobile_number: str, message: str = "") -> str:
    """Android intent — opens WhatsApp (personal) instead of Business."""
    phone = phone_for_wa_link(mobile_number)
    text = quote(message) if message.strip() else ""
    intent = f"intent://send?phone={phone}"
    if text:
        intent += f"&text={text}"
    return intent + "#Intent;scheme=whatsapp;package=com.whatsapp;end"


def wa_business_android_link(mobile_number: str, message: str = "") -> str:
    """Android intent — opens WhatsApp Business when installed."""
    phone = phone_for_wa_link(mobile_number)
    text = quote(message) if message.strip() else ""
    intent = f"intent://send?phone={phone}"
    if text:
        intent += f"&text={text}"
    return intent + "#Intent;scheme=whatsapp;package=com.whatsapp.w4b;end"


def whatsapp_guest_link(
    guest_mobile_number: str,
    message: str = "",
    app_type: str = WHATSAPP_APP_PERSONAL,
    sender_phone: str = "",
) -> str:
    """
    Link to message a guest on WhatsApp.

    If sender_phone is empty, use wa.me (phone default — usually Business if that was last used).
    If sender_phone is set, open the chosen app (Personal vs Business) via Android intent.
    """
    if not (sender_phone or "").strip():
        return wa_me_link(guest_mobile_number, message)
    if app_type == WHATSAPP_APP_BUSINESS:
        return wa_business_android_link(guest_mobile_number, message)
    return wa_personal_android_link(guest_mobile_number, message)
