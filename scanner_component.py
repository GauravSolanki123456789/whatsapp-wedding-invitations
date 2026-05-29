"""Live QR scanner component (back camera) and photo decode fallback."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).parent / "components" / "qr_live_scanner"
_qr_live_scanner = components.declare_component(
    "qr_live_scanner",
    path=str(_COMPONENT_DIR),
)


def render_live_qr_scanner(key: str = "qr_live_scanner") -> str | None:
    """
    Live back-camera QR scan. Returns scanned text instantly via Streamlit component
    bridge (no full page reload).
    """
    result = _qr_live_scanner(key=key, default=None)
    if result is None:
        return None
    text = str(result).strip()
    return text or None


def decode_qr_from_image(image_bytes: bytes) -> str | None:
    """Server-side decode fallback (camera photo upload)."""
    try:
        import io as io_module

        from PIL import Image
        from pyzbar.pyzbar import decode as pyzbar_decode

        image = Image.open(io_module.BytesIO(image_bytes))
        codes = pyzbar_decode(image)
        for code in codes:
            text = code.data.decode("utf-8", errors="ignore").strip()
            if text:
                return text
    except Exception:
        pass
    return None
