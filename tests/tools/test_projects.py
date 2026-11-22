"""Project files (read-only, inside allowed folders, found via the open VS Code
window) and opening Claude Code in a terminal after confirmation."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from server.services import projects as P
from server.services import verification as V


class ProjectBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "Projects"
        (self.root / "mem-lm" / ".git").mkdir(parents=True)
        (self.root / "mem-lm" / "chat.py").write_text("MODEL = 'qwen2.5:7b'\n", encoding="utf-8")
        (self.root / "mem-lm" / "node_modules" / "x").mkdir(parents=True)
        (self.root / "mem-lm" / "node_modules" / "x" / "notes.md").write_text("vendored", encoding="utf-8")
        (self.root / "other-app" / "src").mkdir(parents=True)
        (self.root / "other-app" / "src" / "chat.py").write_text("print('other')\n", encoding="utf-8")
        (self.root / "other-app" / "README.md").write_text("# other", encoding="utf-8")
        self.secret = Path(self.tmp.name) / "secret.txt"
        self.secret.write_text("password", encoding="utf-8")
        self.vscode = []
        # Nothing in these tests may open a real terminal; tests that launch stub Popen themselves.
        never = mock.Mock(side_effect=AssertionError("tried to open a real terminal"))
        for patch in (mock.patch.object(P.settings, "project_roots", str(self.root), create=True),
                      mock.patch.object(P, "open_in_vscode", lambda: list(self.vscode)),
                      mock.patch.object(P.subprocess, "Popen", never)):
            patch.start()
            self.addCleanup(patch.stop)


class ReadTests(ProjectBase):
    def test_file_in_the_project_open_in_vscode_wins(self):
        self.vscode = [("chat.py", "mem-lm")]
        found = P.read_project_file("chat.py")
        self.assertEqual(found["project"], "mem-lm")
        self.assertIn("qwen2.5:7b", found["content"])
        self.vscode = [("app.py", "other-app")]
        self.assertEqual(P.read_project_file("chat.py")["project"], "other-app")

    def test_named_project_and_nested_paths(self):
        self.assertEqual(P.read_project_file("src/chat.py", "other-app")["content"], "print('other')\n")
        self.assertEqual(P.read_project_file("README.md", "Other App")["project"], "other-app")

    def test_cannot_escape_the_project_folders(self):
        for name in ("../../secret.txt", str(self.secret), "..\\secret.txt"):
            with self.subTest(name=name), self.assertRaises(P.ProjectError):
                P.read_project_file(name, "mem-lm")

    def test_skips_dependency_folders(self):
        with self.assertRaises(P.ProjectError) as caught:
            P.read_project_file("notes.md", "mem-lm")
        self.assertEqual(caught.exception.kind, "not_found")

    def test_not_configured_explains_how(self):
        with mock.patch.object(P.settings, "project_roots", "", create=True):
            with self.assertRaises(P.ProjectError) as caught:
                P.read_project_file("chat.py")
        self.assertEqual(caught.exception.kind, "not_configured")
        self.assertIn("Settings → Coding → Project folders", caught.exception.message)

    def test_unknown_or_ambiguous_project(self):
        with self.assertRaises(P.ProjectError) as caught:
            P.find_project("nope")
        self.assertIn("mem-lm", caught.exception.message)   # lists what exists


class ToolTests(ProjectBase):
    def run_tool(self, name, args):
        from server.services.tool_runner.executor import execute_tool_call
        with mock.patch("server.services.audit_log.record_audit") as audit:
            result = asyncio.run(execute_tool_call({"tool": name, "args": args}, None, 1))
        return result, audit

    def test_workspace_read_falls_back_to_projects(self):
        # The auto-read for "In the chat.py, …" used to fail: chat.py isn't in data/workspace.
        self.vscode = [("chat.py", "mem-lm")]
        result, _ = self.run_tool("workspace_read", {"path": "chat.py"})
        self.assertIn("project mem-lm", result)
        self.assertIn("qwen2.5:7b", result)

    def test_missing_file_says_where_it_looked(self):
        result, _ = self.run_tool("project_read_file", {"file": "nothere.py"})
        self.assertTrue(result.startswith("failed: Couldn't find nothere.py"))

    def test_claude_code_is_risky_and_opens_a_terminal_in_the_project(self):
        from server.services.permission_manager import permission_manager
        decision, message, _ = permission_manager.check("claude_code", {"task": "show the model template"})
        self.assertEqual(decision, "confirm")
        self.assertIn("show the model template", message)

        self.vscode = [("chat.py", "mem-lm")]
        launched = []
        evidence = V.Evidence(process={"pid": 42, "name": "claude.exe", "started": "", "cwd": ""},
                              window={"hwnd": 1, "title": "Claude Code · mem-lm", "pid": 41},
                              screenshot="shot.png", screen_text="> show the model template")
        with mock.patch.object(P, "claude_binary", return_value="claude"), \
             mock.patch.object(P, "verify_claude_started", return_value=evidence), \
             mock.patch.object(P.subprocess, "Popen", side_effect=lambda cmd, **kw: launched.append((cmd, kw))):
            result, audit = self.run_tool("claude_code", {"task": "show the model template; then explain it"})
        self.assertIn("Opened Claude Code", result)
        self.assertIn("command check: claude.exe is running (pid 42)", result)
        self.assertIn("window check: 'Claude Code · mem-lm' is open", result)
        self.assertIn("screenshot: shot.png", result)
        self.assertIn("> show the model template", result)
        command, kwargs = launched[0]
        self.assertEqual(Path(kwargs["cwd"]), self.root / "mem-lm")
        self.assertIn("claude", command)
        if command[0].lower().endswith(("wt.exe", "wt")):
            self.assertEqual(command[-1], "show the model template\\; then explain it")   # wt would split on ";"
        self.assertEqual(audit.call_args.args[0], "claude_code")

    def test_unverified_launch_is_reported_as_unconfirmed(self):
        with mock.patch.object(P, "claude_binary", return_value="claude"), \
             mock.patch.object(P, "verify_claude_started", return_value=V.Evidence()), \
             mock.patch.object(P.subprocess, "Popen"):
            result, audit = self.run_tool("claude_code", {"task": "x", "project": "mem-lm"})
        self.assertIn("couldn't confirm it started", result)
        self.assertIn("no matching process found", result)
        self.assertEqual(audit.call_args.kwargs["status"], "unverified")

    def test_check_claude_code(self):
        with mock.patch.object(V, "find_processes", return_value=[]):
            result, _ = self.run_tool("check_claude_code", {"project": "mem-lm"})
        self.assertIn("No Claude Code session is running in mem-lm", result)

        proc = mock.Mock(pid=7, info={"name": "claude.exe", "create_time": 0})
        proc.cwd.return_value = str(self.root / "mem-lm")

        def shot(evidence, label):
            evidence.screenshot, evidence.screen_text = "s.png", "Template: {{ .Prompt }}"
            return evidence

        with mock.patch.object(V, "find_processes", return_value=[proc]), \
             mock.patch.object(V, "window_for", return_value={"hwnd": 3, "title": "Claude Code", "pid": 6}), \
             mock.patch.object(V, "screenshot_evidence", side_effect=shot):
            result, _ = self.run_tool("check_claude_code", {"project": "mem-lm"})
        self.assertIn("Claude Code is running in mem-lm", result)
        self.assertIn("Template: {{ .Prompt }}", result)

    def test_claude_code_not_installed(self):
        with mock.patch.object(P, "claude_binary", return_value=None):
            result, audit = self.run_tool("claude_code", {"task": "x", "project": "mem-lm"})
        self.assertIn("isn't installed", result)
        self.assertEqual(audit.call_args.kwargs["status"], "error")


class VerificationTests(unittest.TestCase):
    def test_claude_start_checks_process_then_window_then_screenshot(self):
        proj = P.Project("mem-lm", Path("E:/p/mem-lm"))
        proc = mock.Mock(pid=9, info={"name": "claude.exe", "create_time": 0})
        proc.cwd.return_value = "E:/p/mem-lm"
        proc.is_running.return_value = True
        sleeps = []
        with mock.patch.object(V, "wait_for_process", return_value=proc) as waited, \
             mock.patch.object(V, "window_for", return_value={"hwnd": 5, "title": "Claude Code · mem-lm", "pid": 8}) as win, \
             mock.patch.object(V, "screenshot_evidence", side_effect=lambda e, label: e) as shot:
            evidence = P.verify_claude_started(proj, "show the template; explain", 100.0, sleep=sleeps.append)
        self.assertTrue(evidence.verified)
        self.assertEqual(waited.call_args.kwargs["cmd_contains"], "show the template")   # matched by its own command line
        self.assertEqual(win.call_args.kwargs["prefer"], ("claude", "mem-lm"))
        self.assertEqual(shot.call_args.args[1], "claude-mem-lm")
        self.assertEqual(sleeps, [P.SETTLE_SECONDS])

    def test_claude_exiting_immediately_is_not_verified(self):
        proc = mock.Mock(pid=9, info={"name": "claude.exe", "create_time": 0})
        proc.is_running.return_value = False
        with mock.patch.object(V, "wait_for_process", return_value=proc):
            evidence = P.verify_claude_started(P.Project("x", Path(".")), "t", 0, sleep=lambda s: None)
        self.assertFalse(evidence.verified)
        self.assertIn("exited right after starting", evidence.summary())

    def test_app_window_check(self):
        apps = [{"app": "Google Chrome", "process": "chrome.exe", "windows": ["New Tab - Google Chrome"]},
                {"app": "WhatsApp", "process": "WhatsApp.Root.exe", "windows": ["WhatsApp"]}]
        found = V.verify_app_window("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                                    sleep=lambda s: None, list_apps=lambda: apps)
        self.assertEqual(found.window["title"], "New Tab - Google Chrome")
        found = V.verify_app_window("whats app", "shell:AppsFolder\\5319275A.WhatsAppDesktop!App",
                                    sleep=lambda s: None, list_apps=lambda: apps)
        self.assertTrue(found.verified)
        missing = V.verify_app_window("spotify", "spotify", timeout=0, sleep=lambda s: None, list_apps=lambda: apps)
        self.assertFalse(missing.verified)

    def test_launch_app_reports_unverified_launch(self):
        from server.services.tool_runner.executor import execute_tool_call
        with mock.patch("server.services.app_launcher.launch_app", return_value=(True, "Launched spotify")), \
             mock.patch("server.services.app_launcher.find_app", return_value=(True, "spotify")), \
             mock.patch.object(V, "verify_app_window", return_value=V.Evidence()):
            result = asyncio.run(execute_tool_call({"tool": "launch_app", "args": {"app": "spotify"}}, None, 1))
        self.assertIn("no window for it appeared", result)
        verified = V.Evidence(process={"pid": None, "name": "Spotify.exe", "started": "", "cwd": ""},
                              window={"hwnd": None, "title": "Spotify Premium", "pid": None})
        with mock.patch("server.services.app_launcher.launch_app", return_value=(True, "Launched spotify")), \
             mock.patch("server.services.app_launcher.find_app", return_value=(True, "spotify")), \
             mock.patch.object(V, "verify_app_window", return_value=verified):
            result = asyncio.run(execute_tool_call({"tool": "launch_app", "args": {"app": "spotify"}}, None, 1))
        self.assertIn("Verified: a 'Spotify Premium' window is open", result)

    def test_screenshot_files_are_capped(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(V, "SCREENSHOT_DIR", Path(tmp)), \
             mock.patch.object(V, "KEEP_SCREENSHOTS", 3):
            for i in range(5):
                (Path(tmp) / f"2020010{i}-000000-old.png").write_bytes(b"x")
            V.save_screenshot(Image.new("RGB", (4, 4)), "Claude mem-lm")
            self.assertEqual(len(list(Path(tmp).glob("*.png"))), 3)


if __name__ == "__main__":
    unittest.main()
