from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.tools import _bootstrap  # noqa: F401


class AgentSkillToolTests(unittest.TestCase):
    def test_list_skills_is_readable(self) -> None:
        from backend.services.skill_manager import list_skills

        skills = list_skills()
        self.assertIsInstance(skills, list)

    def test_agent_task_create_round_trip(self) -> None:
        from backend.services.agent_tasks import TASKS_PATH, create_agent_task

        before = TASKS_PATH.read_text(encoding="utf-8") if TASKS_PATH.exists() else None
        try:
            task = create_agent_task("Smoke test agent task")
            self.assertIn("id", task)
            self.assertEqual(task["description"], "Smoke test agent task")
        finally:
            if before is None:
                if TASKS_PATH.exists():
                    TASKS_PATH.unlink()
            else:
                Path(TASKS_PATH).write_text(before, encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
