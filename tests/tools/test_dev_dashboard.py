import asyncio
import unittest
from unittest import mock

import httpx


def _resp(status, message="", headers=None):
    return httpx.Response(status, json={"message": message}, headers=headers or {},
                          request=httpx.Request("GET", "https://api.github.com/x"))


class GitHubErrorTests(unittest.TestCase):
    def test_errors_are_classified_from_githubs_message(self) -> None:
        from server.services.github import github_error

        cases = {
            "suspended": _resp(403, "Sorry. Your account was suspended"),
            "invalid_token": _resp(401, "Bad credentials"),
            "rate_limited": _resp(403, "API rate limit exceeded", {"x-ratelimit-remaining": "0"}),
            "forbidden": _resp(403, "Resource not accessible by personal access token"),
            "not_found": _resp(404, "Not Found"),
            "upstream": _resp(502, "Bad gateway"),
        }
        for kind, response in cases.items():
            with self.subTest(kind=kind):
                self.assertEqual(github_error(response, "o/r").kind, kind)
        self.assertIsNone(github_error(httpx.Response(200, request=httpx.Request("GET", "https://x"))))
        self.assertIn("suspended", str(github_error(cases["suspended"])))
        self.assertIn("Settings", str(github_error(cases["suspended"])))


class DevDashboardTests(unittest.TestCase):
    def test_unusable_token_falls_back_to_public_data_and_says_why(self) -> None:
        from server.services import dev_dashboard

        def handler(request: httpx.Request) -> httpx.Response:
            if request.headers.get("authorization"):
                return httpx.Response(403, json={"message": "Sorry. Your account was suspended"})
            path = request.url.path
            if path == "/repos/o/r":
                return httpx.Response(200, json={"html_url": "https://github.com/o/r", "private": False})
            if path == "/repos/o/r/commits":
                return httpx.Response(200, json=[{"sha": "abc1234def", "html_url": "https://github.com/o/r/commit/abc",
                                                  "author": {"login": "dev"},
                                                  "commit": {"message": "Fix bug\n\nbody", "author": {"name": "Dev", "date": "2026-09-20T10:00:00Z"}}}])
            if path == "/repos/o/r/pulls":
                return httpx.Response(200, json=[{"number": 7, "title": "Add feature", "user": {"login": "dev"},
                                                  "updated_at": "2026-09-22T10:00:00Z", "html_url": "https://github.com/o/r/pull/7"}])
            if path == "/repos/o/r/pulls/7/comments":
                return httpx.Response(200, json=[{"user": {"login": "rev"}, "body": "Please add tests", "html_url": "https://github.com/o/r/pull/7#c"}])
            if path == "/search/issues":
                return httpx.Response(200, json={"total_count": 3})
            if path == "/repos/o/r/actions/runs":
                return httpx.Response(200, json={"workflow_runs": [{"name": "CI", "status": "completed", "conclusion": "success",
                                                                    "head_branch": "main", "html_url": "https://x", "updated_at": "2026-09-22T10:00:00Z"}]})
            return httpx.Response(404, json={"message": "Not Found"})

        real = httpx.AsyncClient
        with mock.patch.object(dev_dashboard.settings, "github_token", "github_pat_suspended"), \
             mock.patch("httpx.AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw)):
            data = asyncio.run(dev_dashboard.github_summary("o/r"))
        self.assertEqual(data["source"], "public")
        self.assertIn("suspended", data["token_problem"])
        self.assertEqual(data["recent_commits"][0]["message"], "Fix bug")
        self.assertEqual(len(data["open_prs"]), 1)
        self.assertEqual(data["open_issues"], 3)
        self.assertEqual(data["ci"]["conclusion"], "success")
        self.assertEqual(data["review_comments"][0]["body"], "Please add tests")
        self.assertEqual(len(data["commit_days"]), 30)

    def test_rate_limited_results_are_not_cached(self) -> None:
        from server.services import dev_dashboard
        from server.services.github import GitHubError

        dev_dashboard._cache.clear()
        with mock.patch.object(dev_dashboard.github, "default_repo", return_value="o/r"), \
             mock.patch.object(dev_dashboard, "local_status", return_value={"available": False}), \
             mock.patch.object(dev_dashboard, "github_summary",
                               new=mock.AsyncMock(side_effect=GitHubError("rate_limited", "slow down"))):
            data = asyncio.run(dev_dashboard.dashboard())
        self.assertEqual(data["error"]["kind"], "rate_limited")
        self.assertNotIn("o/r", dev_dashboard._cache)

    def test_local_status_reads_this_checkout(self) -> None:
        from server.services.dev_dashboard import local_status

        status = local_status()
        self.assertTrue(status["available"])
        self.assertTrue(status["branch"])
        self.assertIsInstance(status["changed"], int)
        self.assertTrue(status["last_commit"]["sha"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
