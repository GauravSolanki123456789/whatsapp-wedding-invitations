"""Utility helpers for parsing guest lists and normalizing phone numbers."""

from __future__ import annotations

import io
import os
import re
import shutil
from pathlib import Path
from typing import Iterable

import pandas as pd

from constants import (
    ATTACHMENT_FOLDER,
    ATTACHMENT_UPLOAD_STAGING_DIR,
    ATTACHMENT_UPLOAD_STAGING_NAME,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    MOBILE_NUMBER_COLUMN,
    VIDEO_EXTENSIONS,
    WHATSAPP_MAX_DOCUMENT_MB,
    WHATSAPP_MAX_IMAGE_MB,
    WHATSAPP_MAX_VIDEO_MB,
)


def phone_for_wa_link(mobile_number: str) -> str:
    return mobile_number.lstrip("+").replace(" ", "")


def normalize_mobile_number(raw_value: object, country_code: str) -> str | None:
    """Convert a raw Excel cell value into a WhatsApp-ready international number."""
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return None

    value = str(raw_value).strip()
    if not value or value.lower() in {"nan", "none", ""}:
        return None

    # Pandas often reads numbers as floats (e.g. 919876543210.0)
    if re.fullmatch(r"\d+\.0", value):
        value = value[:-2]

    value = re.sub(r"[\s\-().]", "", value)

    if value.startswith("+"):
        normalized = value
    else:
        code = country_code if country_code.startswith("+") else f"+{country_code}"
        if value.startswith("0"):
            value = value[1:]
        normalized = f"{code}{value}"

    if re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        return normalized
    return None


def extract_mobile_numbers_from_excel(
    uploaded_file: bytes,
    country_code: str,
) -> pd.DataFrame:
    """Read the second column of an Excel file and return a guest-list DataFrame."""
    file_buffer = io.BytesIO(uploaded_file)
    dataframe = pd.read_excel(file_buffer, engine="openpyxl", header=None)

    if dataframe.shape[1] < 2:
        raise ValueError(
            "The Excel file must have at least two columns. "
            "Column 1 is ignored; column 2 should contain mobile numbers."
        )

    second_column = dataframe.iloc[:, 1]
    normalized_numbers: list[str] = []

    for raw_value in second_column:
        mobile_number = normalize_mobile_number(raw_value, country_code)
        if mobile_number:
            normalized_numbers.append(mobile_number)

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_numbers: list[str] = []
    for number in normalized_numbers:
        if number not in seen:
            seen.add(number)
            unique_numbers.append(number)

    return pd.DataFrame({MOBILE_NUMBER_COLUMN: unique_numbers})


def guest_list_from_dataframe(dataframe: pd.DataFrame) -> list[str]:
    """Extract a clean, de-duplicated list of mobile numbers from the editor DataFrame."""
    if dataframe is None or dataframe.empty:
        return []

    if MOBILE_NUMBER_COLUMN not in dataframe.columns:
        return []

    seen: set[str] = set()
    result: list[str] = []

    for raw_value in dataframe[MOBILE_NUMBER_COLUMN]:
        value = str(raw_value).strip() if raw_value is not None else ""
        if not value or value.lower() in {"nan", "none"}:
            continue
        if value not in seen:
            seen.add(value)
            result.append(value)

    return result


def count_invalid_numbers(numbers: Iterable[str]) -> int:
    """Return how many numbers fail the international phone format check."""
    pattern = re.compile(r"^\+[1-9]\d{7,14}$")
    return sum(1 for number in numbers if not pattern.fullmatch(number))


def attachment_kind_from_path(attachment_path: str) -> str:
    suffix = Path(attachment_path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    raise ValueError(f"Unsupported attachment type: {suffix}")


def attachment_size_mb(attachment_path: str) -> float:
    return os.path.getsize(attachment_path) / (1024 * 1024)


def attachment_size_label(attachment_path: str) -> str:
    size_mb = attachment_size_mb(attachment_path)
    if size_mb >= 1:
        return f"{size_mb:.1f} MB"
    return f"{size_mb * 1024:.0f} KB"


def prepare_upload_attachment_path(attachment_path: str) -> str:
    """
    Copy attachment to a simple staging path for Selenium file inputs.
    Windows + Chrome often fail on paths with spaces or parentheses in the filename.
    Reuses the cached copy when the source file has not changed.
    """
    source = Path(attachment_path)
    if not source.is_file():
        raise FileNotFoundError(f"Attachment not found: {attachment_path}")

    staging_dir = Path(ATTACHMENT_UPLOAD_STAGING_DIR)
    staging_dir.mkdir(parents=True, exist_ok=True)
    destination = staging_dir / f"{ATTACHMENT_UPLOAD_STAGING_NAME}{source.suffix.lower()}"

    if destination.exists():
        source_stat = source.stat()
        dest_stat = destination.stat()
        if (
            dest_stat.st_size == source_stat.st_size
            and dest_stat.st_mtime >= source_stat.st_mtime
        ):
            return str(destination.resolve())

    if destination.exists():
        destination.unlink()
    shutil.copy2(source, destination)
    return str(destination.resolve())


def validate_attachment_for_whatsapp(attachment_path: str) -> str | None:
    """Return an error message when the attachment exceeds WhatsApp limits."""
    kind = attachment_kind_from_path(attachment_path)
    size_mb = attachment_size_mb(attachment_path)

    limits = {
        "video": WHATSAPP_MAX_VIDEO_MB,
        "document": WHATSAPP_MAX_DOCUMENT_MB,
        "image": WHATSAPP_MAX_IMAGE_MB,
    }
    limit_mb = limits[kind]
    if size_mb > limit_mb:
        label = attachment_size_label(attachment_path)
        return (
            f"This {kind} is {label}. WhatsApp Web allows up to {limit_mb} MB. "
            "Compress the file before sending."
        )
    return None
