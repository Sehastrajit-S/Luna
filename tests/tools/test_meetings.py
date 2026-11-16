"""Meeting mode: chunked recording upload, transcription, minutes, and where the files land."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.config import settings
from server.routers import library
from server.routers.meetings import router as meetings_router
from server.services import workspace
from server.services.meetings import MeetingError, MeetingNotFound, service, store
from server.services.meetings.minutes import split_for_model, write_minutes
from server.services.stt import Segment

SEGMENTS = [
    Segment(0.0, 4.0, "Okay, let's review the launch plan."),
    Segment(65.0, 70.0, "Priya will send the vendor shortlist by Friday."),
    Segment(130.0, 136.0, "We decided to move the launch to May."),
]


def run(coro):
    return asyncio.run(coro)


class MeetingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.ws.mkdir()
        for module in (workspace, library):
            patcher = mock.patch.object(module, "WORKSPACE_DIR", self.ws)
            patcher.start()
            self.addCleanup(patcher.stop)
        audit = mock.patch.object(service, "record_audit")
        audit.start()
        self.addCleanup(audit.stop)


class RecordingTests(MeetingTestCase):
    def test_start_creates_a_meeting_folder_in_the_workspace(self) -> None:
        m = service.start("Weekly sync")
        self.assertRegex(m["id"], r"^\d{4}-\d{2}-\d{2}-\d{4}-weekly-sync$")
        self.assertEqual(m["status"], "recording")
        self.assertTrue((self.ws / "meetings" / m["id"] / store.META).exists())

    def test_chunks_append_in_order_and_retries_are_harmless(self) -> None:
        m = service.start()
        service.append_audio(m["id"], 0, b"aaa")
        service.append_audio(m["id"], 0, b"aaa")          # a retried upload of chunk 0
        service.append_audio(m["id"], 1, b"bb")
        self.assertEqual((self.ws / "meetings" / m["id"] / store.AUDIO).read_bytes(), b"aaabb")
        with self.assertRaises(MeetingError) as ctx:
            service.append_audio(m["id"], 5, b"x")
        self.assertEqual(ctx.exception.kind, "out_of_order")

    def test_limits_and_states(self) -> None:
        m = service.start()
        with self.assertRaises(MeetingError):
            service.append_audio(m["id"], 0, b"")
        with mock.patch.object(service, "MAX_AUDIO_BYTES", 4):
            with self.assertRaises(MeetingError) as ctx:
                service.append_audio(m["id"], 0, b"12345")
        self.assertEqual(ctx.exception.kind, "too_large")
        with self.assertRaises(MeetingError):
            run(self._finish(m["id"]))                       # nothing recorded
        with self.assertRaises(MeetingError) as ctx:
            service.append_audio(m["id"], 0, b"late")
        self.assertEqual(ctx.exception.kind, "wrong_state")

    async def _finish(self, meeting_id):
        return service.finish(meeting_id)

    def test_ids_cannot_escape_the_meetings_folder(self) -> None:
        for bad in ("../../etc", "..", "2026-01-01-1200/../../x", ""):
            with self.assertRaises(MeetingNotFound):
                service.get(bad)


class ProcessingTests(MeetingTestCase):
    def _recorded(self) -> str:
        m = service.start("Launch review")
        service.append_audio(m["id"], 0, b"fake-webm")
        store.update(m["id"], status="processing", stage="transcribing", ended_at="x")
        return m["id"]

    async def _complete(self, prompt, system):
        self.prompts.append(prompt)
        return ("<think>planning</think>Title: Launch date review\n## Summary\nLaunch moves to May.\n\n"
                "## Action items\n- [ ] Priya: send vendor shortlist (Friday)")

    def test_transcript_and_minutes_are_written(self) -> None:
        meeting_id = self._recorded()
        self.prompts = []
        run(service._process(meeting_id, transcribe=lambda path, progress: (SEGMENTS, 140.0), complete=self._complete))
        m = service.get(meeting_id)
        self.assertEqual(m["status"], "done")
        self.assertEqual(m["duration_s"], 140.0)
        self.assertIn("**[00:01:05]** Priya will send the vendor shortlist by Friday.", m["transcript"])
        self.assertTrue(m["minutes"].startswith("# Launch review"), "a title the user gave is kept")
        self.assertNotIn("Title:", m["minutes"])
        self.assertIn("- [ ] Priya: send vendor shortlist (Friday)", m["minutes"])
        self.assertNotIn("<think>", m["minutes"])
        self.assertIn("[00:02:10] We decided to move the launch to May.", self.prompts[0])

    def test_no_speech_is_a_clear_error(self) -> None:
        meeting_id = self._recorded()
        run(service._process(meeting_id, transcribe=lambda path, progress: ([], 30.0), complete=self._complete))
        m = service.get(meeting_id)
        self.assertEqual(m["status"], "error")
        self.assertIn("No speech", m["error"])

    def test_minutes_failure_keeps_the_transcript(self) -> None:
        meeting_id = self._recorded()

        async def broken(prompt, system):
            raise ConnectionError("model offline")

        run(service._process(meeting_id, transcribe=lambda path, progress: (SEGMENTS, 140.0), complete=broken))
        m = service.get(meeting_id)
        self.assertEqual(m["status"], "error")
        self.assertIn("transcript is saved", m["error"])
        self.assertIsNotNone(m["transcript"])

    def test_restart_mid_job_shows_as_interrupted(self) -> None:
        meeting_id = self._recorded()                  # "processing", but no task is running
        self.assertEqual(service.get(meeting_id)["status"], "interrupted")

    def test_meeting_files_show_in_the_library_but_bookkeeping_does_not(self) -> None:
        meeting_id = self._recorded()
        self.prompts = []
        run(service._process(meeting_id, transcribe=lambda path, progress: (SEGMENTS, 140.0), complete=self._complete))
        names = {item["name"] for item in library.list_created(q="")["items"]}
        self.assertEqual(names, {"recording.webm", "transcript.md", "minutes.md"})


class MinutesTests(unittest.TestCase):
    def test_long_meetings_are_summarised_in_parts_then_merged(self) -> None:
        segments = [Segment(i * 10.0, i * 10.0 + 9, "word " * 60) for i in range(60)]
        parts = split_for_model(segments, budget_tokens=1500)
        self.assertGreater(len(parts), 1)
        calls = []

        async def complete(prompt, system):
            calls.append(prompt)
            return "notes"

        with mock.patch.object(settings, "llm_context_window", 2048):
            title, text = run(write_minutes("Long one", "2026-11-16T10:00:00+00:00", 600.0, segments, complete=complete))
        self.assertGreater(len(calls), 2, "one call per part plus the merge")
        self.assertIn("Notes from each part", calls[-1])
        self.assertEqual(title, "Long one")
        self.assertTrue(text.startswith("# Long one"))


class TitleTests(MeetingTestCase):
    def test_untitled_meeting_takes_the_suggested_title(self) -> None:
        m = service.start("")
        service.append_audio(m["id"], 0, b"fake")
        store.update(m["id"], status="processing", stage="transcribing", ended_at="x")

        async def complete(prompt, system):
            return "**Title:** Mobile launch review\n## Summary\nOk."

        run(service._process(m["id"], transcribe=lambda path, progress: (SEGMENTS, 140.0), complete=complete))
        done = service.get(m["id"])
        self.assertEqual(done["title"], "Mobile launch review")
        self.assertTrue(done["minutes"].startswith("# Mobile launch review"))
        self.assertTrue(done["transcript"].startswith("# Mobile launch review: transcript"))


@unittest.skipUnless(__import__("shutil").which("node"), "node is required")
class ChecklistRenderTests(unittest.TestCase):
    def test_task_items_render_as_checkboxes(self) -> None:
        import subprocess
        md = Path(_bootstrap.ROOT) / "interfaces" / "desktop" / "src" / "renderer" / "markdown.js"
        script = ("const fs=require('fs');const vm=require('vm');const w={};"
                  "vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{window:w});"
                  "process.stdout.write(w.renderMarkdown(process.argv[2]))")
        html = subprocess.run(["node", "-e", script, str(md), "- [ ] Priya: send it\n- [x] Done thing\n- plain"],
                              capture_output=True, text=True, timeout=30, check=True).stdout
        self.assertEqual(html.count('class="md-task'), 2)
        self.assertIn("md-task is-done", html)
        self.assertIn("<li>plain</li>", html)
        self.assertNotIn("[ ]", html)


class RouterTests(MeetingTestCase):
    def setUp(self) -> None:
        super().setUp()
        app = FastAPI()
        app.include_router(meetings_router)
        self.client = TestClient(app)

    def test_flow_over_http(self) -> None:
        m = self.client.post("/api/meetings", json={"title": "Standup"}).json()
        self.assertEqual(self.client.put(f"/api/meetings/{m['id']}/audio?seq=0", content=b"abc").status_code, 200)
        self.assertEqual(self.client.put(f"/api/meetings/{m['id']}/audio?seq=3", content=b"abc").status_code, 409)
        self.assertEqual(self.client.get("/api/meetings/not-a-meeting").status_code, 404)
        with mock.patch.object(service, "_process", mock.AsyncMock()):
            finished = self.client.post(f"/api/meetings/{m['id']}/finish").json()
        self.assertEqual(finished["stage"], "transcribing")
        listed = self.client.get("/api/meetings").json()["meetings"]
        self.assertEqual(listed[0]["id"], m["id"])
        self.assertNotIn("transcript", listed[0])

    def test_oversized_chunk_is_rejected_before_reading(self) -> None:
        m = self.client.post("/api/meetings", json={}).json()
        res = self.client.put(f"/api/meetings/{m['id']}/audio?seq=0", content=b"x" * (service.MAX_CHUNK_BYTES + 1))
        self.assertEqual(res.status_code, 413)


if __name__ == "__main__":
    unittest.main(verbosity=2)
