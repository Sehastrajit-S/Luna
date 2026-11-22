"""WhatsApp messaging checks every step on screen and sends nothing when one fails;
plus the request-parsing fixes that came with it (compound "open X and text Y",
Gmail searches, whole-word app matching, asking which browser profile)."""
from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from server.services import messaging as M
from server.services.files.ocr import OcrBox

W, H = 974, 1039


def box(text, left, top, width=200, height=20):
    return OcrBox(text, left, top, left + width, top + height, 0.95)


def screen(header="", composer="Type a message", messages=(), results=()):
    boxes = []
    if header:
        boxes.append(box(header, 471, 52))
    boxes.append(box(composer, 504, H - 55) if composer else box("", 0, 0, 0, 0))
    for i, text in enumerate(messages):
        boxes.append(box(text, 550, 700 + i * 40, 300))
    if results:
        boxes.append(box("Chats", 93, 218, 60))
        for i, name in enumerate(results):
            boxes.append(box(name, 159, 260 + i * 76, 180))
        boxes.append(box("Messages", 93, 260 + len(results) * 76, 80))
    return M.Screen(W, H, [b for b in boxes if b.text])


class FakeKeys:
    def __init__(self, focus_ok=True):
        self.log, self.focus_ok = [], focus_ok

    def foreground(self):
        return 111

    def focus_window(self, hwnd, timeout=2.0):
        self.log.append(("focus", hwnd))
        return self.focus_ok

    def press(self, hwnd, *keys):
        self.log.append(("press",) + keys)

    def type_text(self, hwnd, text):
        self.log.append(("type", text))

    @property
    def typed(self):
        return [e[1] for e in self.log if e[0] == "type"]

    @property
    def sent(self):
        # Enter pressed after the message was typed.
        typed_at = [i for i, e in enumerate(self.log) if e[0] == "type"]
        return len(typed_at) >= 2 and ("press", "enter") in self.log[typed_at[1]:]


