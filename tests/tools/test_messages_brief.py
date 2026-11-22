"""'Any new messages?' — who wrote, per platform, without opening anything; and the
Google sign-in fix (refresh the access token instead of using an expired one forever)."""
from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

import httpx
from PIL import Image, ImageDraw

from server.services import messages_brief as MB
from server.services.files.ocr import OcrBox

W, H = 974, 1039
GREEN = (33, 192, 99)


def b(text, left, top, width=150):
    return OcrBox(text, left, top, left + width, top + 18, 0.95)


def chat_list():
    """Chat list rows like the real WhatsApp window, plus an image with green badges where unread."""
    image = Image.new("RGB", (W, H), (17, 27, 33))
    draw = ImageDraw.Draw(image)
    boxes = [b("Chats", 90, 60, 60), b("Search or start a new chat", 139, 115, 200), b("All", 105, 160, 20),
             b("Unread 122", 154, 160, 80)]
    chats = [("Agentic AI course", "5:47 PM", "Ushnesha: merge it one by one", True),
             ("Meera Nair", "3:55 PM", "V/ Bro, when are you coming", False),
             ("GS", "5:44 PM", "Voice call", True),
             ("AliExpress Orders", "9:33 AM", "[Account Update] Something", True)]
    y = 220
    for name, when, preview, unread in chats:
        boxes += [b(name, 157, y), b(when, 318, y, 50), b(preview, 158, y + 24, 160)]
        if unread:
            draw.ellipse((345, y + 22, 365, y + 42), fill=GREEN)
        y += 76
    return boxes, image


class ParseTests(unittest.TestCase):
    def test_requests(self):
        cases = {
            "any new messages?": ["whatsapp", "gmail", "outlook"],
            "who texted me": ["whatsapp"],
            "any whatsapp messages": ["whatsapp"],
            "who emailed me": ["gmail", "outlook"],
            "check my mail": ["gmail", "outlook"],
            "summarize my inbox": ["gmail", "outlook"],
            "catch me up": ["whatsapp", "gmail", "outlook"],
        }
        for message, sources in cases.items():
            self.assertEqual(MB.parse_brief_request(message), sources, message)
        for message in ("open my mails from Priya", "text priya hi", "send an email to bob",
                        "what is a message queue", "summarize this article", "check my code"):
            self.assertIsNone(MB.parse_brief_request(message), message)

    def test_unread_chats_found_by_badge_colour(self):
        boxes, image = chat_list()
        with mock.patch.object(MB, "_unread_badge", wraps=MB._unread_badge) as badge, \
             mock.patch("server.services.files.ocr.ocr_image", return_value=mock.Mock(text="3")):
            items, _ = MB.parse_whatsapp_chat_list(boxes, W, image)
        self.assertEqual([i.sender for i in items], ["Agentic AI course", "GS", "AliExpress Orders"])
        self.assertEqual(items[0].count, 3)
        self.assertEqual(items[1].preview, "Voice call", "a V that starts a word isn't a read tick")
        self.assertNotIn("Meera Nair", [i.sender for i in items], "no badge, already read")
        self.assertGreaterEqual(badge.call_count, 4)

    def test_background_capture_restores_the_window(self):
        boxes, image = chat_list()
        with mock.patch("server.services.files.ocr.ocr_image", return_value=mock.Mock(text="2")):
            brief = MB.brief_whatsapp(capture=lambda: image, find_window=lambda: {"hwnd": 1, "title": "WhatsApp"},
                                      ocr=lambda img: boxes)
        self.assertTrue(brief.ok)
        self.assertEqual(len(brief.items), 3)
        not_running = MB.brief_whatsapp(capture=lambda: image, find_window=lambda: None, ocr=lambda img: boxes)
        self.assertFalse(not_running.ok)


