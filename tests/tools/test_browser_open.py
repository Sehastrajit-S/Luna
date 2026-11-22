"""Opening websites in the right browser profile (Chrome's profile picker made
"open my Gmail in chrome" stall), and checking the page window appeared."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from server.services import browser_open as B
from server.services import verification as V

LOCAL_STATE = {"profile": {"last_used": "Default", "info_cache": {
    "Default": {"name": "Alexandra", "gaia_name": "Alexandra M", "user_name": "me@gmail.com"},
    "Profile 3": {"name": "Work", "gaia_name": "", "user_name": "work@gmail.com"},
    "Profile 13": {"name": "acme.com", "gaia_name": "Admin", "user_name": "admin@acme.com"},
    "Profile 5": {"name": "Alexandra", "gaia_name": "Alexandra M", "user_name": "other@gmail.com"},
}}}


class ParseTests(unittest.TestCase):
    def test_websites_vs_apps(self):
        cases = {
            "Open my Gmail in chrome": ("https://mail.google.com/", "chrome", ""),
            "open youtube please": ("https://www.youtube.com/", "", ""),
            "open my gmail in chrome with my Work profile": ("https://mail.google.com/", "chrome", "Work"),
            "go to mail in chrome using acme profile": ("https://mail.google.com/", "chrome", "acme"),
            "open my acme gmail in chrome": ("https://mail.google.com/", "chrome", "acme"),
            "open github.com": ("https://github.com", "", ""),
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                r = B.parse_web_open(message)
                self.assertEqual((r.url, r.browser, r.profile), expected)
        for app in ("open spotify", "open whatsapp", "Launch WhatsApp", "open vs code", "open chrome", "open the file chat.py"):
            with self.subTest(app=app):
                self.assertIsNone(B.parse_web_open(app), "apps stay with the app launcher")


class SiteSearchTests(unittest.TestCase):
    """The LinkedIn session: 'Open the linked page' → 'Search for open AI in it' → 'Search it in the LinkedIn'."""

    def test_the_linkedin_conversation(self):
        opened = B.parse_web_open("Open the linked page")   # speech typo
        self.assertEqual((opened.url, opened.key), ("https://www.linkedin.com/", "linkedin"))
        B.remember_site(501, opened, "me@gmail.com")

        search = B.parse_site_search("Search for open AI in it", 501)
        self.assertEqual(search.url, "https://www.linkedin.com/search/results/all/?keywords=open+AI")
        self.assertEqual(search.profile, "me@gmail.com", "same profile as the page it searches")
        B.remember_site(501, search)

        again = B.parse_site_search("Search it in the LinkedIn", 501)
        self.assertEqual(again.url, search.url, "'it' is the last thing searched")

    def test_site_searches(self):
        cases = {
            "search OpenAI on youtube": "https://www.youtube.com/results?search_query=OpenAI",
            "search github for luna agent": "https://github.com/search?q=luna+agent",
            "search for cheap headphones on amazon": "https://www.amazon.com/s?k=cheap+headphones",
            "find priya in my mail": "https://mail.google.com/mail/u/0/#search/priya",
        }
        for message, url in cases.items():
            with self.subTest(message=message):
                self.assertEqual(B.parse_site_search(message).url, url)

    def test_normal_searches_stay_web_searches(self):
        for message in ("search for the weather in phoenix", "search for flights in 2024",
                        "look up transformers on google", "search for open AI in it"):   # no site opened yet
            with self.subTest(message=message):
                self.assertIsNone(B.parse_site_search(message, 999))

    def test_near_miss_names_only_with_page_words(self):
        self.assertEqual(B.parse_web_open("open the you tube site").key, "youtube")
        self.assertIsNone(B.parse_web_open("open linked"), "no 'page'/'site': could be an app")


class ProfileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "Local State").write_text(json.dumps(LOCAL_STATE), encoding="utf-8")
        patch = mock.patch.object(B, "_user_data_dir", return_value=Path(tmp.name))
        patch.start()
        self.addCleanup(patch.stop)
        self.profiles = B.list_profiles("chrome")

    def pick(self, requested="", setting=""):
        with mock.patch.object(B.settings, "browser_profile", setting, create=True):
            p, how = B.pick_profile(self.profiles, requested)
        return (p.directory if p else None), how

    def test_default_is_the_last_used_profile(self):
        self.assertEqual(self.pick(), ("Default", "last used"))

    def test_named_profile_by_name_account_or_domain(self):
        self.assertEqual(self.pick("work"), ("Profile 3", "asked"))
        self.assertEqual(self.pick("acme"), ("Profile 13", "asked"))
        self.assertEqual(self.pick("admin@acme.com"), ("Profile 13", "asked"))
        # Two profiles called "Alexandra": ask which, don't guess.
        self.assertEqual(self.pick("Alexandra M"), (None, "ambiguous"))

    def test_setting_then_unknown(self):
        self.assertEqual(self.pick(setting="Work"), ("Profile 3", "setting"))
        self.assertEqual(self.pick("nope"), (None, "unknown"))

    def test_opens_url_in_profile_without_the_picker(self):
        launched = []
        request = B.parse_web_open("open my gmail in chrome")
        found = V.Evidence(process={"pid": None, "name": "chrome.exe", "started": "", "cwd": ""},
                           window={"hwnd": None, "title": "Inbox (3) - me@gmail.com - Gmail - Google Chrome", "pid": None})
        with mock.patch.object(B, "_browser_exe", return_value="chrome.exe"), \
             mock.patch.object(B.settings, "browser_profile", "", create=True), \
             mock.patch.object(V, "verify_app_window", return_value=found) as verify:
            result = B.open_website(request, launcher=lambda cmd, **kw: launched.append(cmd))
        self.assertEqual(launched, [["chrome.exe", "--profile-directory=Default", "https://mail.google.com/"]])
        self.assertEqual(verify.call_args.args[0], "gmail")
        text = B.describe(result)
        self.assertIn("profile Alexandra (Alexandra M)", text)
        self.assertIn("the profile you used last", text)
        self.assertIn("Checked: the window shows “Inbox (3) - me@gmail.com - Gmail", text)

    def test_unknown_profile_lists_choices_and_launches_nothing(self):
        launched = []
        request = B.parse_web_open("open gmail in chrome with my school profile")
        result = B.open_website(request, launcher=lambda cmd, **kw: launched.append(cmd), verify=False)
        self.assertEqual(launched, [])
        self.assertIn("no Chrome profile called 'school'", result["error"])
        self.assertIn("Work", result["error"])

    def test_unverified_page_says_so(self):
        request = B.parse_web_open("open my gmail in chrome")
        with mock.patch.object(B, "_browser_exe", return_value="chrome.exe"), \
             mock.patch.object(V, "verify_app_window", return_value=V.Evidence()):
            result = B.open_website(request, launcher=lambda cmd, **kw: None)
        self.assertIn("couldn't see it load", B.describe(result))


class ShortcutTests(unittest.TestCase):
    def run_dispatch(self, message):
        from server.services.chat_pipeline.context import ChatContext
        from server.services.chat_pipeline.stage_dispatch import dispatch_direct_commands
        ctx = ChatContext(db=mock.Mock(), user_message=message)
        ctx.conv = mock.Mock(id=1)
        asyncio.run(dispatch_direct_commands(ctx))
        return ctx

    def test_open_my_gmail_in_chrome_opens_the_site_not_plain_chrome(self):
        fake = {"url": "https://mail.google.com/", "site": "Gmail", "browser": "chrome", "profile": "Alexandra",
                "chosen_by": "last used", "evidence": None, "error": ""}
        with mock.patch.object(B, "open_website", return_value=fake) as opened,              mock.patch("server.services.app_launcher.launch_app") as launch:
            ctx = self.run_dispatch("Open my Gmail in chrome")
        launch.assert_not_called()
        self.assertEqual(opened.call_args.args[0].url, "https://mail.google.com/")
        self.assertEqual(ctx.direct_command_type, "open_website")
        self.assertIn("profile Alexandra", ctx.full_response)

    def test_app_shortcut_reports_whether_its_window_appeared(self):
        with mock.patch("server.services.app_launcher.launch_app", return_value=(True, "Launched spotify")),              mock.patch("server.services.app_launcher.find_app", return_value=(True, "spotify")),              mock.patch.object(V, "verify_app_window", return_value=V.Evidence()):
            ctx = self.run_dispatch("open spotify")
        self.assertEqual(ctx.direct_command_type, "launch")
        self.assertIn("no window has appeared yet", ctx.full_response)


class ToolTests(unittest.TestCase):
    def test_open_website_tool(self):
        from server.services.tool_runner.executor import execute_tool_call
        fake = {"url": "https://mail.google.com/", "site": "gmail", "browser": "chrome", "profile": "Work",
                "chosen_by": "asked", "evidence": None, "error": ""}
        with mock.patch.object(B, "open_website", return_value=fake) as opened, \
             mock.patch("server.services.audit_log.record_audit"):
            result = asyncio.run(execute_tool_call(
                {"tool": "open_website", "args": {"site": "gmail", "browser": "chrome", "profile": "Work"}}, None, 1))
        request = opened.call_args.args[0]
        self.assertEqual((request.url, request.browser, request.profile), ("https://mail.google.com/", "chrome", "Work"))
        self.assertIn("Opened gmail in Chrome, profile Work", result)


if __name__ == "__main__":
    unittest.main()
