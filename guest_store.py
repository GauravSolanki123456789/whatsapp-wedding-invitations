"""Persist guest list between app refreshes."""

from __future__ import annotations

import json
import os

import pandas as pd

from constants import GUEST_LIST_FILE, MOBILE_NUMBER_COLUMN

GUEST_LIST_DATA_KEY = "guest_list"


def load_guest_list() -> pd.DataFrame:
    if not os.path.exists(GUEST_LIST_FILE):
        return pd.DataFrame(columns=[MOBILE_NUMBER_COLUMN])

    try:
        with open(GUEST_LIST_FILE, encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except (json.JSONDecodeError, OSError):
        return pd.DataFrame(columns=[MOBILE_NUMBER_COLUMN])

    rows = data.get(GUEST_LIST_DATA_KEY, [])
    if not rows:
        return pd.DataFrame(columns=[MOBILE_NUMBER_COLUMN])

    return pd.DataFrame({MOBILE_NUMBER_COLUMN: rows})


def save_guest_list(guest_list: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(GUEST_LIST_FILE), exist_ok=True)
    numbers: list[str] = []
    if guest_list is not None and MOBILE_NUMBER_COLUMN in guest_list.columns:
        for raw_value in guest_list[MOBILE_NUMBER_COLUMN]:
            value = str(raw_value).strip() if raw_value is not None else ""
            if value and value.lower() not in {"nan", "none"}:
                numbers.append(value)

    payload = {GUEST_LIST_DATA_KEY: numbers}
    with open(GUEST_LIST_FILE, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)
