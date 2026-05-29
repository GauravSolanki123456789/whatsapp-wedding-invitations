"""
WhatsApp Wedding Invitations — Streamlit app for bulk guest messaging.

Run: streamlit run app.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from compose_store import clear_last_compose_attachment, load_last_compose, save_last_compose
from constants import (
    APP_ICON,
    APP_TAGLINE,
    APP_TITLE,
    ALLOWED_ATTACHMENT_TYPES,
    ATTACHMENT_FOLDER,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_GROUP_NAME,
    DELAY_MAX_SECONDS,
    DELAY_MIN_SECONDS,
    DOCUMENT_EXTENSIONS,
    GROUP_MODE_AUTO,
    GROUP_MODE_QUICK,
    IMAGE_EXTENSIONS,
    MANUAL_SEND_LOG_FILE,
    MOBILE_NUMBER_COLUMN,
    SEND_MODE_AUTO,
    SEND_MODE_GUIDED,
    SEND_MODE_QUICK,
    SESSION_ATTACHMENT_BYTES,
    SESSION_GUIDED_COOLDOWN_UNTIL,
    SESSION_GROUP_LOG,
    SESSION_GROUP_MODE,
    SESSION_GROUP_NAME,
    WHATSAPP_MAX_GROUP_PARTICIPANTS,
    SESSION_ATTACHMENT_NAME,
    SESSION_ATTACHMENT_PATH,
    SESSION_COMPOSE_LOADED,
    SESSION_COUNTRY_CODE,
    SESSION_DELAY_MAX,
    SESSION_DELAY_MIN,
    SESSION_FILE_UPLOAD_KEY,
    SESSION_ACTIVE_FAMILY_ID,
    SESSION_ACTIVE_GUEST_LIST_ID,
    SESSION_GUEST_LIST,
    SESSION_GUEST_LIST_LOADED,
    SESSION_MANUAL_SENT,
    SESSION_USE_NAMED_LIST,
    SESSION_MESSAGE,
    SESSION_SEND_LOG,
    SESSION_SEND_MODE,
    STATUS_FAILED,
    STATUS_SENT,
    VIDEO_EXTENSIONS,
)
from group_contacts import (
    build_guest_vcard,
    group_creation_summary_rows,
    numbers_for_clipboard,
)
from guest_store import load_guest_list, save_guest_list
from guided_send import cooldown_remaining, next_pending_guest, start_cooldown
from hosting import auto_send_available, default_send_mode
from wa_links import wa_me_link
from utils import (
    attachment_size_label,
    count_invalid_numbers,
    extract_mobile_numbers_from_excel,
    guest_list_from_dataframe,
    normalize_mobile_number,
    validate_attachment_for_whatsapp,
)
from whatsapp_group_service import create_whatsapp_group, validate_group_request
from whatsapp_service import (
    configure_delays,
    delay_between_messages,
    send_whatsapp_message,
    start_send_session,
    stop_send_session,
)
from database import ensure_database_ready
from family_service import get_family
from named_guest_list_service import get_guest_list_members, members_to_mobile_numbers
from ui_pages import (
    render_database_status,
    render_families_tab,
    render_family_selector,
    render_functions_tab,
    render_integrations_tab,
    render_lists_tab,
    render_reports_tab,
    render_scan_tab,
)
from ui_styles import inject_app_styles


def inject_pwa_meta() -> None:
    st.markdown(
        """
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
        <meta name="mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-title" content="WA Invites">
        """,
        unsafe_allow_html=True,
    )


def init_session_state() -> None:
    defaults = {
        SESSION_GUEST_LIST: pd.DataFrame(columns=[MOBILE_NUMBER_COLUMN]),
        SESSION_MESSAGE: "",
        SESSION_COUNTRY_CODE: DEFAULT_COUNTRY_CODE,
        SESSION_SEND_LOG: [],
        SESSION_FILE_UPLOAD_KEY: 0,
        SESSION_ATTACHMENT_PATH: None,
        SESSION_ATTACHMENT_NAME: None,
        SESSION_COMPOSE_LOADED: False,
        SESSION_GUEST_LIST_LOADED: False,
        SESSION_DELAY_MIN: DELAY_MIN_SECONDS,
        SESSION_DELAY_MAX: DELAY_MAX_SECONDS,
        SESSION_SEND_MODE: default_send_mode(),
        SESSION_MANUAL_SENT: set(),
        SESSION_GROUP_NAME: DEFAULT_GROUP_NAME,
        SESSION_GROUP_MODE: GROUP_MODE_QUICK,
        SESSION_GROUP_LOG: [],
        SESSION_GUIDED_COOLDOWN_UNTIL: 0,
        SESSION_ATTACHMENT_BYTES: None,
        SESSION_ACTIVE_FAMILY_ID: None,
        SESSION_ACTIVE_GUEST_LIST_ID: None,
        SESSION_USE_NAMED_LIST: False,
    }
    db_error = ensure_database_ready(st.session_state)
    if db_error:
        st.session_state["database_error"] = db_error

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state[SESSION_COMPOSE_LOADED]:
        last_compose = load_last_compose()
        if last_compose["message"]:
            st.session_state[SESSION_MESSAGE] = last_compose["message"]
        if last_compose["attachment_path"]:
            st.session_state[SESSION_ATTACHMENT_PATH] = last_compose["attachment_path"]
            st.session_state[SESSION_ATTACHMENT_NAME] = last_compose["attachment_name"]
            if os.path.exists(last_compose["attachment_path"]):
                with open(last_compose["attachment_path"], "rb") as file_handle:
                    st.session_state[SESSION_ATTACHMENT_BYTES] = file_handle.read()
        st.session_state[SESSION_COMPOSE_LOADED] = True

    if not st.session_state[SESSION_GUEST_LIST_LOADED]:
        saved_guests = load_guest_list()
        if not saved_guests.empty:
            st.session_state[SESSION_GUEST_LIST] = saved_guests
        st.session_state[SESSION_GUEST_LIST_LOADED] = True

    st.session_state[SESSION_MANUAL_SENT] = load_manual_sent_numbers()


def render_hero() -> None:
    st.markdown(
        f"""
        <div class="app-shell">
          <p class="hero-title">{APP_ICON} {APP_TITLE}</p>
          <p class="hero-subtitle">{APP_TAGLINE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Settings")
        st.session_state[SESSION_COUNTRY_CODE] = st.text_input(
            "Default country code",
            value=st.session_state[SESSION_COUNTRY_CODE],
            help="Applied to numbers in Excel that don't already include a country code (e.g. +91, +1, +44).",
        )

        st.markdown("---")
        st.markdown("**Delay between guests**")
        delay_min = st.slider(
            "Minimum pause (seconds)",
            min_value=0,
            max_value=60,
            value=int(st.session_state[SESSION_DELAY_MIN]),
            help="Extra wait between guests. Upload time is separate — set 0 for fastest.",
        )
        delay_max = st.slider(
            "Maximum pause (seconds)",
            min_value=delay_min,
            max_value=90,
            value=max(int(st.session_state[SESSION_DELAY_MAX]), delay_min),
        )
        st.session_state[SESSION_DELAY_MIN] = delay_min
        st.session_state[SESSION_DELAY_MAX] = delay_max
        configure_delays(delay_min, delay_max)

        st.markdown("---")
        st.caption(
            f"Pause between guests: **{delay_min}–{delay_max}s** "
            "(used in Guided Send to avoid spam flags)."
        )


def render_upload_section() -> None:
    st.markdown('<p class="section-title">Upload guest list</p>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Choose an Excel file (.xlsx)",
        type=["xlsx"],
        key=f"upload_{st.session_state[SESSION_FILE_UPLOAD_KEY]}",
        help="Column 2 = mobile numbers. Column 1 is ignored.",
    )

    if uploaded_file is not None:
        try:
            guest_list = extract_mobile_numbers_from_excel(
                uploaded_file.getvalue(),
                st.session_state[SESSION_COUNTRY_CODE],
            )
            st.session_state[SESSION_GUEST_LIST] = guest_list
            save_guest_list(guest_list)
            count = len(guest_list)
            if count:
                st.success(f"Loaded **{count}** number{'s' if count != 1 else ''}.")
            else:
                st.warning("No valid numbers in column 2.")
        except Exception as exc:
            st.error(f"Could not read the Excel file: {exc}")


def render_guest_editor() -> None:
    st.markdown('<p class="section-title">Review numbers</p>', unsafe_allow_html=True)

    guest_list: pd.DataFrame = st.session_state[SESSION_GUEST_LIST]
    if guest_list.empty:
        st.info("Upload Excel or add numbers below.")
        guest_list = pd.DataFrame({MOBILE_NUMBER_COLUMN: [""]})

    edited_guest_list = st.data_editor(
        guest_list,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            MOBILE_NUMBER_COLUMN: st.column_config.TextColumn(
                "Mobile number",
                help="Include country code, e.g. +919876543210",
                required=True,
                width="large",
            ),
        },
        key="guest_data_editor",
    )

    st.session_state[SESSION_GUEST_LIST] = edited_guest_list
    save_guest_list(edited_guest_list)

    finalized_numbers = guest_list_from_dataframe(edited_guest_list)
    invalid_count = count_invalid_numbers(finalized_numbers)

    st.markdown(
        f'<span class="stat-pill">{len(finalized_numbers)} guests</span>'
        + (
            f' <span class="stat-pill stat-pill--warn">{invalid_count} invalid</span>'
            if invalid_count
            else ""
        ),
        unsafe_allow_html=True,
    )

    if st.button("Clear list", use_container_width=True):
        st.session_state[SESSION_GUEST_LIST] = pd.DataFrame(columns=[MOBILE_NUMBER_COLUMN])
        st.session_state[SESSION_FILE_UPLOAD_KEY] += 1
        save_guest_list(st.session_state[SESSION_GUEST_LIST])
        st.rerun()


