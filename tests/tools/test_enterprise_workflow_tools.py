from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from tests.tools import _bootstrap  # noqa: F401


class EnterpriseWorkflowToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_enterprise_workflow_requires_bug_query(self) -> None:
        from server.services.enterprise_workflow import run_enterprise_bugfix_workflow

        result = await run_enterprise_bugfix_workflow({})

        self.assertFalse(result.ok)
        self.assertIn("bug_query is required", result.summary)

    async def test_enterprise_workflow_blocks_dirty_repo_before_llm(self) -> None:
        from server.services.enterprise_workflow import run_enterprise_bugfix_workflow

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._git(root, "init")
            self._git(root, "config", "user.email", "test@example.com")
            self._git(root, "config", "user.name", "Test User")
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            self._git(root, "add", "README.md")
            self._git(root, "commit", "-m", "init")
            (root / "dirty.txt").write_text("dirty\n", encoding="utf-8")

            with patch("server.services.enterprise_workflow.stream_coding_agent", new=AsyncMock()):
                result = await run_enterprise_bugfix_workflow({
                    "bug_query": "login bug",
                    "workspace_root": str(root),
                })

        self.assertFalse(result.ok)
        self.assertEqual(result.steps[0].status, "blocked")

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        import subprocess

        proc = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
