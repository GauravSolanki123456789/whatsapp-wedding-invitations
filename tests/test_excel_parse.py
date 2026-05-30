"""Tests for Excel guest parsing."""

from __future__ import annotations

import io
import unittest

import pandas as pd

from constants import GUEST_NAME_COLUMN, MOBILE_NUMBER_COLUMN
from utils import parse_guest_rows_from_excel


class ExcelParseTests(unittest.TestCase):
    def _excel_bytes(self, rows: list[list[object]], header: bool = True) -> bytes:
        buffer = io.BytesIO()
        df = pd.DataFrame(rows[1:], columns=rows[0] if header else None)
        if not header:
            df = pd.DataFrame(rows)
        df.to_excel(buffer, index=False, header=header)
        return buffer.getvalue()

    def test_serial_name_mobile_columns(self) -> None:
        file_bytes = self._excel_bytes(
            [
                ["S.No", "Name", "Mobile"],
                [1, "Arvind Bothra", "9444468051"],
                [2, "Ashok Bothra", "8438316166"],
            ]
        )
        members, error = parse_guest_rows_from_excel(file_bytes, "+91")
        self.assertIsNone(error)
        self.assertEqual(len(members), 2)
        self.assertEqual(members[0][GUEST_NAME_COLUMN], "Arvind Bothra")
        self.assertTrue(members[0][MOBILE_NUMBER_COLUMN].startswith("+91"))

    def test_no_guest_name_mobile_columns(self) -> None:
        file_bytes = self._excel_bytes(
            [
                ["No", "guest_name", "mobile_number"],
                [1, "INDRA BAI JI RANKA", "9848545840"],
                [2, "NAVRATAN JI RANKA", "9393144433"],
            ]
        )
        members, error = parse_guest_rows_from_excel(file_bytes, "+91")
        self.assertIsNone(error)
        self.assertEqual(members[0][GUEST_NAME_COLUMN], "INDRA BAI JI RANKA")
        self.assertEqual(members[1][GUEST_NAME_COLUMN], "NAVRATAN JI RANKA")

    def test_skips_serial_numbers_as_names(self) -> None:
        file_bytes = self._excel_bytes(
            [
                ["ColA", "ColB"],
                [2, "9444468051"],
                [3, "8438316166"],
            ]
        )
        members, error = parse_guest_rows_from_excel(file_bytes, "+91")
        self.assertIsNone(error)
        self.assertEqual(members[0][GUEST_NAME_COLUMN], "")


if __name__ == "__main__":
    unittest.main()
