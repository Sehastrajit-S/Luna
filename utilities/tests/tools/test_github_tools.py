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

        summary_result = {"repo": "owner/repo", "user": "alice", "found": True}
        with patch("backend.services.github.summarize_user_pr_update", new=AsyncMock(return_value=summary_result)):
            result = await execute_tool_call(
                {"tool": "github_summarize_user_pr", "args": {"repo": "owner/repo", "user": "alice"}},
                None,
                0,
            )
            self.assertIn('"user": "alice"', result)

        pr_result = {"number": 1, "url": "https://github.com/owner/repo/pull/1"}
        with patch("backend.services.github.create_pull_request", new=AsyncMock(return_value=pr_result)):
            result = await execute_tool_call(
                {
                    "tool": "github_create_pr",
                    "args": {
                        "repo": "owner/repo",
                        "title": "Fix bug",
                        "head": "fix-branch",
                        "base": "main",
                        "body": "Body",
                        "draft": True,
                    },
                },
                None,
                0,
            )
            self.assertIn('"number": 1', result)

    async def test_github_errors_are_concise(self) -> None:
        from backend.services.tool_runner import execute_tool_call
        from backend.services.tool_runner.verifier import verify_tool_result

        with patch("backend.services.github.list_prs", new=AsyncMock(side_effect=RuntimeError("GitHub token was rejected (401). Replace github_token."))):
            result = await execute_tool_call(
                {"tool": "github_list_prs", "args": {"repo": "owner/repo"}},
                None,
                0,
            )

        self.assertTrue(result.startswith("GitHub error:"))
        verified = await verify_tool_result("github_list_prs", {"repo": "owner/repo"}, result, "show prs")
        self.assertEqual(verified, result)

    def test_github_author_and_repo_extraction_is_generic(self) -> None:
        from backend.services.chat_pipeline.stage_dispatch import _extract_pr_author, _extract_repo

        self.assertEqual(_extract_pr_author("what did user gokul update in his PR"), "gokul")
        self.assertEqual(_extract_pr_author("what did alice change in her pull request"), "alice")
        self.assertEqual(_extract_repo("show PRs in Sehastrajit/Luna"), "Sehastrajit/Luna")


if __name__ == "__main__":
    unittest.main(verbosity=2)