class SendTests(unittest.TestCase):
    def run_send(self, screens, to="Priya Raman", text="I'm running late", keys=None):
        keys = keys or FakeKeys()
        sequence = iter(screens)
        with mock.patch.object(M, "read_screen", side_effect=lambda capture: (next(sequence), object())):
            try:
                result = M.send_whatsapp(to, text, keys=keys, capture=lambda: None, window={"hwnd": 5},
                                         sleep=lambda s: None, save=lambda image, label: f"{label}.png")
                return result, None, keys
            except M.MessageError as e:
                return None, e, keys

    def test_sends_after_every_check_passes(self):
        result, error, keys = self.run_send([
            screen(results=["Priya Raman", "Priya's Mom"]),
            screen(header="Priya Raman"),
            screen(header="Priya Raman", composer="I'm running late"),
            screen(header="Priya Raman", messages=["Hi!", "I'm running late"]),
        ])
        self.assertIsNone(error)
        self.assertEqual(keys.typed, ["Priya Raman", "I'm running late"])
        self.assertTrue(keys.sent)
        self.assertEqual(result.screenshot, "whatsapp-sent.png")
        self.assertIn("chat header shows 'Priya Raman'", M.describe(result))

    def test_contact_not_in_search_sends_nothing(self):
        _, error, keys = self.run_send([screen(results=["Meera Nair", "Arjun"])])
        self.assertEqual(error.kind, "not_found")
        self.assertIn("Meera Nair", error.message)
        self.assertEqual(keys.typed, ["Priya Raman"])   # only the search
        self.assertFalse(keys.sent)

    def test_wrong_chat_opened_sends_nothing(self):
        _, error, keys = self.run_send([screen(results=["Priya Raman"]), screen(header="Priya's Mom")])
        self.assertEqual(error.kind, "wrong_chat")
        self.assertEqual(keys.typed, ["Priya Raman"])
        self.assertFalse(keys.sent)

    def test_existing_draft_is_left_alone(self):
        _, error, keys = self.run_send([screen(results=["Priya Raman"]),
                                        screen(header="Priya Raman", composer="half written thought")])
        self.assertEqual(error.kind, "draft")
        self.assertFalse(keys.sent)

    def test_text_not_in_box_is_cleared_not_sent(self):
        _, error, keys = self.run_send([screen(results=["Priya Raman"]), screen(header="Priya Raman"),
                                        screen(header="Priya Raman", composer="Type a message")])
        self.assertEqual(error.kind, "typing")
        after_typing = keys.log[[i for i, e in enumerate(keys.log) if e[0] == "type"][-1]:]
        self.assertIn(("press", "ctrl", "A"), after_typing)
        self.assertIn(("press", "delete"), after_typing)
        self.assertEqual(keys.log[-1], ("focus", 111), "focus goes back to where the user was")
        self.assertFalse(keys.sent)

    def test_send_not_visible_is_reported(self):
        _, error, _ = self.run_send([screen(results=["Priya Raman"]), screen(header="Priya Raman"),
                                     screen(header="Priya Raman", composer="I'm running late"),
                                     screen(header="Priya Raman", composer="I'm running late", messages=["Hi!"])])
        self.assertEqual(error.kind, "not_sent")

    def test_no_focus_types_nothing(self):
        _, error, keys = self.run_send([], keys=FakeKeys(focus_ok=False))
        self.assertEqual(error.kind, "focus")
        self.assertEqual(keys.typed, [])

    def test_names_match(self):
        self.assertTrue(M.names_match("Alexandra Morgan", "AlexandraMorgan (You) Message yourself"))
        self.assertTrue(M.names_match("Alexandra Morgan", "Alexandra Mo... (You) sunday"))
        self.assertFalse(M.names_match("Priya", "Alexandra Morgan (You)"))
        self.assertFalse(M.names_match("Alexandra Morgan", "Alexandra Kumar"))

    def test_tool_is_risky_and_reports_stops(self):
        from server.services.permission_manager import permission_manager
        from server.services.tool_runner.executor import execute_tool_call
        decision, message, _ = permission_manager.check("message_contact", {"to": "Priya", "text": "running late"})
        self.assertEqual(decision, "confirm")
        self.assertIn("Priya", message)
        with mock.patch.object(M, "send_whatsapp", side_effect=M.MessageError("wrong_chat", "Opened 'Mom', not 'Priya'.")), \
             mock.patch("server.services.audit_log.record_audit") as audit:
            result = asyncio.run(execute_tool_call({"tool": "message_contact", "args": {"to": "Priya", "text": "hi"}}, None, 1))
        self.assertTrue(result.startswith("failed: Opened 'Mom'"))
        self.assertIn("don't say it was sent", result)
        self.assertEqual(audit.call_args.kwargs["status"], "stopped:wrong_chat")


class OpenChatTests(unittest.TestCase):
    def run_open(self, screens, to="Meera"):
        keys = FakeKeys()
        sequence = iter(screens)
        with mock.patch.object(M, "read_screen", side_effect=lambda capture: (next(sequence), object())):
            try:
                return M.open_whatsapp_chat(to, keys=keys, capture=lambda: None, window={"hwnd": 5},
                                            sleep=lambda s: None, save=lambda image, label: f"{label}.png"), None, keys
            except M.MessageError as e:
                return None, e, keys

    def test_opens_the_chat_and_types_only_the_search(self):
        result, error, keys = self.run_open([screen(results=["Meera Nair"]), screen(header="Meera Nair")])
        self.assertIsNone(error)
        self.assertEqual(keys.typed, ["Meera"])
        self.assertNotIn(("focus", 111), keys.log)   # stays on WhatsApp
        self.assertIn("Opened your WhatsApp chat with Meera.", M.describe_open(result))
        self.assertIn("chat header shows 'Meera Nair'", M.describe_open(result))

    def test_wrong_chat_is_reported(self):
        _, error, _ = self.run_open([screen(results=["Meera Nair"]), screen(header="Priya Raman")])
        self.assertEqual(error.kind, "wrong_chat")

    def test_parses_open_chat_requests(self):
        cases = {
            "Open Meera's chat.": "Meera",
            "No, open Meera's chat and WhatsApp.": "Meera",
            "open my chat with Priya Raman on WhatsApp": "Priya Raman",
            "can you open the whatsapp chat with Mom": "Mom",
            "open Arjun's WhatsApp chat": "Arjun",
        }
        for text, name in cases.items():
            self.assertEqual(M.parse_open_chat(text), name, text)
        for text in ("open whatsapp", "open chrome", "open the chat", "open my gmail", "open ChatGPT"):
            self.assertIsNone(M.parse_open_chat(text), text)