def render_group_section() -> None:
    st.markdown('<p class="section-title">WhatsApp group</p>', unsafe_allow_html=True)

    mobile_numbers = collect_mobile_numbers()
    guest_count = len(mobile_numbers)
    invalid_count = count_invalid_numbers(mobile_numbers)

    st.markdown(
        f'<span class="stat-pill">{guest_count} guests</span>',
        unsafe_allow_html=True,
    )

    group_name = st.text_input(
        "Group name",
        value=st.session_state.get(SESSION_GROUP_NAME, DEFAULT_GROUP_NAME),
        placeholder="e.g. Chandana's Wedding Guests",
    )
    st.session_state[SESSION_GROUP_NAME] = group_name

    group_options = [GROUP_MODE_QUICK]
    if auto_send_available():
        group_options.append(GROUP_MODE_AUTO)

    if len(group_options) == 1:
        group_mode = GROUP_MODE_QUICK
    else:
        group_mode = st.radio(
            "How to create the group",
            options=group_options,
            format_func=lambda value: (
                "Quick Group — import contacts on phone (recommended)"
                if value == GROUP_MODE_QUICK
                else "Auto Group — Chrome automation (laptop only)"
            ),
            horizontal=False,
            key=SESSION_GROUP_MODE,
        )

    if guest_count > WHATSAPP_MAX_GROUP_PARTICIPANTS:
        st.warning(
            f"Max **{WHATSAPP_MAX_GROUP_PARTICIPANTS}** members per group. "
            f"You have **{guest_count}** guests."
        )

    if group_mode == GROUP_MODE_QUICK:
        render_quick_group_panel(mobile_numbers, group_name, invalid_count)
    else:
        render_auto_group_panel(mobile_numbers, group_name, invalid_count, guest_count)


