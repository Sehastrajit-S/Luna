"""Tasks app API: add, edit, complete/reopen, lists, delete, clear completed."""
from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.models.database import Base, Task, get_db
from server.routers import tasks as tasks_router


class TasksAppTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        app = FastAPI()
        app.include_router(tasks_router.router)

        def db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = db
        self.client = TestClient(app)

    def add(self, **body):
        r = self.client.post("/api/tasks", json=body)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_add_with_due_time_list_and_priority(self) -> None:
        t = self.add(title="  Call mom  ", due_date="2026-11-18T22:00:00Z", priority="high", list_name="#Family")
        self.assertEqual(t["title"], "Call mom")
        self.assertEqual(t["due_date"], "2026-11-18T22:00:00Z", "stored as UTC, returned with Z")
        self.assertEqual((t["priority"], t["list_name"], t["completed"]), ("high", "Family", False))
        # An offset is converted to UTC.
        t2 = self.add(title="Standup", due_date="2026-11-18T09:30:00-05:00")
        self.assertEqual(t2["due_date"], "2026-11-18T14:30:00Z")

    def test_list_returns_open_completed_and_list_names(self) -> None:
        a = self.add(title="A", list_name="Work")
        self.add(title="B", list_name="home")
        self.add(title="C")
        self.client.patch(f"/api/tasks/{a['id']}", json={"completed": True})
        data = self.client.get("/api/tasks").json()
        self.assertEqual(sorted(t["title"] for t in data["tasks"]), ["A", "B", "C"])
        self.assertEqual(data["lists"], ["home", "Work"])
        self.assertEqual(data["completed_total"], 1)

    def test_complete_and_reopen(self) -> None:
        t = self.add(title="Water plants")
        done = self.client.patch(f"/api/tasks/{t['id']}", json={"completed": True}).json()
        self.assertTrue(done["completed"])
        self.assertIsNotNone(done["completed_at"])
        again = self.client.patch(f"/api/tasks/{t['id']}", json={"completed": False}).json()
        self.assertFalse(again["completed"])
        self.assertIsNone(again["completed_at"])

    def test_edit_and_clear_fields(self) -> None:
        t = self.add(title="Pay rent", due_date="2026-12-01T17:00:00Z", list_name="Home", description="Online")
        r = self.client.patch(f"/api/tasks/{t['id']}", json={"due_date": None, "list_name": "", "description": "",
                                                            "priority": "low", "title": "Pay December rent"})
        body = r.json()
        self.assertEqual((body["title"], body["due_date"], body["list_name"], body["description"], body["priority"]),
                         ("Pay December rent", None, None, "", "low"))
        # Fields left out stay as they were.
        body = self.client.patch(f"/api/tasks/{t['id']}", json={"priority": "high"}).json()
        self.assertEqual(body["title"], "Pay December rent")

    def test_validation_and_missing(self) -> None:
        self.assertEqual(self.client.post("/api/tasks", json={"title": "   "}).status_code, 422)
        self.assertEqual(self.client.post("/api/tasks", json={"title": "x", "priority": "urgent"}).status_code, 422)
        t = self.add(title="x")
        r = self.client.patch(f"/api/tasks/{t['id']}", json={"title": "  "})
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (400, "bad_request"))
        r = self.client.patch("/api/tasks/9999", json={"completed": True})
        self.assertEqual((r.status_code, r.json()["detail"]["kind"]), (404, "not_found"))
        self.assertEqual(self.client.delete("/api/tasks/9999").status_code, 404)

    def test_delete_and_clear_completed(self) -> None:
        keep = self.add(title="Keep")
        gone = self.add(title="Gone")
        for title in ("Done 1", "Done 2"):
            t = self.add(title=title)
            self.client.patch(f"/api/tasks/{t['id']}", json={"completed": True})
        self.assertEqual(self.client.delete(f"/api/tasks/{gone['id']}").status_code, 204)
        self.assertEqual(self.client.delete("/api/tasks/completed").json(), {"removed": 2})
        self.assertEqual([t["title"] for t in self.client.get("/api/tasks").json()["tasks"]], [keep["title"]])

    def test_tasks_luna_added_from_chat_show_up(self) -> None:
        s = self.Session()
        s.add(Task(title="Buy milk", priority="medium"))      # as the chat [TASK:…] command saves it
        s.commit()
        s.close()
        data = self.client.get("/api/tasks").json()
        self.assertEqual([(t["title"], t["list_name"]) for t in data["tasks"]], [("Buy milk", None)])


if __name__ == "__main__":
    unittest.main()
