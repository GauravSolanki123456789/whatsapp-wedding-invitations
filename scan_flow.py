"""Scan tab logic — auto lookup, handout, reset for next guest."""

from __future__ import annotations

import hashlib

import streamlit as st

from constants import (
    QUERY_PARAM_SCAN_TOKEN,
    SESSION_LAST_PROCESSED_SCAN_PAYLOAD,
    SESSION_LAST_SCAN_TOKEN,
    SESSION_SCAN_LOOKUP_GUEST,
    SESSION_SCAN_PHOTO_KEY,
    SESSION_SCAN_PASTE_KEY,
    SESSION_SCAN_UPLOAD_KEY,
    SESSION_SCANNER_STAFF_NAME,
)
from gift_service import get_guest_by_token, record_gift_handout
from qr_utils import parse_scanned_payload


def lookup_guest_from_raw(raw: str) -> tuple[dict | None, str | None]:
    token = parse_scanned_payload(raw)
    if not token:
        return None, "Could not read a valid QR code."
    guest = get_guest_by_token(token)
    if not guest:
        return None, "QR not found. Check the correct family/function or regenerate QRs."
    return guest, None


def apply_scan_raw(raw: str) -> str | None:
    """Store guest in session from scanned text. Returns error message or None."""
    guest, error = lookup_guest_from_raw(raw)
    if error:
        return error
    st.session_state[SESSION_SCAN_LOOKUP_GUEST] = guest
    token = parse_scanned_payload(raw)
    if token:
        st.session_state[SESSION_LAST_SCAN_TOKEN] = token
    return None


def consume_query_param_scan() -> None:
    """Apply scan_token from URL (live scanner navigates parent here)."""
    raw = st.query_params.get(QUERY_PARAM_SCAN_TOKEN)
    if not raw:
        return
    token_str = raw if isinstance(raw, str) else raw[0]
    if token_str == st.session_state.get(SESSION_LAST_SCAN_TOKEN) and st.session_state.get(
        SESSION_SCAN_LOOKUP_GUEST
    ):
        return
    error = apply_scan_raw(token_str)
    if error:
        st.session_state["scan_last_error"] = error
    else:
        st.session_state.pop("scan_last_error", None)


def process_image_bytes(image_bytes: bytes) -> bool:
    """Decode QR from image; auto-lookup if new image. Returns True if lookup ran."""
    from scanner_component import decode_qr_from_image

    digest = hashlib.md5(image_bytes).hexdigest()
    if digest == st.session_state.get(SESSION_LAST_PROCESSED_SCAN_PAYLOAD):
        return False
    st.session_state[SESSION_LAST_PROCESSED_SCAN_PAYLOAD] = digest
    decoded = decode_qr_from_image(image_bytes)
    if not decoded:
        st.session_state["scan_last_error"] = "No QR found in this image. Try again or move closer."
        return False
    error = apply_scan_raw(decoded)
    if error:
        st.session_state["scan_last_error"] = error
        return False
    st.session_state.pop("scan_last_error", None)
    return True


def clear_scan_for_next_guest() -> None:
    """Reset scan UI so staff can scan the next guest immediately."""
    st.session_state.pop(SESSION_SCAN_LOOKUP_GUEST, None)
    st.session_state.pop(SESSION_LAST_SCAN_TOKEN, None)
    st.session_state.pop(SESSION_LAST_PROCESSED_SCAN_PAYLOAD, None)
    st.session_state.pop("scan_last_error", None)
    st.session_state[SESSION_SCAN_PHOTO_KEY] = int(st.session_state.get(SESSION_SCAN_PHOTO_KEY, 0)) + 1
    st.session_state[SESSION_SCAN_UPLOAD_KEY] = int(st.session_state.get(SESSION_SCAN_UPLOAD_KEY, 0)) + 1
    st.session_state[SESSION_SCAN_PASTE_KEY] = int(st.session_state.get(SESSION_SCAN_PASTE_KEY, 0)) + 1
    st.session_state.pop("scan_last_paste_attempt", None)
    if QUERY_PARAM_SCAN_TOKEN in st.query_params:
        try:
            del st.query_params[QUERY_PARAM_SCAN_TOKEN]
        except Exception:
            try:
                st.query_params.clear()
            except Exception:
                pass


def confirm_handout(guest_id: int, gifts_now: int, notes: str) -> tuple[bool, str]:
    ok, msg, _updated = record_gift_handout(
        guest_id,
        gifts_now,
        scanned_by=st.session_state.get(SESSION_SCANNER_STAFF_NAME, ""),
        notes=notes,
    )
    if ok:
        clear_scan_for_next_guest()
    return ok, msg