def render_quick_group_panel(
    mobile_numbers: list[str],
    group_name: str,
    invalid_count: int,
) -> None:
    st.markdown(
        """
        <div class="notice-box tip-box">
          <strong>Phone:</strong> download contacts → import → WhatsApp → New group →
          select <em>Wedding Guest</em> → create.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not mobile_numbers:
        st.warning("Upload your guest list in step 1 first.")
        return

    error = validate_group_request(mobile_numbers, group_name, invalid_count)
    if error:
        st.error(error)
        return

    vcard_bytes = build_guest_vcard(mobile_numbers).encode("utf-8")
    clipboard_text = numbers_for_clipboard(mobile_numbers)

    st.download_button(
        label="Download guest contacts (.vcf)",
        data=vcard_bytes,
        file_name="wedding_guest_contacts.vcf",
        mime="text/vcard",
        use_container_width=True,
    )
    st.download_button(
        label="Download number list (.txt)",
        data=clipboard_text.encode("utf-8"),
        file_name="guest_numbers.txt",
        mime="text/plain",
        use_container_width=True,
    )


def render_auto_group_panel(
    mobile_numbers: list[str],
    group_name: str,
    invalid_count: int,
    guest_count: int,
) -> None:
    st.markdown(
        '<span class="mode-badge">Desktop only · uses automation Chrome</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="notice-box warning-box">
          <strong>Auto Group:</strong> Chrome opens WhatsApp Web and creates the group for you.
          Scan the QR code once if asked. Numbers must appear in WhatsApp search
          (message them once or use Quick Group on phone first).
          Keep automation Chrome <strong>visible</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not mobile_numbers:
        st.warning("Upload your guest list in step 1 first.")
        return

    error = validate_group_request(mobile_numbers, group_name, invalid_count)
    if error:
        st.error(error)
        return

    if st.button(
        f"Create group · all {guest_count} guests",
        type="primary",
        use_container_width=True,
        key="auto_create_group",
    ):
        run_auto_group_flow(group_name.strip(), mobile_numbers)


def run_auto_group_flow(group_name: str, mobile_numbers: list[str]) -> None:
    progress = st.progress(0, text="Opening Chrome for WhatsApp…")
    status = st.empty()

    status.info(
        "Creating your group… If you see a QR code, scan it once. "
        "Keep the Chrome window visible."
    )
    progress.progress(0.15, text="Adding guests to the group…")

    result = create_whatsapp_group(group_name, mobile_numbers)
    progress.progress(1.0, text="Done")

    if result.success:
        status.success(result.detail)
        added_numbers = [n for n in mobile_numbers if n not in result.skipped_numbers]
        log_rows = group_creation_summary_rows(added_numbers, result.skipped_numbers)
        st.session_state[SESSION_GROUP_LOG] = log_rows
    else:
        status.error(result.detail)

    if result.skipped_numbers:
        st.warning(
            "These numbers were not found in WhatsApp Web search: "
            + ", ".join(f"`{n}`" for n in result.skipped_numbers[:8])
            + (" …" if len(result.skipped_numbers) > 8 else "")
            + ". Use **Quick Group** on your phone after importing the .vcf file."
        )


def render_group_log() -> None:
    group_log = st.session_state.get(SESSION_GROUP_LOG, [])
    if group_log:
        st.markdown('<p class="section-title">Group creation log</p>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(group_log), use_container_width=True, hide_index=True)


def load_manual_sent_numbers() -> set[str]:
    if not os.path.exists(MANUAL_SEND_LOG_FILE):
        return set()
    try:
        with open(MANUAL_SEND_LOG_FILE, encoding="utf-8") as file_handle:
            data = json.load(file_handle)
        return set(data.get("mobile_numbers", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_manual_sent_numbers(numbers: set[str]) -> None:
    os.makedirs(os.path.dirname(MANUAL_SEND_LOG_FILE), exist_ok=True)
    with open(MANUAL_SEND_LOG_FILE, "w", encoding="utf-8") as file_handle:
        json.dump({"mobile_numbers": sorted(numbers)}, file_handle, ensure_ascii=False, indent=2)


def mark_manual_sent(mobile_number: str) -> None:
    sent = set(st.session_state.get(SESSION_MANUAL_SENT, set()))
    sent.add(mobile_number)
    st.session_state[SESSION_MANUAL_SENT] = sent
    save_manual_sent_numbers(sent)


def reset_manual_progress() -> None:
    st.session_state[SESSION_MANUAL_SENT] = set()
    save_manual_sent_numbers(set())


def get_attachment_download_data() -> tuple[bytes | None, str | None]:
    name = st.session_state.get(SESSION_ATTACHMENT_NAME)
    bytes_data = st.session_state.get(SESSION_ATTACHMENT_BYTES)
    if bytes_data:
        return bytes_data, name
    attachment_path = st.session_state.get(SESSION_ATTACHMENT_PATH)
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as file_handle:
            st.session_state[SESSION_ATTACHMENT_BYTES] = file_handle.read()
            return st.session_state[SESSION_ATTACHMENT_BYTES], name
    return None, name


def render_attachment_download_button(label: str = "Save video on phone (use once per guest)") -> None:
    data, name = get_attachment_download_data()
    if not data or not name:
        return
    st.download_button(
        label=label,
        data=data,
        file_name=name,
        mime="application/octet-stream",
        use_container_width=True,
    )


def validate_before_send(mobile_numbers: list[str], message: str, attachment_path: str | None) -> bool:
    invalid_count = count_invalid_numbers(mobile_numbers)
    if not mobile_numbers:
        st.error("No mobile numbers to send. Upload a file or add numbers in the editor.")
        return False
    if invalid_count:
        st.error(
            f"{invalid_count} number(s) are invalid. "
            "Each number must include a country code, e.g. +919876543210."
        )
        return False
    has_attachment = bool(st.session_state.get(SESSION_ATTACHMENT_BYTES)) or (
        attachment_path and os.path.exists(attachment_path)
    )
    if not message and not has_attachment:
        st.warning("Add invitation text and/or an attachment in the **Compose** tab first.")
        return False
    if attachment_path and not os.path.exists(attachment_path) and not st.session_state.get(
        SESSION_ATTACHMENT_BYTES
    ):
        st.error("Attachment missing — upload again in **Compose**.")
        return False
    if attachment_path and os.path.exists(attachment_path):
        size_error = validate_attachment_for_whatsapp(attachment_path)
        if size_error:
            st.error(size_error)
            return False
    return True


def save_attachment(uploaded_file) -> str:
    """Persist attachment to disk (survives cloud reruns) and keep bytes in session."""
    os.makedirs(ATTACHMENT_FOLDER, exist_ok=True)
    os.makedirs("data/attachments", exist_ok=True)
    safe_name = Path(uploaded_file.name).name
    file_bytes = bytes(uploaded_file.getbuffer())
    attachment_path = os.path.join("data/attachments", f"current_{safe_name}")

    with open(attachment_path, "wb") as file_handle:
        file_handle.write(file_bytes)

    st.session_state[SESSION_ATTACHMENT_BYTES] = file_bytes
    return attachment_path


def remove_current_attachment() -> None:
    """Clear the active attachment from session state and persisted storage."""
    st.session_state[SESSION_ATTACHMENT_PATH] = None
    st.session_state[SESSION_ATTACHMENT_NAME] = None
    st.session_state[SESSION_ATTACHMENT_BYTES] = None
    clear_last_compose_attachment()


def render_attachment_preview(attachment_path: str, attachment_name: str) -> None:
    """Show a preview for the current attachment based on file type."""
    suffix = Path(attachment_name).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        st.image(attachment_path, caption="Preview", use_container_width=True)
    elif suffix in VIDEO_EXTENSIONS:
        st.video(attachment_path)
    elif suffix in DOCUMENT_EXTENSIONS:
        st.markdown("📄 **PDF document**")
    else:
        st.markdown("📎 **Attachment**")


def render_message_section() -> None:
    st.markdown('<p class="section-title">Invitation</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="notice-box tip-box">
          <strong>Video on phone:</strong> Attach here → in <strong>Send</strong> tap
          <strong>Save attachment</strong> → in WhatsApp use 📎 and pick that file.
          Links cannot auto-attach video (WhatsApp limitation).
        </div>
        """,
        unsafe_allow_html=True,
    )

    message = st.text_area(
        "Message",
        value=st.session_state[SESSION_MESSAGE],
        height=140,
        placeholder="Your wedding invitation text…",
        label_visibility="collapsed",
    )
    st.session_state[SESSION_MESSAGE] = message
    st.caption(f"{len(message)} characters")

    attachment_file = st.file_uploader(
        "Attach video or photo (optional)",
        type=ALLOWED_ATTACHMENT_TYPES,
        key="invitation_attachment",
    )

    if attachment_file is not None:
        attachment_path = save_attachment(attachment_file)
        st.session_state[SESSION_ATTACHMENT_PATH] = attachment_path
        st.session_state[SESSION_ATTACHMENT_NAME] = attachment_file.name
        st.success(f"Attached: **{attachment_file.name}** ({attachment_size_label(attachment_path)})")
        size_error = validate_attachment_for_whatsapp(attachment_path)
        if size_error:
            st.error(size_error)
        if st.button("Remove attachment", key="remove_attachment"):
            remove_current_attachment()
            st.rerun()
    elif st.session_state.get(SESSION_ATTACHMENT_NAME):
        name = st.session_state[SESSION_ATTACHMENT_NAME]
        path = st.session_state.get(SESSION_ATTACHMENT_PATH)
        if path and os.path.exists(path):
            st.info(f"Saved attachment: **{name}** ({attachment_size_label(path)})")
        elif st.session_state.get(SESSION_ATTACHMENT_BYTES):
            st.info(f"Attached: **{name}**")
        if st.button("Remove attachment", key="remove_saved_attachment"):
            remove_current_attachment()
            st.rerun()


