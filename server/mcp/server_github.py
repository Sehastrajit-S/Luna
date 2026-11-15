"""Luna MCP server — GitHub tools.

Exposes: list_repos, list_issues, create_issue, list_prs, get_pr, add_comment, create_pr

Requires: github_token in .env

Run:
    python -m server.mcp.server_github
"""
import json
from mcp.server.fastmcp import FastMCP
from server.services import github as gh

mcp = FastMCP("luna-github")


@mcp.tool()
async def list_repos() -> str:
    """List your GitHub repositories sorted by last updated."""
    repos = await gh.list_repos()
    return json.dumps(repos, indent=2)


@mcp.tool()
async def list_issues(repo: str, state: str = "open") -> str:
    """List issues in a GitHub repository.

    Args:
        repo: Full repo name e.g. 'owner/repo'
        state: 'open', 'closed', or 'all'
    """
    issues = await gh.list_issues(repo, state=state)
    return json.dumps(issues, indent=2)


@mcp.tool()
async def create_issue(repo: str, title: str, body: str = "") -> str:
    """Create a new GitHub issue.

    Args:
        repo: Full repo name e.g. 'owner/repo'
        title: Issue title
        body: Issue body (markdown)
    """
    result = await gh.create_issue(repo, title, body)
    return json.dumps(result, indent=2)


@mcp.tool()
async def list_prs(repo: str, state: str = "open") -> str:
    """List pull requests in a GitHub repository.

    Args:
        repo: Full repo name e.g. 'owner/repo'
        state: 'open', 'closed', or 'all'
    """
    prs = await gh.list_prs(repo, state=state)
    return json.dumps(prs, indent=2)


@mcp.tool()
async def get_pr(repo: str, number: int) -> str:
    """Get details about a specific pull request.

    Args:
        repo: Full repo name e.g. 'owner/repo'
        number: PR number
    """
    pr = await gh.get_pr(repo, number)
    return json.dumps(pr, indent=2)


@mcp.tool()
async def add_comment(repo: str, number: int, body: str) -> str:
    """Post a comment on a GitHub issue or pull request.

    Args:
        repo: Full repo name e.g. 'owner/repo'
        number: Issue or PR number
        body: Comment body (markdown)
    """
    result = await gh.comment_on_issue(repo, number, body)
    return json.dumps(result, indent=2)


@mcp.tool()
async def create_pr(repo: str, title: str, head: str, base: str = "main", body: str = "", draft: bool = True) -> str:
    """Open a GitHub pull request from an already-pushed branch.

    Args:
        repo: Full repo name e.g. 'owner/repo'
        title: Pull request title
        head: Source branch name
        base: Target branch name
        body: Pull request description
        draft: Whether to create a draft PR
    """
    result = await gh.create_pull_request(repo, title, head, base, body, draft)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
