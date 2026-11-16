"""Jira Cloud REST API client for Luna enterprise workflows."""
from __future__ import annotations

import base64
from typing import Any

import httpx

from server.config import reload_settings, settings


class JiraNotConfiguredError(RuntimeError):
    """Raised when Jira credentials are missing."""


def _base_url() -> str:
    reload_settings()
    return settings.jira_base_url.rstrip("/")


def _headers() -> dict[str, str]:
    if not (_base_url() and settings.jira_email and settings.jira_api_token):
        raise JiraNotConfiguredError(
            "Jira is not configured. Set jira_base_url, jira_email, and jira_api_token."
        )
    raw = f"{settings.jira_email}:{settings.jira_api_token}".encode("utf-8")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}",
    }


def is_configured() -> bool:
    return bool(_base_url() and settings.jira_email and settings.jira_api_token)


async def search_issues(jql: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search Jira issues using JQL."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{_base_url()}/rest/api/3/search",
            headers=_headers(),
            params={
                "jql": jql,
                "maxResults": max(1, min(max_results, 25)),
                "fields": "summary,status,assignee,updated,description",
            },
        )
        response.raise_for_status()
        data = response.json()
    return [_issue_summary(issue) for issue in data.get("issues", [])]


async def get_issue(issue_key: str) -> dict[str, Any]:
    """Return a Jira issue summary by key."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{_base_url()}/rest/api/3/issue/{issue_key}",
            headers=_headers(),
            params={"fields": "summary,status,assignee,updated,description,comment"},
        )
        response.raise_for_status()
        return _issue_summary(response.json(), include_comments=True)


def _issue_summary(issue: dict[str, Any], *, include_comments: bool = False) -> dict[str, Any]:
    fields = issue.get("fields", {}) or {}
    status = fields.get("status") or {}
    assignee = fields.get("assignee") or {}
    result = {
        "key": issue.get("key", ""),
        "summary": fields.get("summary", ""),
        "status": status.get("name", ""),
        "assignee": assignee.get("displayName", "") if assignee else "",
        "updated": fields.get("updated", ""),
        "url": f"{_base_url()}/browse/{issue.get('key', '')}" if _base_url() else "",
    }
    if include_comments:
        comments = ((fields.get("comment") or {}).get("comments") or [])[-5:]
        result["comments"] = [
            {
                "author": ((c.get("author") or {}).get("displayName") or ""),
                "created": c.get("created", ""),
                "body": _plain_text(c.get("body")),
            }
            for c in comments
        ]
    return result


def _plain_text(node: Any) -> str:
    """Extract readable text from Atlassian document-format content."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(_plain_text(item) for item in node).strip()
    if isinstance(node, dict):
        parts = []
        if node.get("text"):
            parts.append(str(node["text"]))
        if node.get("content"):
            parts.append(_plain_text(node["content"]))
        return " ".join(p for p in parts if p).strip()
    return ""
