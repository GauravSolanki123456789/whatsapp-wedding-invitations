"""Per-family session state and UI flash messages."""

from __future__ import annotations

import streamlit as st

from constants import (
    SESSION_ACTIVE_FAMILY_ID,
    SESSION_FLASH_MESSAGE,
    SESSION_FLASH_TYPE,
    SESSION_MAIN_NAV_TAB,
    SESSION_PENDING_NAV_TAB,
)


def family_guest_list_key(family_id: int) -> str:
    return f"active_guest_list_id_{family_id}"


def family_function_key(family_id: int) -> str:
    return f"active_function_id_{family_id}"


def family_use_named_list_key(family_id: int) -> str:
    return f"use_named_list_{family_id}"


def family_message_key(family_id: int) -> str:
    return f"message_{family_id}"


def family_manual_sent_key(family_id: int) -> str:
    return f"manual_sent_{family_id}"


def get_active_guest_list_id(family_id: int, list_ids: list[int]) -> int | None:
    key = family_guest_list_key(family_id)
    active = st.session_state.get(key)
    if active in list_ids:
        return int(active)
    if list_ids:
        st.session_state[key] = list_ids[0]
        return list_ids[0]
    st.session_state.pop(key, None)
    return None


def get_active_function_id(family_id: int, function_ids: list[int]) -> int | None:
    key = family_function_key(family_id)
    active = st.session_state.get(key)
    if active in function_ids:
        return int(active)
    if function_ids:
        st.session_state[key] = function_ids[0]
        return function_ids[0]
    st.session_state.pop(key, None)
    return None


def set_active_guest_list_id(family_id: int, list_id: int) -> None:
    st.session_state[family_guest_list_key(family_id)] = list_id


def set_active_function_id(family_id: int, function_id: int) -> None:
    st.session_state[family_function_key(family_id)] = function_id


def use_named_list_for_family(family_id: int) -> bool:
    return bool(st.session_state.get(family_use_named_list_key(family_id), False))


def set_use_named_list_for_family(family_id: int, value: bool) -> None:
    st.session_state[family_use_named_list_key(family_id)] = value


def get_family_message(family_id: int) -> str:
    return str(st.session_state.get(family_message_key(family_id), ""))


def set_family_message(family_id: int, message: str) -> None:
    st.session_state[family_message_key(family_id)] = message


def get_family_manual_sent(family_id: int) -> set[str]:
    raw = st.session_state.get(family_manual_sent_key(family_id))
    if isinstance(raw, set):
        return raw
    return set()


def set_family_manual_sent(family_id: int, numbers: set[str]) -> None:
    st.session_state[family_manual_sent_key(family_id)] = numbers


def mark_family_manual_sent(family_id: int, mobile_number: str) -> None:
    sent = get_family_manual_sent(family_id)
    sent.add(mobile_number)
    set_family_manual_sent(family_id, sent)


def reset_family_manual_sent(family_id: int) -> None:
    set_family_manual_sent(family_id, set())


def set_flash(message: str, level: str = "success") -> None:
    st.session_state[SESSION_FLASH_MESSAGE] = message
    st.session_state[SESSION_FLASH_TYPE] = level


def render_flash() -> None:
    message = st.session_state.pop(SESSION_FLASH_MESSAGE, None)
    level = st.session_state.pop(SESSION_FLASH_TYPE, "success")
    if not message:
        return
    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    elif level == "info":
        st.info(message)
    else:
        st.success(message)


def go_to_tab(tab_name: str) -> None:
    """Schedule tab change before widgets render on the next rerun."""
    st.session_state[SESSION_PENDING_NAV_TAB] = tab_name


def apply_pending_nav() -> None:
    """Apply a pending tab switch — call once at start of main(), before st.radio."""
    pending = st.session_state.pop(SESSION_PENDING_NAV_TAB, None)
    if pending:
        st.session_state[SESSION_MAIN_NAV_TAB] = pending


def sync_family_selector_widget(families: list[dict]) -> None:
    """Keep family dropdown aligned with SESSION_ACTIVE_FAMILY_ID."""
    id_to_name = {int(f["id"]): f["name"] for f in families}
    valid_ids = set(id_to_name.keys())
    current_id = st.session_state.get(SESSION_ACTIVE_FAMILY_ID)
    if current_id not in valid_ids and families:
        current_id = int(families[0]["id"])
        st.session_state[SESSION_ACTIVE_FAMILY_ID] = current_id
    current_name = id_to_name.get(int(current_id), families[0]["name"] if families else "")
    if st.session_state.get("family_selector_widget") != current_name:
        st.session_state["family_selector_widget"] = current_name


def sync_list_selector_widget(family_id: int, lists: list[dict]) -> None:
    """Keep list dropdown aligned with per-family active list id."""
    list_options = {f"{row['name']} ({row['member_count']})": int(row["id"]) for row in lists}
    if not list_options:
        return
    list_ids = list(list_options.values())
    active_id = get_active_guest_list_id(family_id, list_ids)
    id_to_label = {list_id: label for label, list_id in list_options.items()}
    active_label = id_to_label.get(int(active_id), next(iter(list_options.keys())))
    widget_key = f"list_select_{family_id}"
    if st.session_state.get(widget_key) != active_label:
        st.session_state[widget_key] = active_label


def family_guest_df_key(family_id: int) -> str:
    return f"guest_df_{family_id}"


def get_family_guest_df(family_id: int):
    import pandas as pd

    from constants import MOBILE_NUMBER_COLUMN

    key = family_guest_df_key(family_id)
    df = st.session_state.get(key)
    if df is None:
        df = pd.DataFrame(columns=[MOBILE_NUMBER_COLUMN])
        st.session_state[key] = df
    return df


def set_family_guest_df(family_id: int, df) -> None:
    st.session_state[family_guest_df_key(family_id)] = df
