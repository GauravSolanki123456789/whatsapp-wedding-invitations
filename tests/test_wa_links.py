"""Unit tests for WhatsApp link generation."""

from __future__ import annotations

import unittest

from constants import WHATSAPP_APP_BUSINESS, WHATSAPP_APP_PERSONAL
from wa_links import (
    wa_business_android_link,
    wa_me_link,
    wa_personal_android_link,
    whatsapp_guest_link,
)


class WhatsAppLinkTests(unittest.TestCase):
    def test_default_without_sender_uses_wa_me(self) -> None:
        guest = "+919876543210"
        message = "Hello"
        link = whatsapp_guest_link(guest, message, WHATSAPP_APP_PERSONAL, sender_phone="")
        self.assertEqual(link, wa_me_link(guest, message))

    def test_personal_sender_uses_personal_android_intent(self) -> None:
        link = whatsapp_guest_link(
            "+919876543210",
            "Hi",
            WHATSAPP_APP_PERSONAL,
            sender_phone="+919841166662",
        )
        self.assertIn("com.whatsapp;end", link)
        self.assertNotIn("w4b", link)

    def test_business_sender_uses_business_android_intent(self) -> None:
        link = whatsapp_guest_link(
            "+919876543210",
            "Hi",
            WHATSAPP_APP_BUSINESS,
            sender_phone="+918667539795",
        )
        self.assertIn("com.whatsapp.w4b", link)

    def test_personal_android_link_format(self) -> None:
        link = wa_personal_android_link("+919876543210", "Test")
        self.assertTrue(link.startswith("intent://send?phone="))
        self.assertIn("text=Test", link)

    def test_business_android_link_format(self) -> None:
        link = wa_business_android_link("+919876543210")
        self.assertIn("package=com.whatsapp.w4b", link)


if __name__ == "__main__":
    unittest.main()
