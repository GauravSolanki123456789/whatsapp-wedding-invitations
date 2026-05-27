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
    APP_TITLE,
    ALLOWED_ATTACHMENT_TYPES,
    ATTACHMENT_FOLDER,
    DEFAULT_COUNTRY_CODE,
    DELAY_MAX_SECONDS,
    DELAY_MIN_SECONDS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MANUAL_SEND_LOG_FILE,
    MOBILE_NUMBER_COLUMN,
    SEND_MODE_AUTO,
    SEND_MODE_QUICK,
    SESSION_ATTACHMENT_NAME,
    SESSION_ATTACHMENT_PATH,
    SESSION_COMPOSE_LOADED,
    SESSION_COUNTRY_CODE,
    SESSION_DELAY_MAX,
    SESSION_DELAY_MIN,
    SESSION_FILE_UPLOAD_KEY,
    SESSION_GUEST_LIST,
    SESSION_GUEST_LIST_LOADED,
    SESSION_MANUAL_SENT,
    SESSION_MESSAGE,
    SESSION_SEND_LOG,
    SESSION_SEND_MODE,
    STATUS_FAILED,
    STATUS_SENT,
    VIDEO_EXTENSIONS,
)
from guest_store import load_guest_list, save_guest_list
from hosting import auto_send_available, is_cloud_host
from wa_links import wa_me_link, whatsapp_web_link
from utils import (
    attachment_size_label,
    count_invalid_numbers,
    extract_mobile_numbers_from_excel,
    guest_list_from_dataframe,
    normalize_mobile_number,
    validate_attachment_for_whatsapp,
)
from whatsapp_service import (
    configure_delays,
    delay_between_messages,
    send_whatsapp_message,
    start_send_session,
    stop_send_session,
)


