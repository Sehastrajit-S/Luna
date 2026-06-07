from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.tools import _bootstrap  # noqa: F401


class TaskCalendarToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from backend.models.database import Base

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.Session()

    def tearDown(self) -> None:
        self.db.close()

    async def test_create_task_tool_uses_database_session(self) -> None:
        from backend.models.database import Task
        from backend.services.tool_runner import execute_tool_call

        result = await execute_tool_call(
            {"tool": "create_task", "args": {"title": "Smoke task", "priority": "low"}},
            self.db,
            0,
        )
        self.assertIn("created", result)
        self.assertEqual(self.db.query(Task).count(), 1)

    async def test_create_event_tool_uses_database_session(self) -> None:
        from backend.models.database import CalendarEvent
        from backend.services.tool_runner import execute_tool_call

        result = await execute_tool_call(
            {
                "tool": "create_event",
                "args": {
                    "title": "Smoke event",
                    "datetime": "2030-01-01T12:00:00",
                    "duration": "30",
                },
            },
            self.db,
            0,
        )
        self.assertIn("created", result)
        self.assertEqual(self.db.query(CalendarEvent).count(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
