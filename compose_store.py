"""Persist and restore the last composed invitation message and attachment."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from constants import LAST_ATTACHMENT_DIR, LAST_COMPOSE_FILE

COMPOSE_MESSAGE_KEY = "message"
COMPOSE_ATTACHMENT_PATH_KEY = "attachment_path"
COMPOSE_ATTACHMENT_NAME_KEY = "attachment_name"


def _empty_compose() -> dict[str, str | None]:
    return {
        COMPOSE_MESSAGE_KEY: "",
        COMPOSE_ATTACHMENT_PATH_KEY: None,
        COMPOSE_ATTACHMENT_NAME_KEY: None,
    }


def load_last_compose() -> dict[str, str | None]:
    """Load the last saved invitation message and attachment from disk."""
    if not os.path.exists(LAST_COMPOSE_FILE):
        return _empty_compose()

    try:
        with open(LAST_COMPOSE_FILE, encoding="utf-8") as file_handle:
            data = json.load(file_handle)
    except (json.JSONDecodeError, OSError):
        return _empty_compose()

    attachment_path = data.get(COMPOSE_ATTACHMENT_PATH_KEY)
    if attachment_path and not os.path.exists(attachment_path):
        attachment_path = None
        data[COMPOSE_ATTACHMENT_NAME_KEY] = None

    return {
        COMPOSE_MESSAGE_KEY: data.get(COMPOSE_MESSAGE_KEY, "") or "",
        COMPOSE_ATTACHMENT_PATH_KEY: attachment_path,
        COMPOSE_ATTACHMENT_NAME_KEY: data.get(COMPOSE_ATTACHMENT_NAME_KEY),
    }


def save_last_compose(
    message: str,
    attachment_path: str | None,
    attachment_name: str | None,
) -> None:
    """Save the last sent invitation so it is restored on the next app open."""
    os.makedirs(Path(LAST_COMPOSE_FILE).parent, exist_ok=True)
    os.makedirs(LAST_ATTACHMENT_DIR, exist_ok=True)

    persisted_attachment_path: str | None = None
    persisted_attachment_name: str | None = None

    if attachment_path and attachment_name and os.path.exists(attachment_path):
        safe_name = Path(attachment_name).name
        destination = os.path.join(LAST_ATTACHMENT_DIR, safe_name)
        shutil.copy2(attachment_path, destination)
        persisted_attachment_path = destination
        persisted_attachment_name = safe_name

    payload = {
        COMPOSE_MESSAGE_KEY: message,
        COMPOSE_ATTACHMENT_PATH_KEY: persisted_attachment_path,
        COMPOSE_ATTACHMENT_NAME_KEY: persisted_attachment_name,
    }

    with open(LAST_COMPOSE_FILE, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)


def clear_last_compose_attachment() -> None:
    """Remove the saved attachment while keeping the last message."""
    compose = load_last_compose()

    attachment_path = compose.get(COMPOSE_ATTACHMENT_PATH_KEY)
    if attachment_path and os.path.exists(attachment_path):
        os.remove(attachment_path)

    save_last_compose(
        message=str(compose.get(COMPOSE_MESSAGE_KEY, "")),
        attachment_path=None,
        attachment_name=None,
    )
