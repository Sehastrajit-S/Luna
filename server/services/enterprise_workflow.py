"""End-to-end enterprise bugfix workflow orchestration."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from server.config import settings
from server.services import github, jira, slack
from server.services.audit_log import record_audit
from server.services.coding_agent import stream_coding_agent


@dataclass
class WorkflowStep:
    name: str
    status: str
    detail: str = ""
    data: Any = None

    def as_dict(self) -> dict[str, Any]:
        result = {"name": self.name, "status": self.status, "detail": self.detail}
        if self.data is not None:
            result["data"] = self.data
        return result


@dataclass
class EnterpriseBugfixResult:
    ok: bool
    summary: str
    steps: list[WorkflowStep] = field(default_factory=list)
    pr: dict[str, Any] | None = None
    changed_files: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "steps": [s.as_dict() for s in self.steps],
            "pr": self.pr,
            "changed_files": self.changed_files,
        }


async def run_enterprise_bugfix_workflow(args: dict[str, Any]) -> EnterpriseBugfixResult:
    """
    Gather cross-tool context, run Luna's coding agent, verify, and open a PR.

    Expected args:
      bug_query, repo?, jira_key?, pr_number?, slack_query?, slack_channel?,
      since_days?, test_command?, base_branch?, branch_name?, create_pr?,
      draft?, allow_existing_changes?
    """
    bug_query = str(args.get("bug_query") or args.get("query") or "").strip()
    if not bug_query:
        return EnterpriseBugfixResult(False, "bug_query is required")

    workspace = Path(args.get("workspace_root") or settings.enterprise_workflow_workspace_root).resolve()
    repo = str(args.get("repo") or settings.github_default_repo or "").strip()
    base_branch = str(args.get("base_branch") or settings.enterprise_workflow_base_branch or "main").strip()
    test_command = str(args.get("test_command") or settings.enterprise_workflow_test_command).strip()
    create_pr = bool(args.get("create_pr", True))
    draft = bool(args.get("draft", True))
    allow_existing_changes = bool(args.get("allow_existing_changes", False))

    result = EnterpriseBugfixResult(ok=False, summary="")
    record_audit("enterprise_bugfix_workflow", args=_redacted_args(args), status="started")

    if not workspace.exists():
        result.summary = f"Workspace does not exist: {workspace}"
        return result

    before_status = _git_status(workspace)
    if before_status and not allow_existing_changes:
        result.steps.append(WorkflowStep("preflight", "blocked", "Repository has existing local changes.", before_status))
        result.summary = "Blocked before making changes because the repository is not clean."
        return result
    result.steps.append(WorkflowStep("preflight", "ok", f"Workspace: {workspace}"))

    if not repo:
        repo = _infer_github_repo(workspace)
    if not repo:
        result.steps.append(WorkflowStep("github_repo", "skipped", "No repo provided and origin remote is not a GitHub repo."))
    else:
        result.steps.append(WorkflowStep("github_repo", "ok", repo))

    context = await _collect_context(args, bug_query, repo)
    result.steps.extend(context["steps"])

    branch = str(args.get("branch_name") or _branch_name(bug_query)).strip()
    branch = _unique_branch_name(workspace, branch)
    checkout = _run_git(workspace, ["checkout", "-b", branch])
    if checkout.returncode != 0:
        result.steps.append(WorkflowStep("branch", "failed", checkout.stderr.strip() or checkout.stdout.strip()))
        result.summary = "Could not create a feature branch."
        return result
    result.steps.append(WorkflowStep("branch", "ok", branch))

    coding_summary = await _run_coding_agent(workspace, bug_query, context["text"])
    result.steps.append(coding_summary)

    changed = _changed_files_since(workspace, before_status)
    result.changed_files = changed
    if not changed:
        result.summary = "The coding agent completed but produced no file changes."
        result.steps.append(WorkflowStep("changes", "blocked", "No changed files detected."))
        return result
    result.steps.append(WorkflowStep("changes", "ok", f"{len(changed)} changed file(s)", changed))

    if test_command:
        test_step = await _run_test_command(workspace, test_command)
        result.steps.append(test_step)
        if test_step.status != "ok":
            result.summary = "Changes were made, but tests failed. PR creation was skipped."
            return result
    else:
        result.steps.append(WorkflowStep("tests", "skipped", "No test command configured."))

    commit = _commit_changes(workspace, changed, bug_query)
    result.steps.append(commit)
    if commit.status != "ok":
        result.summary = "Changes were made and tested, but commit failed."
        return result

    if create_pr and repo:
        push = _run_git(workspace, ["push", "-u", "origin", branch])
        if push.returncode != 0:
            result.steps.append(WorkflowStep("push", "failed", push.stderr.strip() or push.stdout.strip()))
            result.summary = "Commit succeeded, but push failed. PR creation was skipped."
            return result
        result.steps.append(WorkflowStep("push", "ok", branch))

        pr_body = _build_pr_body(bug_query, context["text"], changed, test_command)
        try:
            pr = await github.create_pull_request(
                repo,
                title=f"Fix: {bug_query[:80]}",
                head=branch,
                base=base_branch,
                body=pr_body,
                draft=draft,
            )
            result.pr = pr
            result.steps.append(WorkflowStep("pull_request", "ok", pr.get("url", ""), pr))
        except Exception as exc:
            result.steps.append(WorkflowStep("pull_request", "failed", str(exc)))
            result.summary = "Commit and push succeeded, but GitHub PR creation failed."
            return result
    else:
        result.steps.append(WorkflowStep("pull_request", "skipped", "create_pr=false or repo unavailable."))

    result.ok = True
    result.summary = "Enterprise bugfix workflow completed."
    record_audit("enterprise_bugfix_workflow", args=_redacted_args(args), result=json.dumps(result.as_dict())[:1000], status="ok")
    return result


async def _collect_context(args: dict[str, Any], bug_query: str, repo: str) -> dict[str, Any]:
    steps: list[WorkflowStep] = []
    context_parts: list[str] = []
    since_days = int(args.get("since_days") or 1)
    since = datetime.now(timezone.utc) - timedelta(days=max(1, since_days))

    jira_key = str(args.get("jira_key") or "").strip()
    if jira_key:
        try:
            issue = await jira.get_issue(jira_key)
            steps.append(WorkflowStep("jira_issue", "ok", jira_key, issue))
            context_parts.append(f"Jira issue:\n{json.dumps(issue, indent=2)}")
        except Exception as exc:
            steps.append(WorkflowStep("jira_issue", "failed", str(exc)))
    elif jira.is_configured():
        jql = f'text ~ "{bug_query}" AND updated >= -{since_days}d ORDER BY updated DESC'
        try:
            issues = await jira.search_issues(jql, max_results=5)
            steps.append(WorkflowStep("jira_search", "ok", jql, issues))
            context_parts.append(f"Jira search results:\n{json.dumps(issues, indent=2)}")
        except Exception as exc:
            steps.append(WorkflowStep("jira_search", "failed", str(exc)))
    else:
        steps.append(WorkflowStep("jira_search", "skipped", "Jira credentials are not configured."))

    pr_number = args.get("pr_number")
    if repo and pr_number:
        try:
            pr = await github.get_pr(repo, int(pr_number))
            steps.append(WorkflowStep("github_pr", "ok", str(pr_number), pr))
            context_parts.append(f"Related GitHub PR:\n{json.dumps(pr, indent=2)}")
        except Exception as exc:
            steps.append(WorkflowStep("github_pr", "failed", str(exc)))
    elif repo:
        try:
            prs = await github.list_prs(repo, state="open", limit=10)
            issues = await github.list_issues(repo, state="open", limit=10)
            steps.append(WorkflowStep("github_context", "ok", "Open PRs and issues fetched.", {"prs": prs, "issues": issues}))
            context_parts.append(f"GitHub context:\n{json.dumps({'prs': prs, 'issues': issues}, indent=2)}")
        except Exception as exc:
            steps.append(WorkflowStep("github_context", "failed", str(exc)))

    slack_query = str(args.get("slack_query") or bug_query).strip()
    slack_channel = str(args.get("slack_channel") or settings.slack_default_channel or "").strip()
    if slack.is_configured():
        try:
            if slack_channel:
                messages = await slack.channel_history(slack_channel, oldest=since.timestamp(), limit=30)
                steps.append(WorkflowStep("slack_history", "ok", slack_channel, messages))
            else:
                messages = await slack.search_messages(f'{slack_query} after:{since.date().isoformat()}', count=10)
                steps.append(WorkflowStep("slack_search", "ok", slack_query, messages))
            context_parts.append(f"Slack context:\n{json.dumps(messages, indent=2)}")
        except Exception as exc:
            steps.append(WorkflowStep("slack_context", "failed", str(exc)))
    else:
        steps.append(WorkflowStep("slack_context", "skipped", "Slack token is not configured."))

    return {"steps": steps, "text": "\n\n".join(context_parts)}


async def _run_coding_agent(workspace: Path, bug_query: str, context: str) -> WorkflowStep:
    prompt = (
        "Fix this bug in the current repository.\n\n"
        f"Bug request: {bug_query}\n\n"
        f"Cross-system context:\n{context or '(no external context available)'}\n\n"
        "Use file tools to inspect and edit the code. Do not run shell commands; "
        "the enterprise workflow will run tests after your edits."
    )
    messages = [{"role": "user", "content": prompt}]
    counts = {"tool_calls": 0, "tool_results": 0, "errors": []}
    visible: list[str] = []

    async for event in stream_coding_agent(messages, auto_confirm_shell=False, workspace_root=workspace):
        etype = event.get("type")
        if etype == "tool_call":
            counts["tool_calls"] += 1
        elif etype == "tool_result":
            counts["tool_results"] += 1
        elif etype == "error":
            counts["errors"].append(event.get("message", "unknown error"))
        elif etype == "token" and len("".join(visible)) < 1000:
            visible.append(event.get("content", ""))

    if counts["errors"]:
        return WorkflowStep("coding_agent", "failed", "; ".join(counts["errors"]), counts)
    return WorkflowStep(
        "coding_agent",
        "ok",
        f"{counts['tool_calls']} tool call(s), {counts['tool_results']} result(s)",
        {"assistant_excerpt": "".join(visible).strip()[:1000], **counts},
    )


async def _run_test_command(workspace: Path, command: str) -> WorkflowStep:
    env = os.environ.copy()
    repo_root = str(workspace.resolve())
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = repo_root if not existing else f"{repo_root}{os.pathsep}{existing}"

    proc = await asyncio.to_thread(
        subprocess.run,
        command,
        shell=True,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    output = "\n".join(p for p in [proc.stdout.strip(), proc.stderr.strip()] if p)
    status = "ok" if proc.returncode == 0 else "failed"
    return WorkflowStep("tests", status, f"exit code {proc.returncode}", output[-4000:])


def _commit_changes(workspace: Path, changed_files: list[str], bug_query: str) -> WorkflowStep:
    if not changed_files:
        return WorkflowStep("commit", "skipped", "No files changed.")
    add = _run_git(workspace, ["add", "--", *changed_files])
    if add.returncode != 0:
        return WorkflowStep("commit", "failed", add.stderr.strip() or add.stdout.strip())
    msg = f"fix: {bug_query[:72]}"
    commit = _run_git(workspace, ["commit", "-m", msg])
    if commit.returncode != 0:
        return WorkflowStep("commit", "failed", commit.stderr.strip() or commit.stdout.strip())
    return WorkflowStep("commit", "ok", msg)


def _git_status(workspace: Path) -> list[str]:
    proc = _run_git(workspace, ["status", "--porcelain"])
    if proc.returncode != 0:
        return [proc.stderr.strip() or proc.stdout.strip()]
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _changed_files_since(workspace: Path, before_status: list[str]) -> list[str]:
    before = {_status_path(line) for line in before_status}
    current = _git_status(workspace)
    changed = []
    for line in current:
        path = _status_path(line)
        if path and path not in before:
            changed.append(path)
    return sorted(set(changed))


def _status_path(line: str) -> str:
    raw = line[3:] if len(line) > 3 else line
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1]
    return raw.strip().strip('"')


def _run_git(workspace: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=120,
    )


def _infer_github_repo(workspace: Path) -> str:
    proc = _run_git(workspace, ["remote", "get-url", "origin"])
    if proc.returncode != 0:
        return ""
    remote = proc.stdout.strip()
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
    if not match:
        return ""
    return f"{match.group('owner')}/{match.group('repo')}"


def _branch_name(bug_query: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", bug_query.lower()).strip("-")[:48]
    return f"luna-fix-{slug or 'bug'}"


def _unique_branch_name(workspace: Path, base: str) -> str:
    candidate = base
    for i in range(2, 50):
        exists = _run_git(workspace, ["rev-parse", "--verify", candidate])
        if exists.returncode != 0:
            return candidate
        candidate = f"{base}-{i}"
    return f"{base}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def _build_pr_body(bug_query: str, context: str, changed: list[str], test_command: str) -> str:
    return (
        f"## Summary\n\nAutomated Luna enterprise bugfix workflow for: {bug_query}\n\n"
        f"## Changed Files\n\n" + "\n".join(f"- `{p}`" for p in changed) + "\n\n"
        f"## Verification\n\n- `{test_command}`\n\n"
        f"## Context Used\n\n```text\n{context[:4000] or 'No external context available.'}\n```\n"
    )


def _redacted_args(args: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(args)
    for key in list(redacted):
        if any(secret in key.lower() for secret in ("token", "secret", "password", "key")):
            redacted[key] = "***"
    return redacted
