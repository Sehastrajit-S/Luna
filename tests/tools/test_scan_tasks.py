"""Voice-only "scan this and …": QR → open the form and fill it with the user's details,
a scanned page → fill the open form, a product → store prices; forms are filled
field by field (checked after typing) and never submitted without "submit it"."""
from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from server.services import form_filler as F
from server.services import scan_tasks as S


class IntentTests(unittest.TestCase):
    def test_intents(self):
        self.assertEqual(S.intent("scan this then fill the form"), "form")
        self.assertEqual(S.intent("scan this QR and apply"), "form")
        self.assertEqual(S.intent("scan it and find prices at different stores"), "prices")
        self.assertEqual(S.intent("scan it, how much is this at walmart"), "prices")
        self.assertEqual(S.intent("scan this and tell me what it says"), "other")
        self.assertTrue(S.is_scan_request("Scan this and fill the form"))
        self.assertFalse(S.is_scan_request("fill the form"))

    def test_submit_only_after_a_fill_in_this_conversation(self):
        self.assertIsNone(S.wants_submit(5, "submit it"), "nothing was filled")
        S._FILLED[5] = ("Internship application", __import__("time").monotonic())
        self.assertIsNone(S.wants_submit(6, "submit it"), "another conversation")
        self.assertIsNone(S.wants_submit(5, "how do I submit a form?"), "a question isn't a go-ahead")
        self.assertEqual(S.wants_submit(5, "Okay, submit it"), "Internship application")
        self.assertIsNone(S.wants_submit(5, "submit it"), "used once")


def run(coro):
    return asyncio.run(coro)


