"""Detect whether the app runs locally or on a free cloud host."""

from __future__ import annotations

import os
import platform


def is_cloud_host() -> bool:
    """True when running on Streamlit Community Cloud or similar."""
    if os.environ.get("STREAMLIT_CLOUD") == "1":
        return True
    if os.path.isdir("/mount/src"):
        return True
    hostname = os.environ.get("HOSTNAME", "").lower()
    return "streamlit" in hostname or "onrender" in hostname


def auto_send_available() -> bool:
    """Chrome automation only works on a local Windows machine."""
    return platform.system() == "Windows" and not is_cloud_host()


def default_send_mode() -> str:
    """Guided Send on hosted/mobile-friendly deploys; Quick Send locally."""
    from constants import SEND_MODE_GUIDED, SEND_MODE_QUICK

    return SEND_MODE_GUIDED if is_cloud_host() else SEND_MODE_QUICK
