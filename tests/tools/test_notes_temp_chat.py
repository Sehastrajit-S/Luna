"""Notes app API, and temporary chats (hidden, not learned from, deleted on leave)."""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timedelta
from unittest import mock

from tests.tools import _bootstrap  # noqa: F401

from fastapi import BackgroundTasks, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.models.database import Base, Conversation, Fact, Message, Trace, get_db


def _engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _client(router, Session):
    app = FastAPI()
    app.include_router(router)

    def db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = db
    return TestClient(app)


class NotesTests(unittest.TestCase):
    def setUp(self) -> None:
        from server.routers import notes
        self.Session = sessionmaker(bind=_engine())
        self.client = _client(notes.router, self.Session)

    def test_create_edit_and_read(self) -> None:
        n = self.client.post("/api/notes", json={}).json()
        self.assertEqual((n["title"], n["body"], n["pinned"], n["heading"]), ("", "", False, ""))
        r = self.client.patch(f"/api/notes/{n['id']}", json={"body": "Groceries\n- milk\n- eggs"})
        body = r.json()
        self.assertEqual(body["heading"], "Groceries", "an untitled note is named by its first line")
        self.assertEqual(body["preview"], "- milk - eggs", "and the preview is the text after it")
        self.assertGreaterEqual(body["updated_at"], n["updated_at"])
        full = self.client.get(f"/api/notes/{n['id']}").json()
        self.assertEqual(full["body"], "Groceries\n- milk\n- eggs")

    def test_list_pinned_first_then_recent_and_search(self) -> None:
        a = self.client.post("/api/notes", json={"title": "Alpha", "body": "first"}).json()
        self.client.post("/api/notes", json={"title": "Beta", "body": "trip to Lisbon"})
        self.client.post("/api/notes", json={"title": "Gamma", "body": "third"})
        self.client.patch(f"/api/notes/{a['id']}", json={"pinned": True})
        notes = self.client.get("/api/notes").json()["notes"]
        self.assertEqual([n["title"] for n in notes], ["Alpha", "Gamma", "Beta"])
        self.assertNotIn("body", notes[0], "the list sends previews, not whole notes")
        self.assertEqual([n["title"] for n in self.client.get("/api/notes?q=lisbon").json()["notes"]], ["Beta"])
        self.assertEqual(self.client.get("/api/notes?q=nothing").json()["notes"], [])

    def test_pinning_does_not_count_as_an_edit(self) -> None:
        n = self.client.post("/api/notes", json={"title": "x"}).json()
        pinned = self.client.patch(f"/api/notes/{n['id']}", json={"pinned": True}).json()
        self.assertEqual(pinned["updated_at"], n["updated_at"])

    def test_delete_and_missing(self) -> None:
        n = self.client.post("/api/notes", json={"title": "bye"}).json()
        self.assertEqual(self.client.delete(f"/api/notes/{n['id']}").status_code, 204)
        r = self.client.get(f"/api/notes/{n['id']}")
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (404, "not_found"))
        self.assertEqual(self.client.patch("/api/notes/999", json={"title": "x"}).status_code, 404)


class TemporaryChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _engine()
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.addCleanup(self.db.close)
        # Shared "active conversation" lives in a JSON file; keep it in memory here.
        self.active = {"id": None}
        for target in ("server.services.chat_pipeline.stage_persist", "server.services.conversations", "server.routers.chat"):
            for name, fn in (("get_active_conversation_id", lambda: self.active["id"]),
                             ("set_active_conversation_id", lambda v: self.active.update(id=v))):
                try:
                    patcher = mock.patch(f"{target}.{name}", fn)
                    patcher.start()
                    self.addCleanup(patcher.stop)
                except AttributeError:
                    pass

    def _persist(self, message: str, *, temporary: bool, conversation_id=None, standalone: bool = False):
        from server.services.chat_pipeline.context import ChatContext
        from server.services.chat_pipeline.stage_persist import persist
        ctx = ChatContext(db=self.db, user_message=message, conversation_id=conversation_id,
                          temporary=temporary, standalone=standalone)
        asyncio.run(persist(ctx))
        return ctx

    def test_standalone_task_neither_joins_nor_replaces_the_open_chat(self) -> None:
        # Remote-control tasks: a saved conversation of their own on the device.
        normal = self._persist("chatting about ollama models", temporary=False)
        task = self._persist("open whatsapp", temporary=False, standalone=True)
        self.assertNotEqual(task.conv.id, normal.conv.id)
        self.assertFalse(task.conv.temporary, "it's kept in Recent, unlike a temporary chat")
        self.assertEqual(self.active["id"], normal.conv.id, "the chat open on the device stays active")
        follow_up = self._persist("search it then find the right name", temporary=False,
                                  standalone=True, conversation_id=task.conv.id)
        self.assertEqual(follow_up.conv.id, task.conv.id)
        self.assertEqual(self.active["id"], normal.conv.id)

    def test_temporary_chat_never_joins_the_shared_conversation(self) -> None:
        normal = self._persist("hello", temporary=False)
        self.assertEqual(self.active["id"], normal.conv.id)
        temp = self._persist("secret question", temporary=True)
        self.assertNotEqual(temp.conv.id, normal.conv.id, "a temporary chat starts fresh, not in the active chat")
        self.assertTrue(temp.conv.temporary)
        self.assertEqual(self.active["id"], normal.conv.id, "and doesn't become the active chat")
        again = self._persist("follow-up", temporary=True, conversation_id=temp.conv.id)
        self.assertEqual(again.conv.id, temp.conv.id)
        self.assertEqual(self.db.query(Message).filter_by(conversation_id=temp.conv.id).count(), 2,
                         "messages are kept while it's open so Luna can follow the thread")

    def test_finalize_skips_memory_and_logs(self) -> None:
        from server.services.chat_pipeline import stage_finalize
        ctx = self._persist("what's 2+2", temporary=True)
        ctx.full_response = "4"
        tasks = BackgroundTasks()
        with mock.patch.object(stage_finalize, "_chat_print") as log, \
                mock.patch("server.services.decision_log.record_turn") as decision:
            asyncio.run(stage_finalize.finalize(ctx, tasks))
        self.assertEqual(tasks.tasks, [], "no fact extraction, summaries or activity tracking")
        log.assert_not_called()
        decision.assert_not_called()
        self.assertEqual(ctx.sse_events[-1]["type"], "done")
        self.assertTrue(ctx.sse_events[-1]["temporary"])
        # A normal chat still schedules its background work.
        normal = self._persist("hi there", temporary=False)
        normal.full_response = "Hello!"
        tasks = BackgroundTasks()
        with mock.patch.object(stage_finalize, "_chat_print"), mock.patch("server.services.decision_log.record_turn"):
            asyncio.run(stage_finalize.finalize(normal, tasks))
        self.assertGreaterEqual(len(tasks.tasks), 1)

    def test_hidden_from_recent_and_context(self) -> None:
        from server.routers import chat
        client = _client(chat.router, self.Session)
        normal = self._persist("hello", temporary=False)
        temp = self._persist("private", temporary=True)
        ids = [c["id"] for c in client.get("/api/chat/conversations").json()]
        self.assertIn(normal.conv.id, ids)
        self.assertNotIn(temp.conv.id, ids)
        self.active["id"] = temp.conv.id          # e.g. set by an older client
        self.assertIsNone(client.get("/api/chat/context").json()["active_conversation_id"])

    def test_deleting_a_temporary_chat_forgets_everything(self) -> None:
        from server.routers import chat
        client = _client(chat.router, self.Session)
        temp = self._persist("remember my PIN is 1234", temporary=True)
        normal = self._persist("my favourite colour is green", temporary=False)
        self.db.add_all([
            Fact(content="PIN is 1234", category="personal", source_conversation_id=temp.conv.id),
            Fact(content="Likes green", category="personal", source_conversation_id=normal.conv.id),
            Trace(span_id="s1", name="llm_call", conversation_id=temp.conv.id, start_time=0.0),
        ])
        self.db.commit()
        temp_id, normal_id = temp.conv.id, normal.conv.id
        self.assertEqual(client.delete(f"/api/chat/conversations/{temp_id}").status_code, 200)
        self.db.expire_all()
        self.assertIsNone(self.db.get(Conversation, temp_id))
        self.assertEqual([f.content for f in self.db.query(Fact).all()], ["Likes green"])
        self.assertEqual(self.db.query(Trace).count(), 0)
        # Deleting a normal chat still only unlinks what it learned.
        client.delete(f"/api/chat/conversations/{normal_id}")
        self.db.expire_all()
        self.assertEqual([(f.content, f.source_conversation_id) for f in self.db.query(Fact).all()], [("Likes green", None)])

    def test_purge_removes_all_or_idle_temporary_chats(self) -> None:
        from server.services.conversations import purge_temporary
        old = self._persist("old", temporary=True)
        fresh = self._persist("fresh", temporary=True)
        normal = self._persist("keep", temporary=False)
        long_ago = datetime.utcnow() - timedelta(hours=10)
        self.db.query(Message).filter_by(conversation_id=old.conv.id).update({Message.created_at: long_ago})
        self.db.query(Conversation).filter_by(id=old.conv.id).update({Conversation.started_at: long_ago})
        self.db.commit()
        self.assertEqual(purge_temporary(self.db, idle_for=timedelta(hours=6)), 1)
        self.assertEqual({c.id for c in self.db.query(Conversation).all()}, {fresh.conv.id, normal.conv.id})
        self.assertEqual(purge_temporary(self.db), 1, "on restart, every temporary chat goes")
        self.assertEqual([c.id for c in self.db.query(Conversation).all()], [normal.conv.id])

    def test_activity_calendar_leaves_temporary_chats_out(self) -> None:
        from server.services.activity_calendar import month_activity
        self._persist("normal message", temporary=False)
        self._persist("temporary message", temporary=True)
        now = datetime.now()
        data = month_activity(self.db, now.year, now.month)
        self.assertEqual(data["total_messages"], 1)
        self.assertEqual(data["streak"], 1)


if __name__ == "__main__":
    unittest.main()
