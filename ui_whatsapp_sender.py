"""Per-family WhatsApp sender settings UI (Send tab + Settings)."""

from __future__ import annotations

import streamlit as st

from constants import (
    WHATSAPP_APP_BUSINESS,
    WHATSAPP_APP_PERSONAL,
    WHATSAPP_APP_TYPE_COLUMN,
    WHATSAPP_SENDER_PHONE_COLUMN,
)
from family_service import get_family, update_family_whatsapp_settings
from family_state import set_flash
from utils import normalize_mobile_number


def _app_label(app_type: str) -> str:
    return "WhatsApp Business" if app_type == WHATSAPP_APP_BUSINESS else "WhatsApp Personal"


def render_whatsapp_sender_settings(
    family_id: int,
    family_name: str,
    *,
    country_code: str,
    compact: bool = False,
) -> tuple[str, str]:
    """
    Render sender phone + app picker. Returns (whatsapp_sender_phone, whatsapp_app_type).
    Stored on the family row in the database.
    """
    family = get_family(family_id) or {}
    saved_phone = str(family.get(WHATSAPP_SENDER_PHONE_COLUMN) or "")
    saved_app = str(family.get(WHATSAPP_APP_TYPE_COLUMN) or WHATSAPP_APP_PERSONAL)

    title = "Send from this WhatsApp" if compact else f"WhatsApp sender for {family_name}"
    st.markdown(
        f"""
        <div class="sender-card-wrap">
          <p class="sender-card-title">{title}</p>
          <p class="sender-card-hint">
            Leave blank to keep your phone&apos;s normal Send behaviour.
            Add a number to force Personal or Business on Android.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if saved_phone:
        st.markdown(
            f'<span class="stat-pill stat-pill--ok">Saved: {_app_label(saved_app)} · {saved_phone}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="stat-pill">Default — opens your usual WhatsApp app</span>',
            unsafe_allow_html=True,
        )

    phone_key = f"whatsapp_sender_phone_input_{family_id}"
    app_key = f"whatsapp_app_type_input_{family_id}"

    if phone_key not in st.session_state:
        st.session_state[phone_key] = saved_phone

    if compact:
        phone_col, app_col = st.columns([1.4, 1])
    else:
        phone_col, app_col = st.columns([1.2, 1])

    with phone_col:
        raw_phone = st.text_input(
            "Your WhatsApp number",
            placeholder="e.g. 9841166662",
            key=phone_key,
            help="The account you want to send from (logged in on this phone).",
        )
    with app_col:
        st.radio(
            "App",
            options=[WHATSAPP_APP_PERSONAL, WHATSAPP_APP_BUSINESS],
            format_func=lambda value: "Personal" if value == WHATSAPP_APP_PERSONAL else "Business",
            index=0 if saved_app == WHATSAPP_APP_PERSONAL else 1,
            key=app_key,
            horizontal=True,
            label_visibility="collapsed",
        )

    st.caption(
        "Example: Business **8667539795** is your default — enter **9841166662**, choose **Personal**, "
        "tap Save, then Send opens Personal WhatsApp on Android."
    )

    btn_cols = st.columns([1, 1]) if not compact else st.columns(1)
    with btn_cols[0]:
        if st.button("Save sender", type="primary", use_container_width=True, key=f"save_wa_{family_id}"):
            app_type = st.session_state[app_key]
            normalized = normalize_mobile_number(raw_phone.strip(), country_code) if raw_phone.strip() else ""
            err = update_family_whatsapp_settings(family_id, normalized, app_type)
            if err:
                st.error(err)
            else:
                label = _app_label(app_type)
                if normalized:
                    set_flash(f"Sender saved — **{label}** · **{normalized}**")
                else:
                    set_flash("Sender cleared — using default WhatsApp behaviour.")
                st.rerun()

    if not compact and len(btn_cols) > 1:
        with btn_cols[1]:
            if saved_phone and st.button("Clear sender", use_container_width=True, key=f"clear_wa_{family_id}"):
                err = update_family_whatsapp_settings(family_id, "", WHATSAPP_APP_PERSONAL)
                if err:
                    st.error(err)
                else:
                    st.session_state[phone_key] = ""
                    set_flash("Sender cleared — using default WhatsApp behaviour.")
                    st.rerun()

    refreshed = get_family(family_id) or {}
    return (
        str(refreshed.get(WHATSAPP_SENDER_PHONE_COLUMN) or ""),
        str(refreshed.get(WHATSAPP_APP_TYPE_COLUMN) or WHATSAPP_APP_PERSONAL),
    )