class MailTests(unittest.TestCase):
    def test_gmail_groups_by_sender(self):
        listing = mock.Mock(data={"messages": [{"id": "1"}, {"id": "2"}, {"id": "3"}], "resultSizeEstimate": 3})

        def meta(sender, subject):
            return mock.Mock(data={"payload": {"headers": [{"name": "From", "value": sender}, {"name": "Subject", "value": subject}]}})

        responses = {"1": meta('"LinkedIn" <jobs@linkedin.com>', "New internships for you"),
                     "2": meta("LinkedIn <jobs@linkedin.com>", "3 new jobs"),
                     "3": meta("Priya Raman <priya@example.com>", "Invoice for October")}

        async def fake(service, action, args):
            return listing if action == "search_messages" else responses[args["message_id"]]

        with mock.patch("server.services.workspace_integrations.google.google_workspace", side_effect=fake), \
             mock.patch.object(MB, "brief_gmail", wraps=MB.brief_gmail), \
             mock.patch("server.config.settings.google_workspace_refresh_token", "r", create=True):
            brief = asyncio.run(MB.brief_gmail())
        self.assertEqual([(i.sender, i.count) for i in brief.items], [("LinkedIn", 2), ("Priya Raman", 1)])
        self.assertEqual(brief.items[1].preview, "Invoice for October")

    def test_failures_are_said_plainly(self):
        text = MB.describe([MB.SourceBrief("WhatsApp", True, [MB.Item("GS", 1, "Voice call")]),
                            MB.SourceBrief("Gmail", False, note="Google sign-in has expired or was revoked. Reconnect…"),
                            MB.SourceBrief("Outlook", False, note="")])
        self.assertIn("**WhatsApp** — 1 unread from 1 chat:\n- GS — Voice call", text)
        self.assertIn("**Gmail** — couldn't check: Google sign-in has expired", text)
        self.assertNotIn("Outlook", text, "not connected: left out quietly")
        self.assertIn("nothing was opened or marked as read", text)


class TokenRefreshTests(unittest.TestCase):
    def setUp(self):
        from server.services.workspace_integrations import base
        self.base = base
        base._TOKEN_CACHE.clear()
        self.addCleanup(base._TOKEN_CACHE.clear)
        for name, value in (("google_workspace_client_id", "id"), ("google_workspace_client_secret", "secret"),
                            ("google_workspace_refresh_token", "refresh"), ("google_workspace_access_token", "stale")):
            patch = mock.patch.object(base.settings, name, value, create=True)
            patch.start()
            self.addCleanup(patch.stop)

    def run_requests(self, handler, calls=1):
        transport = httpx.MockTransport(handler)
        real = httpx.AsyncClient

        def client(*args, **kwargs):
            kwargs["transport"] = transport
            return real(*args, **kwargs)

        async def go():
            out = []
            for _ in range(calls):
                out.append(await self.base._request("GET", "https://gmail.googleapis.com/x", "google"))
            return out

        with mock.patch.object(self.base.httpx, "AsyncClient", side_effect=client):
            return asyncio.run(go())

    def test_uses_a_fresh_token_and_caches_it(self):
        seen = {"refresh": 0, "auth": []}

        def handler(request):
            if "oauth2.googleapis.com" in str(request.url):
                seen["refresh"] += 1
                return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3599})
            seen["auth"].append(request.headers["Authorization"])
            return httpx.Response(200, json={"ok": True})

        self.run_requests(handler, calls=2)
        self.assertEqual(seen["auth"], ["Bearer fresh", "Bearer fresh"], "the expired .env token isn't used")
        self.assertEqual(seen["refresh"], 1, "cached until it nears expiry")

    def test_401_refreshes_once_and_retries(self):
        seen = {"auth": []}
        self.base._TOKEN_CACHE["google"] = ("old", 10 ** 12)

        def handler(request):
            if "oauth2.googleapis.com" in str(request.url):
                return httpx.Response(200, json={"access_token": "new", "expires_in": 3599})
            seen["auth"].append(request.headers["Authorization"])
            return httpx.Response(401 if request.headers["Authorization"] == "Bearer old" else 200, json={})

        self.run_requests(handler)
        self.assertEqual(seen["auth"], ["Bearer old", "Bearer new"])

    def test_revoked_sign_in_says_how_to_reconnect(self):
        def handler(request):
            if "oauth2.googleapis.com" in str(request.url):
                return httpx.Response(400, json={"error": "invalid_grant", "error_description": "Bad Request"})
            return httpx.Response(401, json={})

        with self.assertRaises(self.base.WorkspaceIntegrationError) as caught:
            self.run_requests(handler)
        self.assertIn("Reconnect Google", str(caught.exception))
        self.assertIn("/api/integrations/workspace/google/oauth/start", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