def render_send_section() -> None:
    st.markdown('<p class="section-title">Send</p>', unsafe_allow_html=True)

    if st.session_state.get(SESSION_USE_NAMED_LIST):
        st.caption("Numbers come from your **Lists** tab (saved list).")
    else:
        st.caption("Numbers come from **Guests** tab. Enable saved list in **Lists**.")

    message = st.session_state[SESSION_MESSAGE].strip()
    attachment_name = st.session_state.get(SESSION_ATTACHMENT_NAME)
    attachment_path = st.session_state.get(SESSION_ATTACHMENT_PATH)
    mobile_numbers = collect_mobile_numbers()
    guest_count = len(mobile_numbers)
    sent_manual = st.session_state.get(SESSION_MANUAL_SENT, set())

    send_options = [SEND_MODE_GUIDED, SEND_MODE_QUICK]
    if auto_send_available():
        send_options.append(SEND_MODE_AUTO)

    send_mode = st.radio(
        "Send mode",
        options=send_options,
        format_func=lambda value: {
            SEND_MODE_GUIDED: "Guided Send — one guest at a time with pause (best on phone)",
            SEND_MODE_QUICK: "Quick Send — see full guest list",
            SEND_MODE_AUTO: "Auto Send — full Chrome automation (laptop only)",
        }[value],
        horizontal=False,
        key=SESSION_SEND_MODE,
    )

    if send_mode == SEND_MODE_GUIDED:
        render_guided_send_panel(
            mobile_numbers=mobile_numbers,
            message=message,
            attachment_name=attachment_name,
            attachment_path=attachment_path,
            sent_manual=sent_manual,
            guest_count=guest_count,
        )
    elif send_mode == SEND_MODE_QUICK:
        render_quick_send_panel(
            mobile_numbers=mobile_numbers,
            message=message,
            attachment_name=attachment_name,
            attachment_path=attachment_path,
            sent_manual=sent_manual,
            guest_count=guest_count,
        )
    else:
        render_auto_send_panel(
            mobile_numbers=mobile_numbers,
            message=message,
            attachment_name=attachment_name,
            attachment_path=attachment_path,
            guest_count=guest_count,
        )


