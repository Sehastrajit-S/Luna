"""Library: uploaded attachments and files Luna created in its workspace."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.models.database import Attachment, Base, Conversation, Message, get_db
from server.routers import library
from server.services import workspace


class LibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

        app = FastAPI()
        app.include_router(library.router)

        def db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = db
        self.client = TestClient(app)

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.ws.mkdir()
        for module in (library, workspace):
            patcher = mock.patch.object(module, "WORKSPACE_DIR", self.ws)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _seed_uploads(self) -> None:
        s = self.Session()
        conv = Conversation(title="Trip planning")
        s.add(conv)
        s.flush()
        msg = Message(conversation_id=conv.id, role="user", content="see attached")
        s.add(msg)
        s.flush()
        now = datetime.now(timezone.utc)
        s.add_all([
            Attachment(id="old", conversation_id=conv.id, message_id=msg.id, filename="itinerary.pdf", mime_type="application/pdf",
                       kind="pdf", size_bytes=1000, created_at=now - timedelta(days=2)),
            Attachment(id="new", conversation_id=conv.id, message_id=msg.id, filename="budget.xlsx", mime_type="application/vnd.ms-excel",
                       kind="spreadsheet", size_bytes=2000, created_at=now),
            Attachment(id="draft", filename="unsent.txt", mime_type="text/plain", kind="text", size_bytes=10, created_at=now),
        ])
        s.commit()
        s.close()

    def _write(self, rel: str, text: str = "x", age_s: float = 0) -> None:
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))

    def test_uploads_lists_sent_files_newest_first_with_chat(self) -> None:
        self._seed_uploads()
        items = self.client.get("/api/library/uploads").json()["items"]
        self.assertEqual([i["id"] for i in items], ["new", "old"], "drafts excluded, newest first")
        self.assertEqual(items[0]["conversation_title"], "Trip planning")
        self.assertIsNotNone(items[0]["conversation_id"])

    def test_uploads_search(self) -> None:
        self._seed_uploads()
        items = self.client.get("/api/library/uploads", params={"q": "ITIN"}).json()["items"]
        self.assertEqual([i["filename"] for i in items], ["itinerary.pdf"])

    def test_created_lists_workspace_output_and_skips_internal_folders(self) -> None:
        self._write("docs/report.md", age_s=100)
        self._write("data.csv", age_s=10)
        self._write("skills/some-skill/SKILL.md")
        self._write("_tests/scratch.txt")
        self._write(".cache/blob")
        items = self.client.get("/api/library/created").json()["items"]
        self.assertEqual([i["path"] for i in items], ["data.csv", "docs/report.md"])
        self.assertEqual(items[1]["folder"], "docs")

    def test_created_search(self) -> None:
        self._write("docs/report.md")
        self._write("data.csv")
        items = self.client.get("/api/library/created", params={"q": "docs"}).json()["items"]
        self.assertEqual([i["name"] for i in items], ["report.md"])

    def test_created_raw_downloads_and_blocks_escapes(self) -> None:
        self._write("docs/report.md", "hello")
        res = self.client.get("/api/library/created/raw", params={"path": "docs/report.md"})
        self.assertEqual((res.status_code, res.text), (200, "hello"))
        (Path(self._tmp.name) / "secret.txt").write_text("nope", encoding="utf-8")
        self.assertEqual(self.client.get("/api/library/created/raw", params={"path": "../secret.txt"}).status_code, 400)
        self._write("skills/x/SKILL.md")
        self.assertEqual(self.client.get("/api/library/created/raw", params={"path": "skills/x/SKILL.md"}).status_code, 404)
        self.assertEqual(self.client.get("/api/library/created/raw", params={"path": "missing.md"}).status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
