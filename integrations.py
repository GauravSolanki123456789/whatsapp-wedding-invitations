"""Optional WhatsApp Cloud API and voice-call integrations (env-based)."""

from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass
class IntegrationStatus:
    whatsapp_api: bool
    voice_calls: bool
    whatsapp_detail: str
    voice_detail: str


def integration_status() -> IntegrationStatus:
    wa_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    wa_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    twilio_from = os.environ.get("TWILIO_CALL_FROM_NUMBER", "").strip()

    wa_ok = bool(wa_token and wa_phone_id)
    voice_ok = bool(twilio_sid and twilio_token and twilio_from)

    return IntegrationStatus(
        whatsapp_api=wa_ok,
        voice_calls=voice_ok,
        whatsapp_detail=(
            "Configured — bulk API send available."
            if wa_ok
            else "Add WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID in Streamlit Secrets."
        ),
        voice_detail=(
            "Configured — Twilio calls available."
            if voice_ok
            else "Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_CALL_FROM_NUMBER in Secrets."
        ),
    )


def send_whatsapp_template_message(
    mobile_number: str,
    template_name: str,
    language_code: str = "en",
) -> tuple[bool, str]:
    """Send approved template via Meta Cloud API (requires Business verification)."""
    token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    if not token or not phone_id:
        return False, "WhatsApp API not configured."

    phone = mobile_number.lstrip("+").replace(" ", "")
    url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if response.status_code in (200, 201):
            return True, "Sent"
        return False, response.text[:500]
    except Exception as exc:
        return False, str(exc)


def place_invitation_call(mobile_number: str, twiml_url: str) -> tuple[bool, str]:
    """Outbound call via Twilio (TwiML URL plays your recorded message)."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.environ.get("TWILIO_CALL_FROM_NUMBER", "").strip()
    if not all([sid, token, from_number]):
        return False, "Twilio not configured."

    try:
        from twilio.rest import Client

        client = Client(sid, token)
        call = client.calls.create(to=mobile_number, from_=from_number, url=twiml_url)
        return True, call.sid
    except ImportError:
        return False, "Install twilio: pip install twilio"
    except Exception as exc:
        return False, str(exc)