def inject_custom_styles() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Source+Sans+3:wght@400;500;600&display=swap');

          :root {
            --brand: #b76e79;
            --brand-dark: #9e5560;
            --ink: #2c2416;
            --ink-soft: #6b5b52;
            --surface: #ffffff;
            --surface-muted: #fff9f5;
            --border: rgba(183, 110, 121, 0.18);
            --shadow: 0 8px 28px rgba(44, 36, 22, 0.06);
            --radius-lg: 18px;
            --radius-md: 14px;
          }

          html, body, [class*="css"] {
            -webkit-font-smoothing: antialiased;
          }

          .block-container {
            padding-top: 1.25rem;
            padding-bottom: 4rem;
            max-width: 960px;
          }

          h1, h2, h3, .hero-title, .section-title {
            font-family: 'Cormorant Garamond', Georgia, serif !important;
            letter-spacing: 0.02em;
          }

          p, label, .stMarkdown, .stCaption, input, textarea, button {
            font-family: 'Source Sans 3', sans-serif !important;
          }

          #MainMenu, footer, header[data-testid="stHeader"] {
            visibility: hidden;
          }

          .hero-card {
            background: linear-gradient(135deg, #fff9f5 0%, #f8ece6 55%, #f3e0dc 100%);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.75rem 1.5rem;
            margin-bottom: 1.25rem;
            box-shadow: var(--shadow);
          }

          .hero-title {
            font-size: clamp(1.65rem, 4.5vw, 2.4rem);
            color: #5c3d42;
            margin: 0 0 0.4rem 0;
            line-height: 1.12;
          }

          .hero-subtitle {
            color: var(--ink-soft);
            font-size: clamp(0.92rem, 2.6vw, 1.05rem);
            margin: 0;
            line-height: 1.55;
            max-width: 52ch;
          }

          .step-progress {
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
            margin-bottom: 1.25rem;
          }

          .step-chip {
            flex: 1 1 auto;
            min-width: 7rem;
            text-align: center;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 999px;
            padding: 0.45rem 0.75rem;
            font-size: 0.78rem;
            font-weight: 600;
            color: #7a6358;
            letter-spacing: 0.01em;
          }

          .section-title {
            font-size: clamp(1.05rem, 3vw, 1.2rem);
            color: #5c3d42;
            margin: 0 0 0.75rem 0;
            font-weight: 600;
          }

          .stat-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            align-items: center;
            margin-top: 0.35rem;
          }

          .stat-pill {
            display: inline-flex;
            align-items: center;
            background: #f5ede6;
            color: #5c3d42;
            border-radius: 999px;
            padding: 0.4rem 0.9rem;
            font-size: 0.84rem;
            font-weight: 600;
          }

          .stat-pill--warn {
            background: #fde8e8;
            color: #8b2e2e;
          }

          .notice-box {
            border-radius: var(--radius-md);
            padding: 0.9rem 1rem;
            margin: 0.65rem 0;
            font-size: 0.91rem;
            line-height: 1.5;
          }

          .warning-box {
            background: #fff8e8;
            border-left: 4px solid #d4a017;
            color: #5c4a1a;
          }

          .tip-box {
            background: #f0faf3;
            border-left: 4px solid #3d9970;
            color: #2d4a38;
          }

          div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: var(--radius-lg) !important;
            border-color: var(--border) !important;
            background: var(--surface) !important;
            box-shadow: 0 4px 16px rgba(44, 36, 22, 0.035);
            margin-bottom: 1rem;
            padding: 0.25rem 0.35rem;
          }

          .attachment-card {
            background: var(--surface-muted);
            border: 1px dashed rgba(183, 110, 121, 0.35);
            border-radius: var(--radius-md);
            padding: 0.85rem;
            margin-top: 0.5rem;
          }

          div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #fff9f5 0%, #f5ede6 100%);
            border-right: 1px solid var(--border);
          }

          div[data-testid="stSidebar"] .block-container {
            padding-top: 1.25rem;
          }

          div[data-testid="stSidebar"] h3 {
            color: #5c3d42;
          }

          .stButton > button {
            border-radius: 12px !important;
            min-height: 2.75rem;
            font-weight: 600;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
          }

          .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, var(--brand) 0%, var(--brand-dark) 100%) !important;
            border: none !important;
            color: #fff !important;
            box-shadow: 0 4px 14px rgba(158, 85, 96, 0.25);
          }

          .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(158, 85, 96, 0.35);
          }

          .stButton > button[kind="secondary"] {
            border: 1.5px solid rgba(183, 110, 121, 0.45) !important;
            color: #5c3d42 !important;
            background: #fff !important;
          }

          div[data-testid="stDataEditor"],
          div[data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border);
          }

          div[data-testid="stFileUploader"] {
            border-radius: var(--radius-md);
          }

          .stTextArea textarea {
            border-radius: var(--radius-md) !important;
            border-color: var(--border) !important;
          }

          .guest-card {
            background: var(--surface-muted);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 0.85rem 1rem;
            margin-bottom: 0.65rem;
          }

          .guest-card--sent {
            background: #f0faf3;
            border-color: rgba(61, 153, 112, 0.35);
          }

          .mode-badge {
            display: inline-block;
            background: #f5ede6;
            color: #5c3d42;
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
          }

          a[data-testid="stLinkButton"] {
            border-radius: 12px !important;
            min-height: 2.75rem;
            font-weight: 600 !important;
          }

          div[data-testid="stProgress"] > div {
            background: linear-gradient(90deg, var(--brand), var(--brand-dark));
            border-radius: 999px;
          }

          @media (max-width: 768px) {
            .block-container {
              padding-left: 0.85rem;
              padding-right: 0.85rem;
              padding-bottom: 5.5rem;
            }

            .hero-card {
              padding: 1.25rem 1rem;
              border-radius: 16px;
            }

            .step-wrap {
              padding: 1rem 0.9rem 1.15rem;
              border-radius: 16px;
            }

            .step-progress {
              gap: 0.35rem;
            }

            .step-chip {
              min-width: calc(50% - 0.35rem);
              font-size: 0.72rem;
              padding: 0.4rem 0.55rem;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
              padding: 0.15rem 0.2rem;
            }

            div[data-testid="column"] {
              width: 100% !important;
              flex: 1 1 100% !important;
              min-width: 100% !important;
            }

            div[data-testid="stSidebar"] {
              min-width: 17rem !important;
            }

            .stat-row {
              flex-direction: column;
              align-items: stretch;
            }

            .stat-pill {
              justify-content: center;
            }

            .send-actions [data-testid="column"] .stButton > button {
              width: 100%;
            }
          }

          @media (max-width: 480px) {
            .hero-title {
              font-size: 1.55rem;
            }

            .step-chip {
              min-width: 100%;
            }

            .notice-box {
              font-size: 0.87rem;
              padding: 0.8rem 0.85rem;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
        SESSION_SEND_MODE: SEND_MODE_QUICK,
        SESSION_MANUAL_SENT: set(),
    }
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
        <div class="hero-card">
          <p class="hero-title">{APP_ICON} {APP_TITLE}</p>
          <p class="hero-subtitle">
            Upload your guest list, review mobile numbers, compose your invitation,
            and send personalized WhatsApp messages safely — one guest at a time.
          </p>
        </div>
        <div class="step-progress">
          <span class="step-chip">1 · Guest list</span>
          <span class="step-chip">2 · Review numbers</span>
          <span class="step-chip">3 · Compose</span>
          <span class="step-chip">4 · Send</span>
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
        st.markdown("**How to send safely**")
        st.caption(
            f"Optional pause between guests: **{delay_min}–{delay_max}s**. "
            "Set both to **0** for no extra wait (video upload still takes time)."
        )
        st.markdown(
            """
            **Quick Send (recommended)**
            - Works on **phone & laptop**
            - Tap each guest → WhatsApp opens → attach file → send → back here

            **Auto Send**
            - Opens **WhatsApp in Chrome** automatically (keeps your login)
            - Run this app in **Edge or Brave** — Chrome will restart when you click Auto Send
            - Use Quick Send if auto fails
            """
        )


def render_upload_section() -> None:
    with st.container(border=True):
        st.markdown('<p class="section-title">1 · Upload guest list</p>', unsafe_allow_html=True)

        uploaded_file = st.file_uploader(
            "Choose an Excel file (.xlsx)",
            type=["xlsx"],
            key=f"upload_{st.session_state[SESSION_FILE_UPLOAD_KEY]}",
            help="The app reads **column 2 only** (mobile numbers). Column 1 (names) is ignored.",
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
                    st.success(f"Loaded **{count}** mobile number{'s' if count != 1 else ''} from column 2.")
                else:
                    st.warning("No valid mobile numbers found in column 2. Check your file and country code.")
            except Exception as exc:
                st.error(f"Could not read the Excel file: {exc}")


def render_guest_editor() -> None:
    with st.container(border=True):
        st.markdown('<p class="section-title">2 · Review & edit numbers</p>', unsafe_allow_html=True)

        guest_list: pd.DataFrame = st.session_state[SESSION_GUEST_LIST]
        if guest_list.empty:
            st.info("Upload an Excel file to populate the guest list, or add numbers manually below.")
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
            f"""
            <div class="stat-row">
              <span class="stat-pill">{len(finalized_numbers)} guests</span>
              {f'<span class="stat-pill stat-pill--warn">{invalid_count} invalid</span>' if invalid_count else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Clear list", use_container_width=True):
            st.session_state[SESSION_GUEST_LIST] = pd.DataFrame(columns=[MOBILE_NUMBER_COLUMN])
            st.session_state[SESSION_FILE_UPLOAD_KEY] += 1
            save_guest_list(st.session_state[SESSION_GUEST_LIST])
            st.rerun()


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
    if not message and not attachment_path:
        st.error("Please write a message or attach a file before sending.")
        return False
    if attachment_path and not os.path.exists(attachment_path):
        st.error("The attached file could not be found. Please upload it again.")
        return False
    if attachment_path:
        size_error = validate_attachment_for_whatsapp(attachment_path)
        if size_error:
            st.error(size_error)
            return False
    return True


def save_attachment(uploaded_file) -> str:
    """Persist an uploaded attachment to disk and return its path."""
    os.makedirs(ATTACHMENT_FOLDER, exist_ok=True)
    safe_name = Path(uploaded_file.name).name
    attachment_path = os.path.join(ATTACHMENT_FOLDER, safe_name)

    with open(attachment_path, "wb") as file_handle:
        file_handle.write(uploaded_file.getbuffer())

    return attachment_path


def remove_current_attachment() -> None:
    """Clear the active attachment from session state and persisted storage."""
    st.session_state[SESSION_ATTACHMENT_PATH] = None
    st.session_state[SESSION_ATTACHMENT_NAME] = None
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
    with st.container(border=True):
        st.markdown('<p class="section-title">3 · Compose invitation</p>', unsafe_allow_html=True)

        message = st.text_area(
            "Invitation message",
            value=st.session_state[SESSION_MESSAGE],
            height=180,
            placeholder="Type your wedding invitation message here…",
            help="This text is sent with every invitation. With an attachment, it becomes the caption.",
        )
        st.session_state[SESSION_MESSAGE] = message

        st.caption(f"{len(message)} characters")

        st.markdown("**Attach a file (optional)**")
        attachment_file = st.file_uploader(
            "Invitation attachment",
            type=ALLOWED_ATTACHMENT_TYPES,
            key="invitation_attachment",
            help="PDF, images, or video (MP4, MOV, etc.). Sent with your message. Leave empty for text only.",
            label_visibility="collapsed",
        )

        if attachment_file is not None:
            attachment_path = save_attachment(attachment_file)
            st.session_state[SESSION_ATTACHMENT_PATH] = attachment_path
            st.session_state[SESSION_ATTACHMENT_NAME] = attachment_file.name

            st.markdown('<div class="attachment-card">', unsafe_allow_html=True)
            col_preview, col_info = st.columns([1, 1.4])
            with col_preview:
                render_attachment_preview(attachment_path, attachment_file.name)
            with col_info:
                st.success(f"Attached: **{attachment_file.name}**")
                st.caption(
                    f"Size: **{attachment_size_label(attachment_path)}** · "
                    "This file will be sent with every invitation."
                )
                size_error = validate_attachment_for_whatsapp(attachment_path)
                if size_error:
                    st.error(size_error)
                if st.button("Remove attachment", key="remove_attachment", use_container_width=True):
                    remove_current_attachment()
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        elif st.session_state.get(SESSION_ATTACHMENT_PATH) and st.session_state.get(
            SESSION_ATTACHMENT_NAME
        ):
            attachment_path = st.session_state[SESSION_ATTACHMENT_PATH]
            attachment_name = st.session_state[SESSION_ATTACHMENT_NAME]

            if os.path.exists(attachment_path):
                st.markdown('<div class="attachment-card">', unsafe_allow_html=True)
                col_preview, col_info = st.columns([1, 1.4])
                with col_preview:
                    render_attachment_preview(attachment_path, attachment_name)
                with col_info:
                    st.info(f"Last attachment: **{attachment_name}**")
                    st.caption(
                        f"Size: **{attachment_size_label(attachment_path)}** · "
                        "Restored from your last sent invitation."
                    )
                    size_error = validate_attachment_for_whatsapp(attachment_path)
                    if size_error:
                        st.error(size_error)
                    if st.button("Remove attachment", key="remove_saved_attachment", use_container_width=True):
                        remove_current_attachment()
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("The saved attachment file is missing. Please upload it again.")
                remove_current_attachment()


def render_send_section() -> None:
    with st.container(border=True):
        st.markdown('<p class="section-title">4 · Send invitations</p>', unsafe_allow_html=True)

        message = st.session_state[SESSION_MESSAGE].strip()
        attachment_name = st.session_state.get(SESSION_ATTACHMENT_NAME)
        attachment_path = st.session_state.get(SESSION_ATTACHMENT_PATH)
        mobile_numbers = collect_mobile_numbers()
        guest_count = len(mobile_numbers)
        sent_manual = st.session_state.get(SESSION_MANUAL_SENT, set())

        if is_cloud_host():
            st.success("You are on the hosted app — use **Quick Send** below. It works on phone and laptop.")

        send_options = [SEND_MODE_QUICK]
        if auto_send_available():
            send_options.append(SEND_MODE_AUTO)

        if len(send_options) == 1:
            send_mode = SEND_MODE_QUICK
            st.caption("Quick Send is active (best for hosted & mobile use).")
        else:
            send_mode = st.radio(
                "Choose send method",
                options=send_options,
                format_func=lambda value: (
                    "Quick Send — tap each guest (recommended · phone & laptop)"
                    if value == SEND_MODE_QUICK
                    else "Auto Send — full automation (laptop only · experimental)"
                ),
                horizontal=False,
                key=SESSION_SEND_MODE,
            )

        if send_mode == SEND_MODE_QUICK:
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


def render_quick_send_panel(
    mobile_numbers: list[str],
    message: str,
    attachment_name: str | None,
    attachment_path: str | None,
    sent_manual: set[str],
    guest_count: int,
) -> None:
    st.markdown('<span class="mode-badge">Works on phone & laptop · most reliable</span>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="notice-box tip-box">
          <strong>How Quick Send works:</strong> Tap <em>Open WhatsApp</em> for each guest.
          Your message is pre-filled. Attach your video/photo once in WhatsApp (📎), tap Send,
          then come back here for the next guest. Perfect for mobile — no automation needed.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if attachment_path and os.path.exists(attachment_path):
        st.caption(f"Attachment for every guest: **{attachment_name}** ({attachment_size_label(attachment_path)})")
        with open(attachment_path, "rb") as file_handle:
            st.download_button(
                label="Download attachment (save on phone once, reuse for each guest)",
                data=file_handle.read(),
                file_name=attachment_name or "invitation_attachment",
                mime="application/octet-stream",
                use_container_width=True,
            )

    if not mobile_numbers:
        st.warning("Add guest numbers in step 2 first.")
        return

    if not validate_before_send(mobile_numbers, message, attachment_path):
        return

    sent_count = sum(1 for number in mobile_numbers if number in sent_manual)
    st.progress(sent_count / guest_count if guest_count else 0, text=f"Sent manually: {sent_count} of {guest_count}")

    col_reset, col_stats = st.columns(2)
    with col_reset:
        if st.button("Reset progress", use_container_width=True):
            reset_manual_progress()
            st.rerun()
    with col_stats:
        st.caption(f"✅ {sent_count} done · ⏳ {guest_count - sent_count} remaining")

    for index, mobile_number in enumerate(mobile_numbers, start=1):
        is_sent = mobile_number in sent_manual
        card_class = "guest-card guest-card--sent" if is_sent else "guest-card"
        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

        label_col, action_col = st.columns([1.2, 1])
        with label_col:
            status = "✅ Sent" if is_sent else f"Guest {index}"
            st.markdown(f"**{status}** · `{mobile_number}`")

        with action_col:
            link = wa_me_link(mobile_number, message)
            st.link_button(
                "Open WhatsApp",
                link,
                use_container_width=True,
                help="Opens WhatsApp app on phone or WhatsApp Web on laptop",
            )

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if not is_sent and st.button("Mark as sent", key=f"mark_sent_{mobile_number}", use_container_width=True):
                mark_manual_sent(mobile_number)
                st.rerun()
        with btn_col2:
            st.link_button(
                "Open in browser",
                whatsapp_web_link(mobile_number, message),
                use_container_width=True,
                help="WhatsApp Web link for laptop",
            )

        st.markdown("</div>", unsafe_allow_html=True)


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
          <strong>Auto Send:</strong> Chrome will open with <strong>WhatsApp Web</strong> automatically
          (uses your normal Chrome login).{attachment_note}
          Keep this app in <strong>Edge or Brave</strong> — not Chrome. Videos must be under 100 MB.
          If this fails, use <strong>Quick Send</strong> — it always works.
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
        "Starting Chrome with WhatsApp… "
        "Chrome may close and reopen — keep this window open in Edge or Brave."
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
        layout="wide",
        initial_sidebar_state="auto",
    )

    inject_custom_styles()
    inject_pwa_meta()
    init_session_state()
    render_sidebar()
    render_hero()

    with st.container():
        render_upload_section()

    with st.container():
        render_guest_editor()

    with st.container():
        render_message_section()

    with st.container():
        render_send_section()

    render_send_log()


if __name__ == "__main__":
    main()
