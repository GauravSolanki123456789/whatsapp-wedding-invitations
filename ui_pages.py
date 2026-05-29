"""Tab panels: families, lists, functions, scan, reports, integrations."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from constants import (
    GIFT_QUANTITY_COLUMN,
    GUEST_NAME_COLUMN,
    MOBILE_NUMBER_COLUMN,
    SESSION_ACTIVE_FAMILY_ID,
    SESSION_ACTIVE_FUNCTION_ID,
    SESSION_ACTIVE_GUEST_LIST_ID,
    SESSION_COUNTRY_CODE,
    SESSION_SCAN_COMPONENT_KEY,
    SESSION_SCAN_LOOKUP_GUEST,
    SESSION_SCAN_PASTE_KEY,
    SESSION_SCAN_PHOTO_KEY,
    SESSION_SCAN_UPLOAD_KEY,
    SESSION_SCANNER_STAFF_NAME,
    SESSION_USE_NAMED_LIST,
)
from excel_templates import gift_guest_template_bytes, guest_list_template_bytes
from family_service import create_family, delete_family, list_families
from gift_service import (
    create_function,
    delete_function,
    function_report,
    import_gift_guests_from_excel,
    list_functions,
    list_gift_guests,
    regenerate_all_qr_tokens,
)
from integrations import integration_status, send_whatsapp_template_message
from named_guest_list_service import (
    create_guest_list,
    delete_guest_list,
    get_guest_list_members,
    import_excel_to_guest_list,
    list_guest_lists,
)
from qr_utils import build_qr_zip_for_function, generate_guest_qr_card
from scan_flow import (
    apply_scan_raw,
    clear_scan_for_next_guest,
    confirm_handout,
    handle_live_scan_result,
    process_image_bytes,
    refresh_lookup_guest,
)
from scanner_component import render_live_qr_scanner
from wa_links import wa_me_link


def render_database_status() -> None:
    from database import get_database_status

    status = get_database_status()
    level_class = {
        "ok": "stat-pill--ok",
        "warn": "stat-pill--warn",
        "info": "",
    }.get(status["level"], "")
    st.markdown(
        f'<span class="stat-pill {level_class}">{status["label"]}</span>',
        unsafe_allow_html=True,
    )
    st.caption(status["detail"])


def render_family_selector() -> int:
    families = list_families()
    if not families:
        from database import ensure_default_family

        ensure_default_family()
        families = list_families()

    names = {f["name"]: f["id"] for f in families}
    current_id = st.session_state.get(SESSION_ACTIVE_FAMILY_ID)
    if current_id not in names.values():
        current_id = families[0]["id"]
        st.session_state[SESSION_ACTIVE_FAMILY_ID] = current_id

    current_name = next((f["name"] for f in families if f["id"] == current_id), families[0]["name"])

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_name = st.selectbox(
            "Family",
            options=list(names.keys()),
            index=list(names.keys()).index(current_name) if current_name in names else 0,
            label_visibility="collapsed",
        )
        st.session_state[SESSION_ACTIVE_FAMILY_ID] = names[selected_name]
    with col2:
        st.caption(f"{len(families)} famil{'ies' if len(families) != 1 else 'y'}")

    return int(st.session_state[SESSION_ACTIVE_FAMILY_ID])


def render_families_tab(family_id: int) -> None:
    st.markdown('<p class="section-title">Families</p>', unsafe_allow_html=True)
    st.markdown(
        '<div class="notice-box info-box">Each family has its own lists, functions, and gift data.</div>',
        unsafe_allow_html=True,
    )

    new_name = st.text_input("New family name", placeholder="e.g. Lalwani Family")
    if st.button("Add family", use_container_width=True) and new_name:
        _, err = create_family(new_name)
        if err:
            st.error(err)
        else:
            st.success(f"Added **{new_name}**")
            st.rerun()

    families = list_families()
    for family in families:
        if family["id"] == family_id:
            st.info(f"Active: **{family['name']}**")
        else:
            st.caption(f"• {family['name']}")

    if len(families) > 1:
        if st.button("Delete current family", use_container_width=True):
            from family_service import delete_family

            err = delete_family(family_id)
            if err:
                st.error(err)
            else:
                st.session_state[SESSION_ACTIVE_FAMILY_ID] = None
                st.rerun()


def render_lists_tab(family_id: int) -> None:
    st.markdown('<p class="section-title">Saved guest lists</p>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "Sample Excel (lists)",
            data=guest_list_template_bytes(),
            file_name="guest_list_sample.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col_b:
        st.session_state[SESSION_USE_NAMED_LIST] = st.toggle(
            "Use saved list for Send tab",
            value=st.session_state.get(SESSION_USE_NAMED_LIST, False),
        )

    list_name = st.text_input("New list name", placeholder="e.g. Ranka Invitations")
    if st.button("Create list", use_container_width=True) and list_name:
        lid, err = create_guest_list(family_id, list_name)
        if err:
            st.error(err)
        else:
            st.session_state[SESSION_ACTIVE_GUEST_LIST_ID] = lid
            st.success(f"Created **{list_name}**")
            st.rerun()

    lists = list_guest_lists(family_id)
    if not lists:
        st.info("Create a list, then upload Excel below.")
        return

    list_options = {f"{row['name']} ({row['member_count']})": row["id"] for row in lists}
    active = st.session_state.get(SESSION_ACTIVE_GUEST_LIST_ID)
    if active not in list_options.values():
        active = lists[0]["id"]
    labels = list(list_options.keys())
    default_idx = next(
        (i for i, label in enumerate(labels) if list_options[label] == active),
        0,
    )
    chosen_label = st.selectbox("Select list", labels, index=default_idx)
    guest_list_id = list_options[chosen_label]
    st.session_state[SESSION_ACTIVE_GUEST_LIST_ID] = guest_list_id

    uploaded = st.file_uploader("Upload Excel to this list", type=["xlsx"], key="list_upload")
    if uploaded and st.button("Import into list", type="primary", use_container_width=True):
        count, err = import_excel_to_guest_list(
            guest_list_id,
            uploaded.getvalue(),
            st.session_state[SESSION_COUNTRY_CODE],
        )
        if err:
            st.error(err)
        else:
            st.success(f"Imported **{count}** guests.")
            st.rerun()

    members = get_guest_list_members(guest_list_id)
    st.dataframe(members, use_container_width=True, hide_index=True)

    if st.button("Delete this list", use_container_width=True):
        delete_guest_list(guest_list_id)
        st.session_state[SESSION_ACTIVE_GUEST_LIST_ID] = None
        st.rerun()


def render_functions_tab(family_id: int, family_name: str) -> None:
    st.markdown('<p class="section-title">Functions & gift QR</p>', unsafe_allow_html=True)

    st.download_button(
        "Sample Excel (gifts)",
        data=gift_guest_template_bytes(),
        file_name="gift_guests_sample.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    fn_name = st.text_input("New function", placeholder="e.g. Mayara, Reception")
    if st.button("Add function", use_container_width=True) and fn_name:
        fid, err = create_function(family_id, fn_name)
        if err:
            st.error(err)
        else:
            st.session_state[SESSION_ACTIVE_FUNCTION_ID] = fid
            st.rerun()

    functions = list_functions(family_id)
    if not functions:
        st.info("Add a function, then upload guests with gift quantities.")
        return

    fn_map = {f"{row['name']} ({row['guest_count']} guests)": row["id"] for row in functions}
    active_fn = st.session_state.get(SESSION_ACTIVE_FUNCTION_ID)
    if active_fn not in fn_map.values():
        active_fn = functions[0]["id"]
    fn_labels = list(fn_map.keys())
    fn_idx = next((i for i, label in enumerate(fn_labels) if fn_map[label] == active_fn), 0)
    chosen_fn = st.selectbox("Function", fn_labels, index=fn_idx)
    function_id = fn_map[chosen_fn]
    st.session_state[SESSION_ACTIVE_FUNCTION_ID] = function_id
    function_name = functions[next(i for i, f in enumerate(functions) if f["id"] == function_id)]["name"]

    replace = st.checkbox("Replace existing guests on import", value=False)
    gift_file = st.file_uploader("Upload guests for this function", type=["xlsx"], key="gift_upload")
    if gift_file and st.button("Import guests", type="primary", use_container_width=True):
        count, err = import_gift_guests_from_excel(
            function_id,
            gift_file.getvalue(),
            st.session_state[SESSION_COUNTRY_CODE],
            replace_existing=replace,
        )
        if err:
            st.error(err)
        else:
            st.success(f"Imported **{count}** guests.")
            st.rerun()

    guests = list_gift_guests(function_id)
    if not guests:
        st.warning("No guests yet. Upload Excel using the sample format.")
        return

    report = function_report(function_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Guests", report["total_guests"])
    c2.metric("Gifts given", report["total_given"])
    c3.metric("Pending", report["total_pending"])
    c4.metric("Done", report["fully_completed_guests"])

    zip_bytes = build_qr_zip_for_function(
        guests,
        {"family_name": family_name, "function_name": function_name},
    )
    st.download_button(
        "Download all QR cards (ZIP)",
        data=zip_bytes,
        file_name=f"{function_name}_qr_cards.zip",
        mime="application/zip",
        use_container_width=True,
    )

    with st.expander("Send QR via WhatsApp (one guest)", expanded=False):
        idx = st.number_input("Guest #", min_value=1, max_value=len(guests), value=1) - 1
        guest = guests[int(idx)]
        qr_png = generate_guest_qr_card(
            qr_token=guest["qr_token"],
            guest_name=guest["guest_name"],
            function_name=function_name,
            family_name=family_name,
            gift_quantity=guest["gift_quantity"],
            gifts_pending=guest["gifts_pending"],
        )
        msg = (
            f"{family_name} — {function_name}\n"
            f"Gift QR for {guest['guest_name'] or 'guest'}\n"
            f"Gifts: {guest['gift_quantity']}"
        )
        st.image(qr_png, caption="Guest QR card")
        st.download_button(
            "Download this QR PNG",
            data=qr_png,
            file_name=f"qr_{guest['id']}.png",
            mime="image/png",
            use_container_width=True,
        )
        st.link_button(
            "Open WhatsApp to this guest",
            wa_me_link(guest["mobile_number"], msg),
            use_container_width=True,
        )

    st.dataframe(
        pd.DataFrame(guests)[
            ["guest_name", "mobile_number", "gift_quantity", "gifts_given", "gifts_pending"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Regenerate all QR codes (resets gift counts)", use_container_width=True):
        n = regenerate_all_qr_tokens(function_id)
        st.warning(f"Regenerated **{n}** QR codes. Old screenshots are invalid.")
        st.rerun()

    if st.button("Delete this function", use_container_width=True):
        delete_function(function_id)
        st.session_state[SESSION_ACTIVE_FUNCTION_ID] = None
        st.rerun()


def _on_manual_scan_token() -> None:
    paste_key = f"scan_token_input_{st.session_state.get(SESSION_SCAN_PASTE_KEY, 0)}"
    raw = st.session_state.get(paste_key, "")
    if not raw.strip():
        return
    if raw.strip() == st.session_state.get("scan_last_paste_attempt"):
        return
    st.session_state["scan_last_paste_attempt"] = raw.strip()
    error = apply_scan_raw(raw)
    if error:
        st.session_state["scan_last_error"] = error
    else:
        st.session_state.pop("scan_last_error", None)
        st.rerun()


def render_scan_tab() -> None:
    st.markdown('<p class="section-title">Staff scan</p>', unsafe_allow_html=True)

    guest = st.session_state.get(SESSION_SCAN_LOOKUP_GUEST)

    if guest:
        _render_scan_handout_panel(guest)
        return

    st.markdown(
        """
        <div class="notice-box tip-box scan-hint">
          Tap <strong>Start scanner</strong> — back camera opens. Guest loads instantly on scan.
          Backup: photo or paste below.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Staff name (optional)", expanded=False):
        st.session_state[SESSION_SCANNER_STAFF_NAME] = st.text_input(
            "Logged as",
            value=st.session_state.get(SESSION_SCANNER_STAFF_NAME, ""),
            placeholder="Staff name",
            label_visibility="collapsed",
            key="scan_staff_input",
        )

    scan_error = st.session_state.pop("scan_last_error", None)
    if scan_error:
        st.error(scan_error)

    component_key = f"qr_live_{st.session_state.get(SESSION_SCAN_COMPONENT_KEY, 0)}"
    scanned = render_live_qr_scanner(key=component_key)
    if handle_live_scan_result(scanned):
        st.rerun()

    with st.expander("Photo or paste backup", expanded=False):
        st.caption("Use when live scan or camera permission fails.")

        paste_key = f"scan_token_input_{st.session_state.get(SESSION_SCAN_PASTE_KEY, 0)}"
        st.text_input(
            "Paste QR text",
            placeholder="waiv:…",
            key=paste_key,
            on_change=_on_manual_scan_token,
        )

        photo_key = f"scan_camera_{st.session_state.get(SESSION_SCAN_PHOTO_KEY, 0)}"
        photo = st.camera_input("Take photo of QR", key=photo_key)
        if photo is not None and process_image_bytes(photo.getvalue()):
            st.rerun()

        upload_key = f"scan_upload_{st.session_state.get(SESSION_SCAN_UPLOAD_KEY, 0)}"
        upload = st.file_uploader(
            "Upload QR image",
            type=["png", "jpg", "jpeg"],
            key=upload_key,
        )
        if upload is not None and process_image_bytes(upload.getvalue()):
            st.rerun()


