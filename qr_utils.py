"""Generate QR code images and guest cards for WhatsApp sharing."""

from __future__ import annotations

import io
import zipfile
from typing import Any

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_M

from constants import QR_TOKEN_PREFIX


def qr_payload_from_token(qr_token: str) -> str:
    """Compact payload encoded in the QR (scanned by staff app)."""
    return qr_token.strip()


def parse_scanned_payload(raw: str) -> str | None:
    text = (raw or "").strip()
    if not text:
        return None
    if QR_TOKEN_PREFIX in text:
        idx = text.find(QR_TOKEN_PREFIX)
        fragment = text[idx:].split()[0].strip()
        return fragment
    return text if text.startswith(QR_TOKEN_PREFIX) else f"{QR_TOKEN_PREFIX}{text}"


def generate_qr_image(
    qr_token: str,
    size_px: int = 400,
) -> bytes:
    payload = qr_payload_from_token(qr_token)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size_px, size_px), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_guest_qr_card(
    *,
    qr_token: str,
    guest_name: str,
    function_name: str,
    family_name: str,
    gift_quantity: int,
    gifts_pending: int | None = None,
) -> bytes:
    """PNG card: family, function, guest, quantity — easy to screenshot on WhatsApp."""
    width, height = 720, 900
    img = Image.new("RGB", (width, height), "#FFFBF7")
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
        body_font = ImageFont.truetype("arial.ttf", 28)
        small_font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = title_font
        small_font = title_font

    draw.rectangle([(0, 0), (width, 120)], fill="#B76E79")
    draw.text((40, 40), family_name[:40], fill="white", font=title_font)

    y = 150
    for label, value in [
        ("Function", function_name),
        ("Guest", guest_name or "Guest"),
        ("Total gifts", str(gift_quantity)),
    ]:
        draw.text((40, y), f"{label}:", fill="#6B5B52", font=small_font)
        draw.text((40, y + 28), str(value)[:50], fill="#2C2416", font=body_font)
        y += 90

    qr_bytes = generate_qr_image(qr_token, size_px=320)
    qr_img = Image.open(io.BytesIO(qr_bytes))
    img.paste(qr_img, ((width - 320) // 2, y + 10))

    pending = gifts_pending if gifts_pending is not None else gift_quantity
    draw.text(
        (40, height - 80),
        "Show this QR to staff at the venue.",
        fill="#6B5B52",
        font=small_font,
    )
    draw.text(
        (40, height - 48),
        f"Pending gifts when issued: {pending}",
        fill="#5C3D42",
        font=small_font,
    )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def build_qr_zip_for_function(guests: list[dict[str, Any]], meta: dict[str, str]) -> bytes:
    """ZIP of PNG cards — one file per guest."""
    buffer = io.BytesIO()
    family_name = meta.get("family_name", "Family")
    function_name = meta.get("function_name", "Function")
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for guest in guests:
            safe_name = _safe_filename(guest.get("guest_name") or guest["mobile_number"])
            png = generate_guest_qr_card(
                qr_token=guest["qr_token"],
                guest_name=guest.get("guest_name", ""),
                function_name=function_name,
                family_name=family_name,
                gift_quantity=guest["gift_quantity"],
                gifts_pending=guest.get("gifts_pending", guest["gift_quantity"]),
            )
            archive.writestr(f"{safe_name}_{guest['id']}.png", png)
    return buffer.getvalue()


def _safe_filename(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_" else "_" for character in value)
    return cleaned[:40] or "guest"