class HandleTests(unittest.TestCase):
    def test_qr_form_opens_link_and_fills_with_my_details(self):
        evidence = mock.Mock(verified=True, window={"title": "Internship application - Google Chrome"})
        opened = {"error": "", "evidence": evidence, "profile_key": "me@gmail.com"}
        filled = F.FillResult(title="Internship application", filled=[("Email address", "me@gmail.com")], empty=["Date of birth"])
        with mock.patch("server.services.shopping.barcode.decode_qr", return_value="https://forms.gle/abc"), \
             mock.patch("server.services.browser_open.open_website", return_value=opened) as open_site, \
             mock.patch.object(F, "my_details", mock.AsyncMock(return_value={"email": "me@gmail.com"})) as mine, \
             mock.patch.object(F, "fill_form", return_value=filled) as fill, \
             mock.patch.object(S.asyncio, "sleep", mock.AsyncMock()):
            out = run(S.handle(mock.Mock(), 11, "scan this QR and fill the form", b"img"))
        self.assertEqual(open_site.call_args.args[0].url, "https://forms.gle/abc")
        self.assertEqual(mine.call_args.kwargs["browser_email"], "me@gmail.com")
        self.assertEqual(fill.call_args.kwargs["title_hint"], "Internship application")
        self.assertIn("Opened the form from the QR code", out.reply)
        self.assertIn("Using your details", out.reply)
        self.assertIn("I haven't submitted it", out.reply)
        self.assertIn(11, S._FILLED)

    def test_scanned_page_fills_the_open_form_with_its_details(self):
        filled = F.FillResult(title="Form", filled=[("Full name", "Asha Rao")])
        with mock.patch("server.services.shopping.barcode.decode_qr", return_value=None), \
             mock.patch.object(S, "_ocr_text", return_value="Name: Asha Rao\nEmail: asha@example.com"), \
             mock.patch.object(F, "details_from_scan", mock.AsyncMock(return_value={"full_name": "Asha Rao"})), \
             mock.patch.object(F, "fill_form", return_value=filled) as fill:
            out = run(S.handle(mock.Mock(), 12, "scan this then fill the form", b"img"))
        self.assertEqual(fill.call_args.args[0], {"full_name": "Asha Rao"})
        self.assertIn("Using the scanned page", out.reply)

    def test_prices_from_barcode_then_from_the_photo(self):
        product = mock.Mock(name="p")
        product.name, product.title = "Coca-Cola Zero Sugar 12 fl oz", "Coke Zero"
        with mock.patch("server.services.shopping.barcode.decode_qr", return_value=None), \
             mock.patch("server.services.shopping.barcode.decode_image_async", mock.AsyncMock(return_value="049000028911")), \
             mock.patch("server.services.shopping.barcode.lookup", mock.AsyncMock(return_value=product)):
            out = run(S.handle(mock.Mock(), 1, "scan it and find prices at different stores", b"img"))
        self.assertEqual(out.rewrite, "Compare store prices for Coca-Cola Zero Sugar 12 fl oz (barcode 049000028911)")

        from server.services.shopping.barcode import BarcodeError
        with mock.patch("server.services.shopping.barcode.decode_qr", return_value=None), \
             mock.patch("server.services.shopping.barcode.decode_image_async",
                        mock.AsyncMock(side_effect=BarcodeError("no_barcode", "none"))), \
             mock.patch.object(S, "_name_product", mock.AsyncMock(return_value="Tide Pods 42 count")):
            out = run(S.handle(mock.Mock(), 1, "scan it and compare prices", b"img"))
        self.assertEqual(out.rewrite, "Compare store prices for Tide Pods 42 count")

    def test_bare_qr_opens_its_link_and_other_scans_fall_through(self):
        with mock.patch("server.services.shopping.barcode.decode_qr", return_value="https://example.com/menu"), \
             mock.patch.object(S, "_open_link", mock.AsyncMock(return_value="Opened it.")):
            self.assertEqual(run(S.handle(mock.Mock(), 1, "scan this", b"img")).reply, "Opened it.")
        with mock.patch("server.services.shopping.barcode.decode_qr", return_value=None):
            out = run(S.handle(mock.Mock(), 1, "scan this and tell me what it says", b"img"))
        self.assertIsNone(out.reply)
        self.assertIsNone(out.rewrite)


    def test_bare_scan_says_what_it_is_from_this_photo_only(self):
        from server.services.shopping.barcode import BarcodeError
        product = mock.Mock(name="p")
        product.name, product.title = "Coca-Cola Zero Sugar 12 fl oz", ""
        with mock.patch("server.services.shopping.barcode.decode_qr", return_value=None),              mock.patch("server.services.shopping.barcode.decode_image_async", mock.AsyncMock(return_value="049000028911")),              mock.patch("server.services.shopping.barcode.lookup", mock.AsyncMock(return_value=product)):
            out = run(S.handle(mock.Mock(), 1, "Can you scan this?", b"img"))
        self.assertIn("Coca-Cola Zero Sugar 12 fl oz", out.reply)
        self.assertIn("luna-suggest", out.reply)   # a "Compare prices" button

        with mock.patch("server.services.shopping.barcode.decode_qr", return_value=None),              mock.patch("server.services.shopping.barcode.decode_image_async",
                        mock.AsyncMock(side_effect=BarcodeError("no_barcode", "none"))),              mock.patch.object(S, "_ask_vision", mock.AsyncMock(return_value="A price label reading 228910.")) as ask:
            out = run(S.handle(mock.Mock(), 1, "scan this", b"img"))
        self.assertEqual(out.reply, "A price label reading 228910.")
        self.assertEqual(ask.await_args.args[0], b"img")

    def test_which_requests_the_scan_handler_reads_itself(self):
        for text in ("Can you scan this?", "scan this", "scan it and find prices", "scan the QR and fill the form"):
            self.assertTrue(S.reads_photo_itself(text), text)
        for text in ("scan this and tell me what it says", "what is this", "describe the photo"):
            self.assertFalse(S.reads_photo_itself(text), text)

class FakeElement:
    def __init__(self, name):
        self.name, self.value = name, ""


class FakeUIA:
    def __init__(self, fields):
        self.list = fields
        self.focused = None

    def fields(self, hwnd):
        return [F.Field(label=e.name, kind="select" if e.name == "Country" else "text", element=e, value=e.value)
                for e in self.list]

    def value(self, el):
        return el.value

    def focus(self, el):
        self.focused = el

    def select_option(self, el, wanted):
        el.value = wanted
        return True