class SendRequestTests(unittest.TestCase):
    def test_parses_whatsapp_send_requests(self):
        cases = {
            "Send Arjun hi in WhatsApp": ("Arjun", "hi"),
            "send hi to Priya Raman on WhatsApp": ("Priya Raman", "hi"),
            "text Priya that I am running late on whatsapp": ("Priya", "I am running late"),
            "open whatsapp and text Mom I reached": ("Mom", "I reached"),
            "WhatsApp Meera saying see you at 6": ("Meera", "see you at 6"),
            "send Alexandra Morgan a message saying test on WhatsApp": ("Alexandra Morgan", "test"),
        }
        for text, wanted in cases.items():
            self.assertEqual(M.parse_send_request(text), wanted, text)
        for text in ("send the report to my boss", "tell me about whatsapp", "send a message on whatsapp",
                     "Open Meera's chat", "open whatsapp"):
            self.assertIsNone(M.parse_send_request(text), text)

    def test_follow_up_sends_go_to_the_last_contact_in_this_conversation(self):
        self.assertIsNone(M.parse_follow_up_send(7, "Send this is from Luna"))   # nobody messaged yet
        M.remember_contact(7, "Arjun")
        self.assertEqual(M.parse_follow_up_send(7, "Send this is from Luna"), ("Arjun", "this is from Luna"))
        self.assertEqual(M.parse_follow_up_send(7, "Send him this is from Luna"), ("Arjun", "this is from Luna"))
        self.assertEqual(M.parse_follow_up_send(7, "also tell him that I'm on my way"), ("Arjun", "I'm on my way"))
        self.assertIsNone(M.parse_follow_up_send(8, "Send him hi"))              # another conversation
        for text in ("send me the link", "send it to Meera", "send an email to Bob", "what did he say?"):
            self.assertIsNone(M.parse_follow_up_send(7, text), text)

    def test_send_waits_for_approval_and_streams_the_question_first(self):
        import asyncio
        from types import SimpleNamespace
        from server.services.chat_pipeline import stage_dispatch as D, stages

        ctx = SimpleNamespace(sse_events=[], db=None, conv=SimpleNamespace(id=1))
        ctx.emit_sse = ctx.sse_events.append
        seen = []

        async def answer_later(confirm_id, timeout_seconds):
            await asyncio.sleep(0.5)          # the question must be out before this returns
            seen.append([e["type"] for e in ctx.sse_events] or "flushed")
            return False

        async def collect():
            async for chunk in stages._live(ctx, D._send_with_approval(ctx, "Arjun", "hi")):
                seen.append(chunk)

        with mock.patch("server.services.chat_pipeline.stage_tools._wait_for_confirmation", answer_later), \
             mock.patch.object(D, "execute_tool_call", mock.AsyncMock()) as run:
            asyncio.run(collect())
        self.assertIn("confirmation_required", seen[0])     # streamed while waiting
        self.assertIn("Send a WhatsApp message to Arjun", seen[0])
        self.assertEqual(seen[1], "flushed")
        self.assertIn("confirmation_resolved", seen[2])
        run.assert_not_called()                              # declined: nothing sent


