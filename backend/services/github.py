"""GitHub REST API client for Luna tools."""
import re
import subprocess

import httpx

from backend.config import reload_settings, settings

_BASE = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _auth_headers() -> dict:
    reload_settings()
    h = dict(_HEADERS)
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def _raise_github_error(response: httpx.Response, repo: str = "") -> None:
    if response.status_code == 401:
        raise RuntimeError(
            "GitHub token was rejected (401). Replace github_token with a valid token, "
            "then run /connect_app github so Luna reloads it. Classic tokens need repo scope; "
            f"fine-grained tokens need access to {repo or 'the target repository'} with Pull requests read permission."
        )
    if response.status_code == 403:
        raise RuntimeError(
            "GitHub token is authenticated but not allowed for this request (403). "
            f"Grant access to {repo or 'the target repository'} and Pull requests read permission."
        )
    response.raise_for_status()


def default_repo() -> str:
    """Return configured GitHub repo or infer it from the local origin remote."""
    reload_settings()
    if settings.github_default_repo:
        return settings.github_default_repo
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=".",
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
    if not match:
        return ""
    return f"{match.group('owner')}/{match.group('repo')}"


async def list_repos(per_page: int = 30) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/user/repos",
            headers=_auth_headers(),
            params={"per_page": per_page, "sort": "updated", "affiliation": "owner,collaborator"},
        )
        _raise_github_error(r)
        return [
            {
                "name": repo["full_name"],
                "description": repo.get("description") or "",
                "stars": repo["stargazers_count"],
                "open_issues": repo["open_issues_count"],
                "url": repo["html_url"],
            }
            for repo in r.json()
        ]


async def list_issues(repo: str, state: str = "open", limit: int = 20) -> list[dict]:
    repo = repo or default_repo()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/repos/{repo}/issues",
            headers=_auth_headers(),
            params={"state": state, "per_page": limit, "sort": "updated"},
        )
        _raise_github_error(r, repo)
        return [
            {
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "user": i["user"]["login"],
                "labels": [lb["name"] for lb in i.get("labels", [])],
                "url": i["html_url"],
            }
            for i in r.json()
            if "pull_request" not in i  # exclude PRs from issues list
        ]


async def create_issue(repo: str, title: str, body: str = "", labels: list[str] | None = None) -> dict:
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{_BASE}/repos/{repo}/issues",
            headers=_auth_headers(),
            json=payload,
        )
        _raise_github_error(r, repo)
        data = r.json()
        return {"number": data["number"], "title": data["title"], "url": data["html_url"]}


async def comment_on_issue(repo: str, number: int, body: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{_BASE}/repos/{repo}/issues/{number}/comments",
            headers=_auth_headers(),
            json={"body": body},
        )
        _raise_github_error(r, repo)
        return {"url": r.json()["html_url"]}


async def list_prs(repo: str, state: str = "open", limit: int = 20) -> list[dict]:
    repo = repo or default_repo()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/repos/{repo}/pulls",
            headers=_auth_headers(),
            params={"state": state, "per_page": limit, "sort": "updated"},
        )
        _raise_github_error(r, repo)
        return [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "user": pr["user"]["login"],
                "draft": pr["draft"],
                "url": pr["html_url"],
            }
            for pr in r.json()
        ]


async def get_pr(repo: str, number: int) -> dict:
    repo = repo or default_repo()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/repos/{repo}/pulls/{number}",
            headers=_auth_headers(),
        )
        _raise_github_error(r, repo)
        pr = r.json()
        return {
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "user": pr["user"]["login"],
            "body": (pr.get("body") or "")[:500],
            "draft": pr["draft"],
            "mergeable": pr.get("mergeable"),
            "changed_files": pr["changed_files"],
            "additions": pr["additions"],
            "deletions": pr["deletions"],
            "url": pr["html_url"],
        }


async def list_pr_files(repo: str, number: int, limit: int = 100) -> list[dict]:
    repo = repo or default_repo()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/repos/{repo}/pulls/{number}/files",
            headers=_auth_headers(),
            params={"per_page": limit},
        )
        _raise_github_error(r, repo)
        return [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "changes": f["changes"],
                "patch": (f.get("patch") or "")[:500],
            }
            for f in r.json()
        ]


async def summarize_user_pr_update(repo: str, user: str, state: str = "all") -> dict:
    repo = repo or default_repo()
    if not repo:
        raise ValueError("GitHub repo is required. Set github_default_repo in .env or ask with owner/repo.")
    wanted = user.lower().lstrip("@")
    prs = await list_prs(repo, state=state, limit=50)
    matches = [pr for pr in prs if pr.get("user", "").lower() == wanted]
    if not matches:
        return {"repo": repo, "user": wanted, "found": False, "message": f"No PRs found for @{wanted} in {repo}."}
    pr = matches[0]
    detail = await get_pr(repo, int(pr["number"]))
    files = await list_pr_files(repo, int(pr["number"]))
    return {
        "repo": repo,
        "user": wanted,
        "found": True,
        "pr": detail,
        "files": files,
        "summary": {
            "title": detail["title"],
            "number": detail["number"],
            "changed_files": detail["changed_files"],
            "additions": detail["additions"],
            "deletions": detail["deletions"],
            "url": detail["url"],
        },
    }


async def create_pull_request(
    repo: str,
    title: str,
    head: str,
    base: str,
    body: str = "",
    draft: bool = True,
) -> dict:
    """Open a GitHub pull request from an existing pushed branch."""
    payload = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "draft": draft,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{_BASE}/repos/{repo}/pulls",
            headers=_auth_headers(),
            json=payload,
        )
        _raise_github_error(r, repo)
        pr = r.json()
        return {
            "number": pr["number"],
            "title": pr["title"],
            "draft": pr["draft"],
            "url": pr["html_url"],
            "head": pr["head"]["ref"],
            "base": pr["base"]["ref"],
        }