class FakeKeys:
    def __init__(self, uia):
        self.uia = uia

    def foreground(self):
        return 1

    def focus_window(self, hwnd, timeout=2.0):
        return True

    def press(self, hwnd, *keys):
        if keys == ("ctrl", "A") and self.uia.focused:
            self.uia.focused.value = ""

    def type_text(self, hwnd, text):
        if self.uia.focused.name != "Phone number":   # pretend this site rejects the typing
            self.uia.focused.value += text


class FillTests(unittest.TestCase):
    def test_fills_known_fields_checks_them_and_names_the_rest(self):
        elements = [FakeElement(n) for n in ("First name", "Last name", "Email address", "Phone number",
                                             "Date of birth", "Country", "Promo code")]
        elements[5].value = "Choose…"   # a dropdown's placeholder isn't a value
        uia = FakeUIA(elements)
        details = F.complete_details({"full_name": "Asha Rao", "email": "asha@example.com", "phone": "555 0100",
                                      "country": "India"})
        with mock.patch("server.services.verification.capture_window", return_value=None):
            result = F.fill_form(details, window={"hwnd": 9, "title": "Apply - Google Chrome"}, uia=uia,
                                 keys=FakeKeys(uia), sleep=lambda s: None)
        self.assertEqual(result.filled, [("First name", "Asha"), ("Last name", "Rao"),
                                         ("Email address", "asha@example.com"), ("Country", "India")])
        self.assertEqual(result.failed[0][0], "Phone number")
        self.assertEqual(result.empty, ["Date of birth", "Promo code"])
        text = F.describe(result)
        self.assertIn("Left empty — I don't know these: Date of birth, Promo code.", text)
        self.assertIn("I haven't submitted it", text)

    def test_already_filled_fields_are_left_alone(self):
        elements = [FakeElement("Email address")]
        elements[0].value = "someone@else.com"
        uia = FakeUIA(elements)
        with mock.patch("server.services.verification.capture_window", return_value=None):
            result = F.fill_form({"email": "me@x.com"}, window={"hwnd": 9, "title": "t"}, uia=uia, keys=FakeKeys(uia),
                                 sleep=lambda s: None)
        self.assertEqual(result.skipped, ["Email address (already filled)"])
        self.assertEqual(elements[0].value, "someone@else.com")

    def test_extracted_details_must_appear_in_the_source(self):
        llm = '{"full_name": "Asha Rao", "email": "asha@example.com", "phone": "999 1234", "city": "Mumbai"}'
        with mock.patch("server.services.llm.ollama.complete", mock.AsyncMock(return_value=llm)):
            details = run(F.details_from_scan("Asha Rao\nasha@example.com\nBengaluru"))
        self.assertEqual(details["email"], "asha@example.com")
        self.assertNotIn("phone", details, "not on the page: invented")
        self.assertNotIn("city", details)
        self.assertEqual((details["first_name"], details["last_name"]), ("Asha", "Rao"))


class QrTests(unittest.TestCase):
    def test_reads_a_qr_link_from_a_photo(self):
        import cv2
        import numpy as np

        from server.services.shopping.barcode import decode_qr
        qr = cv2.QRCodeEncoder.create().encode("https://forms.gle/AbCdEf123")
        qr = cv2.resize(qr, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
        canvas = np.full((1200, 1600), 235, np.uint8)
        canvas[300:300 + qr.shape[0], 500:500 + qr.shape[1]] = qr
        ok, jpg = cv2.imencode(".jpg", canvas)
        self.assertEqual(decode_qr(jpg.tobytes()), "https://forms.gle/AbCdEf123")
        ok, blank = cv2.imencode(".jpg", np.full((400, 400), 200, np.uint8))
        self.assertIsNone(decode_qr(blank.tobytes()))


if __name__ == "__main__":
    unittest.main()