def _render_scan_handout_panel(guest: dict) -> None:
    guest = refresh_lookup_guest() or guest
    pending = int(guest.get("gifts_pending", 0))
    name = guest.get("guest_name") or guest["mobile_number"]

    if pending <= 0:
        st.markdown(
            f"""
            <div class="focus-card focus-card--used">
              <p class="focus-meta">Already completed</p>
              <p class="focus-guest-number">{name}</p>
              <p class="focus-meta">{guest['family_name']} · {guest['function_name']}</p>
              <p class="focus-meta">All {guest['gift_quantity']} gift(s) given.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Scan next guest", type="primary", use_container_width=True, key="scan_next_done"):
            clear_scan_for_next_guest()
            st.rerun()
        return

    st.markdown(
        f"""
        <div class="focus-card focus-card--ok scan-handout-card">
          <p class="focus-meta">Hand out gifts</p>
          <p class="focus-guest-number">{name}</p>
          <p class="focus-meta">{guest['family_name']} · {guest['function_name']}</p>
          <p class="focus-meta"><strong>{pending}</strong> of {guest['gift_quantity']} pending</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    gifts_now = st.number_input(
        "Gifts giving now",
        min_value=1,
        max_value=pending,
        value=1,
        step=1,
        key="scan_gifts_now",
    )
    notes = st.text_input("Notes (optional)", key="scan_notes_handout")

    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("Confirm & next guest", type="primary", use_container_width=True):
            ok, msg = confirm_handout(guest["id"], int(gifts_now), notes)
            if ok:
                st.toast(msg, icon="✅")
                st.rerun()
            else:
                st.error(msg)
    with col_cancel:
        if st.button("Cancel", use_container_width=True, key="scan_cancel_handout"):
            clear_scan_for_next_guest()
            st.rerun()


def render_reports_tab(family_id: int) -> None:
    st.markdown('<p class="section-title">Reports</p>', unsafe_allow_html=True)
    functions = list_functions(family_id)
    if not functions:
        st.info("No functions yet.")
        return

    for fn in functions:
        report = function_report(fn["id"])
        with st.expander(f"{fn['name']} — {report['total_given']}/{report['total_allocated']} gifts given"):
            st.metric("Guests fully served", report["fully_completed_guests"])
            st.metric("Gifts still pending", report["total_pending"])
            df = pd.DataFrame(report["guests"])
            if not df.empty:
                st.dataframe(
                    df[
                        [
                            "guest_name",
                            "mobile_number",
                            "gift_quantity",
                            "gifts_given",
                            "gifts_pending",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            csv = df.to_csv(index=False).encode("utf-8") if not df.empty else b""
            if csv:
                st.download_button(
                    f"Download {fn['name']} CSV",
                    data=csv,
                    file_name=f"{fn['name']}_gift_report.csv",
                    mime="text/csv",
                    key=f"csv_{fn['id']}",
                    use_container_width=True,
                )


def render_integrations_tab() -> None:
    st.markdown('<p class="section-title">API & calls</p>', unsafe_allow_html=True)
    status = integration_status()
    st.markdown(f"**WhatsApp Cloud API:** {status.whatsapp_detail}")
    st.markdown(f"**Voice calls (Twilio):** {status.voice_detail}")
    st.markdown(
        '<div class="notice-box info-box">See <strong>GUIDE.md</strong> in the project for setup steps and costs.</div>',
        unsafe_allow_html=True,
    )

    if status.whatsapp_api:
        template = st.text_input("Approved template name", value="hello_world")
        test_number = st.text_input("Test number (+91…)", value="+91")
        if st.button("Send test template", use_container_width=True):
            ok, detail = send_whatsapp_template_message(test_number, template)
            if ok:
                st.success("Sent.")
            else:
                st.error(detail)
