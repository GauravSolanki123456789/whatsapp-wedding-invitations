"""Tests for vCard contact naming."""

from __future__ import annotations

import unittest

from constants import GUEST_NAME_COLUMN, MOBILE_NUMBER_COLUMN
from group_contacts import build_guest_vcard, format_vcard_contact_name, vcard_download_filename


class VCardContactTests(unittest.TestCase):
    def test_format_name_with_list_label(self) -> None:
        name = format_vcard_contact_name("INDRA BAI JI RANKA", "Rankalist", 1)
        self.assertEqual(name, "INDRA BAI JI RANKA Rankalist")

    def test_format_fallback_without_guest_name(self) -> None:
        name = format_vcard_contact_name("", "Rankalist", 5)
        self.assertEqual(name, "Wedding Guest 5 Rankalist")

    def test_build_vcard_uses_guest_names(self) -> None:
        guests = [
            {GUEST_NAME_COLUMN: "INDRA BAI JI RANKA", MOBILE_NUMBER_COLUMN: "+919876543210"},
            {GUEST_NAME_COLUMN: "NAVRATAN JI RANKA", MOBILE_NUMBER_COLUMN: "+919876543211"},
        ]
        vcard = build_guest_vcard(guests, list_label="Rankalist")
        self.assertIn("FN:INDRA BAI JI RANKA Rankalist", vcard)
        self.assertIn("FN:NAVRATAN JI RANKA Rankalist", vcard)
        self.assertNotIn("Wedding Guest 1 Rankalist", vcard)

    def test_vcard_filename_slug(self) -> None:
        self.assertEqual(vcard_download_filename("Rankalist"), "rankalist_contacts.vcf")


if __name__ == "__main__":
    unittest.main()
