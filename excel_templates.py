"""Sample Excel templates for guest lists and gift tracking."""

from __future__ import annotations

import io

import pandas as pd

from constants import GIFT_QUANTITY_COLUMN, GUEST_NAME_COLUMN, MOBILE_NUMBER_COLUMN


def guest_list_template_bytes() -> bytes:
    dataframe = pd.DataFrame(
        {
            GUEST_NAME_COLUMN: ["Ramesh Kumar", "Priya Shah", ""],
            MOBILE_NUMBER_COLUMN: ["9876543210", "9123456789", "9988776655"],
        }
    )
    return _dataframe_to_xlsx(dataframe)


def gift_guest_template_bytes() -> bytes:
    dataframe = pd.DataFrame(
        {
            GUEST_NAME_COLUMN: ["Ramesh Kumar", "Priya Shah", "Guest without name"],
            MOBILE_NUMBER_COLUMN: ["9876543210", "9123456789", "9988776655"],
            GIFT_QUANTITY_COLUMN: [1, 2, 4],
        }
    )
    return _dataframe_to_xlsx(dataframe)


def _dataframe_to_xlsx(dataframe: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Guests")
    return buffer.getvalue()
