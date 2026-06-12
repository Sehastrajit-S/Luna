"""GitHub REST API client for Luna tools."""
import httpx

from backend.config import settings

_BASE = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _auth_headers() -> dict:
    h = dict(_HEADERS)
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


async def list_repos(per_page: int = 30) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/user/repos",
            headers=_auth_headers(),
            params={"per_page": per_page, "sort": "updated", "affiliation": "owner,collaborator"},
        )
        r.raise_for_status()
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
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/repos/{repo}/issues",
            headers=_auth_headers(),
            params={"state": state, "per_page": limit, "sort": "updated"},
        )
        r.raise_for_status()
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
        r.raise_for_status()
        data = r.json()
        return {"number": data["number"], "title": data["title"], "url": data["html_url"]}


async def comment_on_issue(repo: str, number: int, body: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{_BASE}/repos/{repo}/issues/{number}/comments",
            headers=_auth_headers(),
            json={"body": body},
        )
        r.raise_for_status()
        return {"url": r.json()["html_url"]}


async def list_prs(repo: str, state: str = "open", limit: int = 20) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/repos/{repo}/pulls",
            headers=_auth_headers(),
            params={"state": state, "per_page": limit, "sort": "updated"},
        )
        r.raise_for_status()
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
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{_BASE}/repos/{repo}/pulls/{number}",
            headers=_auth_headers(),
        )
        r.raise_for_status()
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
        r.raise_for_status()
        pr = r.json()
        return {
            "number": pr["number"],
            "title": pr["title"],
            "draft": pr["draft"],
            "url": pr["html_url"],
            "head": pr["head"]["ref"],
            "base": pr["base"]["ref"],
        }
