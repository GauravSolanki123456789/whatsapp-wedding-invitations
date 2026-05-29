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


    return None


def _column_name_matches(column: object, candidates: list[str]) -> bool:
    key = str(column).strip().lower().replace(" ", "_")
    return key in candidates or any(candidate in key for candidate in candidates)


def detect_mobile_column(dataframe: pd.DataFrame, country_code: str):
    """Pick the column that most likely contains phone numbers."""
    for column in dataframe.columns:
        if _column_name_matches(
            column,
            ["mobile_number", "mobile", "phone", "contact", "whatsapp", "number", "cell"],
        ):
            return column

    best_column = None
    best_score = 0
    for column in dataframe.columns:
        score = sum(
            1
            for value in dataframe[column].head(100)
            if normalize_mobile_number(value, country_code)
        )
        if score > best_score:
            best_score = score
            best_column = column
    return best_column if best_score > 0 else None


def detect_name_column(dataframe: pd.DataFrame, mobile_column) -> object | None:
    if mobile_column is None:
        return None
    for column in dataframe.columns:
        if column == mobile_column:
            continue
        if _column_name_matches(column, ["guest_name", "name", "guest", "invitee"]):
            return column
    for column in dataframe.columns:
        if column == mobile_column:
            continue
        return column
    return None


def parse_guest_rows_from_excel(
    file_bytes: bytes,
    country_code: str,
) -> tuple[list[dict[str, str]], str | None]:
    """
    Parse Excel into guest rows with mobile_number (+ optional guest_name).
    Handles S.No | Name | Mobile layouts and header/no-header files.
    """
    from constants import GUEST_NAME_COLUMN

    buffer = io.BytesIO(file_bytes)
    dataframe = pd.read_excel(buffer, engine="openpyxl", header=0)
    if dataframe.empty:
        return [], "The Excel file is empty."

    mobile_column = detect_mobile_column(dataframe, country_code)
    if mobile_column is None:
        buffer.seek(0)
        dataframe = pd.read_excel(buffer, engine="openpyxl", header=None)
        mobile_column = detect_mobile_column(dataframe, country_code)

    if mobile_column is None:
        return [], "Could not find a column with mobile numbers."

    name_column = detect_name_column(dataframe, mobile_column)
    members: list[dict[str, str]] = []
    for _, row in dataframe.iterrows():
        mobile = normalize_mobile_number(row[mobile_column], country_code)
        if not mobile:
            continue
        guest_name = ""
        if name_column is not None and pd.notna(row[name_column]):
            raw_name = str(row[name_column]).strip()
            if raw_name.lower() not in {"nan", "none"} and not re.fullmatch(r"\d+\.?\d*", raw_name):
                guest_name = raw_name
        members.append({GUEST_NAME_COLUMN: guest_name, MOBILE_NUMBER_COLUMN: mobile})

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for member in members:
        number = member[MOBILE_NUMBER_COLUMN]
        if number not in seen:
            seen.add(number)
            unique.append(member)

    if not unique:
        return [], "No valid mobile numbers found in the Excel file."
    return unique, None


def extract_mobile_numbers_from_excel(
    uploaded_file: bytes,
    country_code: str,
) -> pd.DataFrame:
    """Read an Excel file and return a guest-list DataFrame (mobile numbers)."""
    members, error = parse_guest_rows_from_excel(uploaded_file, country_code)
    if error:
        raise ValueError(error)
    return pd.DataFrame({MOBILE_NUMBER_COLUMN: [row[MOBILE_NUMBER_COLUMN] for row in members]})


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