class RequestParsingTests(unittest.TestCase):
    def test_compound_requests_skip_the_app_shortcut(self):
        from server.services.command_parser import parse_user_launch_request as launch
        self.assertEqual(launch("open spotify"), "spotify")
        self.assertEqual(launch("open vs code please"), "vs code")
        for message in ("open whatsapp and text Priya I am running late", "open my mails from Priya",
                        "open whatsapp and message mom that I reached"):
            self.assertIsNone(launch(message), message)

    def test_app_names_match_whole_words(self):
        from server.services.app_launcher import launcher
        apps = {"run": "run.lnk", "ea": "ea.lnk", "whatsapp": "wa", "google chrome": "chrome.lnk"}
        self.assertIsNone(launcher._best_match("i am running late", {"run": "run.lnk"}))
        self.assertIsNone(launcher._best_match("message mom that i reached", {"ea": "ea.lnk"}))
        self.assertEqual(launcher._best_match("chrome", apps), "chrome.lnk")
        self.assertEqual(launcher._best_match("whatsapp desktop", apps), "wa")

    def test_gmail_searches(self):
        from server.services.browser_open import parse_web_open
        cases = {
            "open my mails from Priya": ("from:Priya", ""),
            "open the email about the invoice": ("invoice", ""),
            "open my unread emails": ("is:unread", ""),
            "open emails from john smith about the project deadline": ('from:"john smith" project deadline', ""),
            "show me mails from amazon with attachments from last week": ("newer_than:7d has:attachment from:amazon", ""),
            "open the email with subject Offer Letter": ("subject:(Offer Letter)", ""),
            "open emails sent to hr@acme.com": ("to:hr@acme.com", ""),
            "open my acme mails from the CEO in chrome": ("from:CEO", "acme"),
        }
        for message, (query, profile) in cases.items():
            with self.subTest(message=message):
                request = parse_web_open(message)
                self.assertEqual(request.site, f"Gmail search “{query}”")
                self.assertEqual(request.profile, profile)
                self.assertIn("mail.google.com/mail/u/0/#search/", request.url)
        self.assertEqual(parse_web_open("open my emails").url, "https://mail.google.com/")


class ProfileQuestionTests(unittest.TestCase):
    PROFILES = None

    def setUp(self):
        from server.services import browser_open as B
        self.B = B
        self.profiles = [B.Profile("Default", "Alexandra", "Alexandra M", "me@gmail.com", True),
                         B.Profile("Profile 2", "Alexandra", "", "games@gmail.com", False),
                         B.Profile("Profile 5", "Alexandra", "", "college@gmail.com", False),
                         B.Profile("Profile 3", "Work", "", "work@gmail.com", False)]
        for patch in (mock.patch.object(B, "list_profiles", return_value=self.profiles),
                      mock.patch.object(B, "_browser_exe", return_value="chrome.exe"),
                      mock.patch.object(B.settings, "browser_profile", "", create=True)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_same_named_profiles_ask_with_options_and_open_nothing(self):
        launched = []
        request = self.B.parse_web_open("open my mails from Priya in chrome with my Alexandra profile")
        result = self.B.open_website(request, launcher=lambda cmd, **kw: launched.append(cmd), verify=False)
        self.assertEqual(launched, [])
        self.assertTrue(result["question"])
        text = self.B.describe(result)
        self.assertIn("3 Chrome profiles called 'Alexandra'", text)
        self.assertIn("2. Alexandra — games@gmail.com", text)
        self.assertEqual([b["message"] for b in self.B.choice_buttons(result)],
                         ["Use profile me@gmail.com", "Use profile games@gmail.com", "Use profile college@gmail.com"])

    def test_answers_reopen_the_waiting_request(self):
        request = self.B.parse_web_open("open my mails from Priya in chrome with my Alexandra profile")
        result = self.B.open_website(request, launcher=lambda cmd, **kw: None, verify=False)
        for answer, expected in (("2", "games@gmail.com"), ("the second one", "games@gmail.com"),
                                 ("the last one", "college@gmail.com"), ("Use profile me@gmail.com", "me@gmail.com"),
                                 ("college", "college@gmail.com")):
            with self.subTest(answer=answer):
                self.B.remember_question(9, request, result)
                picked = self.B.answer_pending(9, answer)
                self.assertEqual(picked.profile, expected)
                self.assertEqual(picked.url, request.url)   # same Gmail search
        self.B.remember_question(9, request, result)
        self.assertIsNone(self.B.answer_pending(9, "what's the weather"))
        self.assertIsNone(self.B.answer_pending(10, "2"), "only in the conversation that asked")

    def test_unique_profile_name_needs_no_question(self):
        launched = []
        request = self.B.parse_web_open("open gmail in chrome with my work profile")
        self.B.open_website(request, launcher=lambda cmd, **kw: launched.append(cmd), verify=False)
        self.assertEqual(launched, [["chrome.exe", "--profile-directory=Profile 3", "https://mail.google.com/"]])


if __name__ == "__main__":
    unittest.main()
