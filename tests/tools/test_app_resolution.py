"""App launching finds installed apps whose profile name isn't on PATH (Chrome,
Store apps like WhatsApp), says "did you mean" instead of a raw WinError, and
list_open_apps reports what's open instead of the model guessing."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from server.services.app_launcher import discovery, launcher, open_apps

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WHATSAPP = "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"


class WindowsResolutionTests(unittest.TestCase):
    def setUp(self):
        patches = [
            mock.patch.object(launcher, "IS_WINDOWS", True),
            mock.patch.object(launcher, "IS_MAC", False),
            mock.patch.object(launcher, "IS_LINUX", False),
            mock.patch.object(launcher.shutil, "which", return_value=None),   # nothing on PATH
            mock.patch.object(discovery, "_get_luna_apps", return_value={}),
            mock.patch.object(discovery, "_get_registry_apps", return_value={"chrome": CHROME_EXE}),
            mock.patch.object(discovery, "_get_start_menu_apps", return_value={"google chrome": "C:\\Start\\Google Chrome.lnk"}),
            mock.patch.object(discovery, "_get_store_apps", return_value={"whatsapp": WHATSAPP, "spotify": "shell:AppsFolder\\Spotify"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        real_exists = launcher.Path.exists
        exists = mock.patch.object(launcher.Path, "exists", lambda self: str(self) == CHROME_EXE or real_exists(self))
        exists.start()
        self.addCleanup(exists.stop)

    def test_profile_name_not_on_path_uses_the_registered_exe(self):
        self.assertEqual(launcher.find_app("chrome"), (True, CHROME_EXE))
        self.assertEqual(launcher.find_app("Google Chrome"), (True, CHROME_EXE))

    def test_store_app_is_found(self):
        self.assertEqual(launcher.find_app("WhatsApp"), (True, WHATSAPP))
        self.assertEqual(launcher.find_app("whats app"), (True, WHATSAPP))

    def test_uri_profiles_still_win(self):
        self.assertEqual(launcher.find_app("teams"), (True, "ms-teams:"))

    def test_unknown_app_is_not_found_with_suggestions(self):
        ok, message = launcher.find_app("whatsapq messenger zz")
        self.assertFalse(ok)
        self.assertIn("Couldn't find an app called", message)
        ok, message = launcher.find_app("zzqqxx")
        self.assertFalse(ok)
        self.assertNotIn("WinError", message)

    def test_launch_failure_suggests_instead_of_raw_error(self):
        with mock.patch.object(launcher, "find_app", return_value=(True, "whatsap")), \
             mock.patch.object(launcher, "_launch_target", side_effect=FileNotFoundError(2, "The system cannot find the file specified")), \
             mock.patch.object(launcher.os, "startfile", side_effect=FileNotFoundError(2, "nope"), create=True):
            ok, message = launcher.launch_app("whatsap")
        self.assertFalse(ok)
        self.assertIn("Did you mean whatsapp", message)
        self.assertNotIn("WinError", message)


class OpenAppsTests(unittest.TestCase):
    def test_groups_windows_by_app_and_skips_shell_pieces(self):
        raw = [
            ("chrome.exe", "Inbox - Gmail"), ("chrome.exe", "Luna PR #38"), ("Code.exe", "remote.js - Luna"),
            ("explorer.exe", "Program Manager"), ("TextInputHost.exe", "Windows Input Experience"),
            ("explorer.exe", "Downloads"), ("WhatsApp.Root.exe", "WhatsApp"),
        ]
        with mock.patch.object(open_apps, "PLATFORM", "Windows"), \
             mock.patch.object(open_apps, "_windows_open_windows", return_value=raw):
            apps = open_apps.list_open_apps()
        self.assertEqual([a["app"] for a in apps], ["Google Chrome", "VS Code", "File Explorer", "WhatsApp"])
        self.assertEqual(apps[0]["windows"], ["Inbox - Gmail", "Luna PR #38"])
        self.assertEqual(apps[2]["windows"], ["Downloads"])

    def test_tool_reports_open_apps(self):
        from server.services.tool_registry import TOOL_REGISTRY, RiskLevel
        from server.services.tool_runner.executor import execute_tool_call
        self.assertEqual(TOOL_REGISTRY["list_open_apps"].risk, RiskLevel.SAFE)
        with mock.patch("server.services.app_launcher.list_open_apps", return_value=[{"app": "Spotify", "process": "Spotify.exe", "windows": ["Spotify Premium"]}]):
            result = asyncio.run(execute_tool_call({"tool": "list_open_apps", "args": {}}, None, 1))
        self.assertEqual(json.loads(result)["open_apps"][0]["app"], "Spotify")
        with mock.patch("server.services.app_launcher.list_open_apps", return_value=[]):
            result = asyncio.run(execute_tool_call({"tool": "list_open_apps", "args": {}}, None, 1))
        self.assertIn("No apps", result)


if __name__ == "__main__":
    unittest.main()
