"""Developer dashboard data: the local checkout + the GitHub repo.

Local git status works offline and without any token. GitHub data uses the
configured token; if that token is unusable (suspended account, expired, no
access) and the repository is public, it falls back to GitHub's anonymous API
so the dashboard still works — with the token problem reported alongside.
Responses are cached briefly to stay well inside GitHub's rate limits.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from server.config import BASE_DIR, settings
from server.services import github

logger = logging.getLogger(__name__)

CACHE_TTL_S = 180
_cache: dict[str, tuple[float, dict]] = {}
_API = "https://api.github.com"
_TOKEN_FALLBACK_KINDS = {"suspended", "invalid_token", "forbidden", "not_found"}


# ── Local checkout ───────────────────────────────────────────────────────────

def _git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL, timeout=10).strip()


def local_status(path: Path = BASE_DIR) -> dict:
    try:
        branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=path)
    except (OSError, subprocess.SubprocessError):
        return {"available": False}
    porcelain = _git("status", "--porcelain", cwd=path).splitlines()
    staged = sum(1 for l in porcelain if l[:1] not in (" ", "?"))
    untracked = sum(1 for l in porcelain if l.startswith("??"))
    ahead = behind = None
    try:
        counts = _git("rev-list", "--left-right", "--count", "HEAD...@{upstream}", cwd=path).split()
        ahead, behind = int(counts[0]), int(counts[1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass    # no upstream configured
    last = _git("log", "-1", "--format=%h%x1f%s%x1f%an%x1f%cI", cwd=path).split("\x1f")
    return {
        "available": True,
        "path": str(path),
        "branch": branch,
        "changed": len(porcelain) - untracked,
        "staged": staged,
        "untracked": untracked,
        "ahead": ahead,
        "behind": behind,
        "last_commit": {"sha": last[0], "message": last[1], "author": last[2], "date": last[3]} if len(last) == 4 else None,
    }


# ── GitHub ───────────────────────────────────────────────────────────────────

class _Client:
    """Token first; public API if the token itself is the problem."""

    def __init__(self, http: httpx.AsyncClient, repo: str):
        self.http, self.repo = http, repo
        self.token_error: github.GitHubError | None = None
        self.anonymous = not settings.github_token

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if settings.github_token and not self.anonymous:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        return headers

    async def get(self, path: str, **params):
        r = await self.http.get(f"{_API}{path}", headers=self._headers(), params=params)
        error = github.github_error(r, self.repo)
        if error and not self.anonymous and error.kind in _TOKEN_FALLBACK_KINDS:
            self.token_error, self.anonymous = error, True
            r = await self.http.get(f"{_API}{path}", headers=self._headers(), params=params)
            error = github.github_error(r, self.repo)
        if error:
            raise error
        return r.json()


def _daily_counts(commits: list[dict], days: int) -> list[int]:
    today = datetime.now().date()
    counts = Counter()
    for c in commits:
        stamp = (c.get("commit", {}).get("author") or {}).get("date")
        if stamp:
            counts[datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().date()] += 1
    return [counts.get(today - timedelta(days=offset), 0) for offset in range(days - 1, -1, -1)]


async def github_summary(repo: str) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    async with httpx.AsyncClient(timeout=12) as http:
        client = _Client(http, repo)
        info = await client.get(f"/repos/{repo}")       # first call settles token vs. anonymous
        commits, latest, pulls, issues, runs = await asyncio.gather(
            client.get(f"/repos/{repo}/commits", since=since, per_page=100),
            client.get(f"/repos/{repo}/commits", per_page=6),       # newest, however old
            client.get(f"/repos/{repo}/pulls", state="open", per_page=20),
            client.get("/search/issues", q=f"repo:{repo} is:issue is:open", per_page=1),
            client.get(f"/repos/{repo}/actions/runs", per_page=1),
            return_exceptions=True,
        )
        comments = []
        if isinstance(pulls, list):
            for pr in pulls[:4]:
                try:
                    for c in await client.get(f"/repos/{repo}/pulls/{pr['number']}/comments", per_page=5):
                        comments.append({"pr": pr["number"], "author": c["user"]["login"],
                                         "body": " ".join(c.get("body", "").split())[:160], "url": c["html_url"]})
                except github.GitHubError:
                    break
    ok = lambda v: not isinstance(v, BaseException)
    run = runs["workflow_runs"][0] if ok(runs) and runs.get("workflow_runs") else None
    return {
        "repo": repo,
        "url": info.get("html_url"),
        "private": info.get("private"),
        "default_branch": info.get("default_branch"),
        "stars": info.get("stargazers_count"),
        "source": "public" if client.anonymous else "token",
        "token_problem": str(client.token_error) if client.token_error else None,
        "commits_30d": len(commits) if ok(commits) else None,
        "commit_days": _daily_counts(commits, 30) if ok(commits) else [],
        "recent_commits": [
            {"sha": c["sha"][:7], "message": c["commit"]["message"].splitlines()[0][:100],
             "author": (c.get("author") or {}).get("login") or c["commit"]["author"]["name"],
             "date": c["commit"]["author"]["date"], "url": c["html_url"]}
            for c in (latest if ok(latest) else [])
        ],
        "open_prs": [
            {"number": p["number"], "title": p["title"], "author": p["user"]["login"], "draft": p.get("draft"),
             "updated": p["updated_at"], "url": p["html_url"]}
            for p in (pulls if ok(pulls) else [])
        ],
        "open_issues": issues.get("total_count") if ok(issues) else None,
        "ci": {"name": run["name"], "status": run["status"], "conclusion": run["conclusion"],
               "branch": run["head_branch"], "url": run["html_url"], "updated": run["updated_at"]} if run else None,
        "review_comments": comments[:8],
    }


async def dashboard(force: bool = False) -> dict:
    repo = github.default_repo()
    key = repo or "_local"
    cached = _cache.get(key)
    if cached and not force and time.monotonic() - cached[0] < CACHE_TTL_S:
        return cached[1]
    local = await asyncio.to_thread(local_status)
    remote, error = None, None
    if repo:
        try:
            remote = await github_summary(repo)
        except github.GitHubError as e:
            error = {"kind": e.kind, "message": str(e)}
        except httpx.HTTPError as e:
            error = {"kind": "offline", "message": f"Couldn't reach GitHub ({type(e).__name__})."}
    else:
        error = {"kind": "no_repo", "message": "No GitHub repository configured — set one in Settings › Integrations."}
    data = {"local": local, "github": remote, "error": error, "fetched_at": datetime.now(timezone.utc).isoformat()}
    if remote or (error and error["kind"] != "rate_limited"):
        _cache[key] = (time.monotonic(), data)
    return data