def render_guided_send_panel(
    mobile_numbers: list[str],
    message: str,
    attachment_name: str | None,
    attachment_path: str | None,
    sent_manual: set[str],
    guest_count: int,
) -> None:
    if not mobile_numbers:
        st.warning("Add guests in the **Guests** tab first.")
        return

    if not validate_before_send(mobile_numbers, message, attachment_path):
        return

    delay_min = int(st.session_state[SESSION_DELAY_MIN])
    delay_max = int(st.session_state[SESSION_DELAY_MAX])
    wait_seconds = cooldown_remaining(st.session_state)

    if wait_seconds > 0:
        st.markdown(
            f"""
            <div class="focus-card focus-card--wait">
              <p class="focus-meta">Anti-spam pause</p>
              <p class="focus-guest-number">{wait_seconds}s</p>
              <p class="focus-meta">Next guest unlocks automatically…</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(1 - wait_seconds / max(delay_max, 1))
        time.sleep(1)
        st.rerun()
        return

    number, position, pending, total = next_pending_guest(mobile_numbers, sent_manual)
    sent_count = total - pending

    if not number:
        st.success(f"All done — **{sent_count}** invitation{'s' if sent_count != 1 else ''} sent.")
        if st.button("Reset progress", use_container_width=True):
            reset_manual_progress()
            st.session_state[SESSION_GUIDED_COOLDOWN_UNTIL] = 0
            st.rerun()
        return

    st.progress(sent_count / total if total else 0, text=f"{sent_count} of {total} sent")

    st.markdown(
        f"""
        <div class="focus-card">
          <p class="focus-meta">Guest {position} of {total}</p>
          <p class="focus-guest-number">{number}</p>
          <ol class="step-list">
            <li>Tap <strong>Open WhatsApp</strong> below</li>
            <li>Attach your video (📎) if needed → Send</li>
            <li>Return here → tap <strong>Done, next guest</strong></li>
          </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if attachment_name:
        st.caption(f"Attachment: **{attachment_name}**")
        render_attachment_download_button()

    st.link_button(
        "Open WhatsApp",
        wa_me_link(number, message),
        use_container_width=True,
    )

    if st.button("Done — next guest", type="primary", use_container_width=True, key="guided_next"):
        mark_manual_sent(number)
        if pending > 1 and (delay_min > 0 or delay_max > 0):
            pause = start_cooldown(st.session_state, delay_min, delay_max)
            st.toast(f"Pause {int(pause)}s before next guest")
        st.rerun()

    if st.button("Reset progress", use_container_width=True):
        reset_manual_progress()
        st.session_state[SESSION_GUIDED_COOLDOWN_UNTIL] = 0
        st.rerun()


def render_quick_send_panel(
    mobile_numbers: list[str],
    message: str,
    attachment_name: str | None,
    attachment_path: str | None,
    sent_manual: set[str],
    guest_count: int,
) -> None:
    if not mobile_numbers:
        st.warning("Add guests in the **Guests** tab first.")
        return

    if not validate_before_send(mobile_numbers, message, attachment_path):
        return

    if attachment_name:
        render_attachment_download_button("Save attachment on phone")

    sent_count = sum(1 for number in mobile_numbers if number in sent_manual)
    st.progress(sent_count / guest_count if guest_count else 0, text=f"{sent_count} of {guest_count} sent")

    with st.expander(f"All guests ({guest_count})", expanded=False):
        for index, mobile_number in enumerate(mobile_numbers, start=1):
            is_sent = mobile_number in sent_manual
            status = "✅" if is_sent else str(index)
            col_a, col_b = st.columns([1.4, 1])
            with col_a:
                st.markdown(f"{status} `{mobile_number}`")
            with col_b:
                st.link_button("Open", wa_me_link(mobile_number, message), use_container_width=True)
            if not is_sent and st.button("Mark sent", key=f"mark_sent_{mobile_number}", use_container_width=True):
                mark_manual_sent(mobile_number)
                st.rerun()

    if st.button("Reset progress", use_container_width=True):
        reset_manual_progress()
        st.rerun()


def render_auto_send_panel(
    mobile_numbers: list[str],
    message: str,
    attachment_name: str | None,
    attachment_path: str | None,
    guest_count: int,
) -> None:
    st.markdown('<span class="mode-badge">Desktop only · requires Chrome automation</span>', unsafe_allow_html=True)

    delay_min = int(st.session_state[SESSION_DELAY_MIN])
    delay_max = int(st.session_state[SESSION_DELAY_MAX])
    attachment_note = (
        f" Each invitation includes **{attachment_name}**."
        if attachment_name
        else ""
    )

    st.markdown(
        f"""
        <div class="notice-box warning-box">
          <strong>Auto Send:</strong> A separate <strong>Chrome</strong> window opens with WhatsApp Web.{attachment_note}
          <strong>First time only:</strong> scan the QR code in that Chrome window with your phone.
          Keep this dashboard in <strong>Edge or Brave</strong> — do not use Chrome for the app.
          Leave the automation Chrome <strong>maximized and visible</strong> while sending.
          Videos must be under 100 MB. If auto fails, use <strong>Quick Send</strong>.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if guest_count == 0:
        st.warning("Add guest numbers in step 2 first.")
        return

    col_test, col_send = st.columns(2)
    with col_test:
        test_clicked = st.button("Auto test · first guest", use_container_width=True)
    with col_send:
        send_clicked = st.button("Auto send · all guests", type="primary", use_container_width=True)

    if test_clicked:
        run_send_flow(test_only=True)
    if send_clicked:
        run_send_flow(test_only=False)


def collect_mobile_numbers() -> list[str]:
    if st.session_state.get(SESSION_USE_NAMED_LIST) and st.session_state.get(
        SESSION_ACTIVE_GUEST_LIST_ID
    ):
        members = get_guest_list_members(st.session_state[SESSION_ACTIVE_GUEST_LIST_ID])
        numbers = members_to_mobile_numbers(members, st.session_state[SESSION_COUNTRY_CODE])
        if numbers:
            return numbers

    guest_list = st.session_state[SESSION_GUEST_LIST]
    country_code = st.session_state[SESSION_COUNTRY_CODE]
    normalized_rows = []
    for raw_value in guest_list_from_dataframe(guest_list):
        normalized = normalize_mobile_number(raw_value, country_code) or raw_value
        normalized_rows.append(normalized)
    return [number for number in normalized_rows if number]


def run_send_flow(test_only: bool = False) -> None:
    message = st.session_state[SESSION_MESSAGE].strip()
    attachment_path = st.session_state.get(SESSION_ATTACHMENT_PATH)
    mobile_numbers = collect_mobile_numbers()

    if not validate_before_send(mobile_numbers, message, attachment_path):
        return

    if test_only:
        mobile_numbers = mobile_numbers[:1]

    total = len(mobile_numbers)
    progress_bar = st.progress(0, text="Preparing to send…")
    status_placeholder = st.empty()
    log_placeholder = st.empty()
    send_log: list[dict[str, str]] = []

    st.session_state[SESSION_SEND_LOG] = send_log

    status_placeholder.info(
        "Opening Chrome for WhatsApp… "
        "If you see a QR code, scan it with your phone (first time only). "
        "Keep the Chrome window visible and this app in Edge or Brave."
    )
    try:
        start_send_session()
    except RuntimeError as exc:
        stop_send_session()
        status_placeholder.error(str(exc))
        progress_bar.empty()
        return
    except Exception as exc:
        stop_send_session()
        status_placeholder.error(f"Could not start Chrome automation: {exc}")
        progress_bar.empty()
        return

    try:
        for index, mobile_number in enumerate(mobile_numbers):
            current = index + 1
            progress_bar.progress(
                (index) / total,
                text=f"Sending message {current} of {total}…",
            )
            status_placeholder.info(
                f"Sending to **{mobile_number}** ({current}/{total})"
                + (
                    f" — uploading **{st.session_state.get(SESSION_ATTACHMENT_NAME)}**, "
                    "keep Chrome visible…"
                    if attachment_path
                    else "…"
                )
            )

            result = send_whatsapp_message(mobile_number, message, attachment_path)
            send_log.append(
                {
                    MOBILE_NUMBER_COLUMN: result.mobile_number,
                    "status": STATUS_SENT if result.success else STATUS_FAILED,
                    "detail": result.detail,
                }
            )
            st.session_state[SESSION_SEND_LOG] = send_log

            log_placeholder.dataframe(
                pd.DataFrame(send_log),
                use_container_width=True,
                hide_index=True,
            )

            progress_bar.progress(current / total, text=f"Completed {current} of {total}")

            if not result.success:
                status_placeholder.warning(
                    f"Failed for **{mobile_number}**: {result.detail}. "
                    f"Continuing with remaining guests…"
                )
            elif current < total:
                status_placeholder.success(f"Sent to **{mobile_number}** ({current}/{total})")

            if current < total:
                delay_seconds = delay_between_messages()
                if delay_seconds > 0:
                    countdown_placeholder = st.empty()
                    for remaining in range(int(delay_seconds), 0, -1):
                        countdown_placeholder.caption(
                            f"Waiting {remaining}s before next guest…"
                        )
                        time.sleep(1)
                    fractional = delay_seconds - int(delay_seconds)
                    if fractional > 0:
                        time.sleep(fractional)
                    countdown_placeholder.empty()
    finally:
        stop_send_session()

    success_count = sum(1 for entry in send_log if entry["status"] == STATUS_SENT)
    failed_count = total - success_count

    if failed_count == 0:
        label = "Test message sent successfully!" if test_only else f"All {total} invitation messages were sent successfully!"
        status_placeholder.success(label)
    else:
        status_placeholder.warning(
            f"Finished: **{success_count}** sent, **{failed_count}** failed. See log below."
        )

    if not test_only or success_count > 0:
        save_last_compose(
            message=message,
            attachment_path=attachment_path,
            attachment_name=st.session_state.get(SESSION_ATTACHMENT_NAME),
        )


def render_send_log() -> None:
    send_log = st.session_state.get(SESSION_SEND_LOG, [])
    if send_log:
        st.markdown('<p class="section-title">Send history</p>', unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame(send_log),
            use_container_width=True,
            hide_index=True,
        )


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    inject_app_styles()
    inject_pwa_meta()
    init_session_state()

    db_error = st.session_state.get("database_error")
    if db_error:
        st.markdown(f"### {APP_ICON} Database setup needed")
        st.error("The app could not connect to Supabase.")
        st.markdown(db_error)
        st.info(
            "After updating **Secrets**, wait ~1 minute for the app to reboot, then refresh this page."
        )
        st.stop()

    render_sidebar()
    render_hero()

    render_database_status()
    family_id = render_family_selector()
    family = get_family(family_id)
    family_name = family["name"] if family else "Family"

    if st.session_state.get(SESSION_USE_NAMED_LIST):
        st.markdown(
            '<span class="stat-pill stat-pill--ok">Using saved list for Send</span>',
            unsafe_allow_html=True,
        )

    nav_labels = ["Guests", "Lists", "Compose", "Send", "Gifts", "Scan", "Reports", "Settings"]
    active_tab = st.radio(
        "Section",
        nav_labels,
        horizontal=True,
        label_visibility="collapsed",
        key="main_nav_tab",
    )

    with st.container(border=True):
        if active_tab == "Guests":
            render_upload_section()
            st.divider()
            render_guest_editor()
        elif active_tab == "Lists":
            render_lists_tab(family_id)
        elif active_tab == "Compose":
            render_message_section()
        elif active_tab == "Send":
            render_send_section()
            render_send_log()
        elif active_tab == "Gifts":
            render_functions_tab(family_id, family_name)
        elif active_tab == "Scan":
            render_scan_tab()
        elif active_tab == "Reports":
            render_reports_tab(family_id)
        elif active_tab == "Settings":
            render_families_tab(family_id)
            st.divider()
            render_group_section()
            render_group_log()
            st.divider()
            render_integrations_tab()


if __name__ == "__main__":
    main()
