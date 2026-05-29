"""Decode QR from camera/upload images (server-side, works on Streamlit Cloud)."""

from __future__ import annotations


def decode_qr_from_image(image_bytes: bytes) -> str | None:
    """Server-side decode fallback (camera photo upload)."""
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        from PIL import Image
        import io as io_module

        image = Image.open(io_module.BytesIO(image_bytes))
        codes = pyzbar_decode(image)
        for code in codes:
            text = code.data.decode("utf-8", errors="ignore").strip()
            if text:
                return text
    except Exception:
        pass
    return None
