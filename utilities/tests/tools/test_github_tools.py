from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from tests.tools import _bootstrap  # noqa: F401


class GitHubToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_github_safe_read_tools(self) -> None:
        from backend.services.tool_runner import execute_tool_call

        with patch("backend.services.github.list_repos", new=AsyncMock(return_value=[])):
            result = await execute_tool_call({"tool": "github_list_repos", "args": {}}, None, 0)
            self.assertEqual(result, "[]")

        with patch("backend.services.github.list_issues", new=AsyncMock(return_value=[])):
            result = await execute_tool_call(
                {"tool": "github_list_issues", "args": {"repo": "owner/repo"}},
                None,
                0,
            )
            self.assertEqual(result, "[]")

        with patch("backend.services.github.list_prs", new=AsyncMock(return_value=[])):
            result = await execute_tool_call(
                {"tool": "github_list_prs", "args": {"repo": "owner/repo"}},
                None,
                0,
            )
            self.assertEqual(result, "[]")


if __name__ == "__main__":
    unittest.main(verbosity=2)
