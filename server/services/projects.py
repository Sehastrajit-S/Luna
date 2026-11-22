"""Your own code projects: read their files (read-only) and hand tasks to Claude Code.

Luna's file tools only reach data/workspace. Project folders you allow in
Settings → Coding → Project folders (`project_roots`, separated by ";") are
readable too, never writable. Each folder directly inside a root is a project,
and so is a root that is itself a repo.

A file named without a project ("the chat.py") is looked up in the projects
open in VS Code right now (window titles read "file - project - Visual Studio
Code"), then in every project.

Claude Code runs in a new, visible terminal window in the project folder, so
you watch it and answer its own approval prompts there. Luna only starts it,
after you confirm (the claude_code tool is risky), and logs it to the audit log.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from server.config import settings

MAX_READ_CHARS = 20_000
MAX_SCAN_FILES = 20_000
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".mypy_cache",
              ".pytest_cache", "site-packages", ".idea", ".vscode", "target", ".tox", "env"}
_VSCODE_TITLE = re.compile(r"^(?:● )?(?P<file>.+?) - (?P<project>.+?) - Visual Studio Code")
_PROJECT_MARKERS = (".git", "pyproject.toml", "package.json", "requirements.txt", "Cargo.toml", "go.mod")


class ProjectError(Exception):
    """kind: not_configured | not_found | ambiguous | outside | unavailable"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass
class Project:
    name: str
    path: Path


# ── Projects ─────────────────────────────────────────────────────────────────

def project_roots() -> list[Path]:
    raw = getattr(settings, "project_roots", "") or ""
    roots = []
    for part in re.split(r"[;\n]", raw):
        part = part.strip().strip('"')
        if part and Path(part).expanduser().is_dir():
            roots.append(Path(part).expanduser().resolve())
    return roots


def _is_project(path: Path) -> bool:
    return any((path / marker).exists() for marker in _PROJECT_MARKERS)


def list_projects() -> list[Project]:
    found: dict[str, Project] = {}
    for root in project_roots():
        if _is_project(root):
            found.setdefault(root.name.lower(), Project(root.name, root))
        try:
            children = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError:
            continue
        for child in children:
            found.setdefault(child.name.lower(), Project(child.name, child))
    return list(found.values())


def _norm(name: str) -> str:
    return re.sub(r"[\s_.-]+", "", name.lower())


def find_project(name: str) -> Project:
    if not project_roots():
        raise ProjectError("not_configured", _NOT_CONFIGURED)
    wanted = _norm(name)
    projects = list_projects()
    exact = [p for p in projects if _norm(p.name) == wanted]
    if exact:
        return exact[0]
    partial = [p for p in projects if wanted and (wanted in _norm(p.name) or _norm(p.name) in wanted)]
    if len(partial) == 1:
        return partial[0]
    if partial:
        raise ProjectError("ambiguous", f"'{name}' matches several projects: {', '.join(p.name for p in partial[:5])}. Which one?")
    names = ", ".join(p.name for p in projects[:12]) or "none"
    raise ProjectError("not_found", f"No project called '{name}' in your project folders. Projects: {names}.")


def open_in_vscode() -> list[tuple[str, str]]:
    """(file, project) for each VS Code window, front-most first."""
    try:
        from server.services.app_launcher import list_open_apps
        apps = list_open_apps()
    except Exception:
        return []
    pairs = []
    for app in apps:
        if app.get("app") != "VS Code":
            continue
        for title in app.get("windows", []):
            match = _VSCODE_TITLE.match(title)
            if match:
                pairs.append((match.group("file").strip(), match.group("project").strip()))
    return pairs


def _candidate_projects(project: str | None, filename: str | None = None) -> list[Project]:
    if project:
        return [find_project(project)]
    if not project_roots():
        raise ProjectError("not_configured", _NOT_CONFIGURED)
    ordered: list[Project] = []
    open_pairs = open_in_vscode()
    # A window showing that very file first, then any open project, then the rest.
    if filename:
        open_pairs.sort(key=lambda fp: Path(fp[0]).name.lower() != Path(filename).name.lower())
    for _file, name in open_pairs:
        try:
            p = find_project(name)
        except ProjectError:
            continue
        if p.path not in [o.path for o in ordered]:
            ordered.append(p)
    for p in list_projects():
        if p.path not in [o.path for o in ordered]:
            ordered.append(p)
    return ordered


# ── Files ────────────────────────────────────────────────────────────────────

def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _find_in(project: Project, filename: str) -> list[Path]:
    rel = filename.replace("\\", "/").lstrip("/")
    direct = (project.path / rel).resolve()
    if _inside(direct, project.path) and direct.is_file():
        return [direct]
    target = Path(rel).name.lower()
    hits, seen = [], 0
    for dirpath, dirnames, filenames in os.walk(project.path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        seen += len(filenames)
        for f in filenames:
            if f.lower() == target:
                full = Path(dirpath) / f
                if "/" not in rel or full.as_posix().lower().endswith(rel.lower()):
                    hits.append(full)
        if seen > MAX_SCAN_FILES:
            break
    hits.sort(key=lambda p: len(p.parts))
    return hits


def locate_file(filename: str, project: str | None = None) -> tuple[Project, Path]:
    for candidate in _candidate_projects(project, filename):
        hits = _find_in(candidate, filename)
        if hits:
            return candidate, hits[0]
    where = f"project '{project}'" if project else "your project folders"
    raise ProjectError("not_found", f"Couldn't find {filename} in {where}.")


def read_project_file(filename: str, project: str | None = None) -> dict:
    proj, path = locate_file(filename, project)
    if not any(_inside(path.resolve(), root) for root in project_roots()):
        raise ProjectError("outside", "That file is outside your project folders.")
    text = path.read_text(encoding="utf-8", errors="replace")
    return {
        "project": proj.name,
        "path": str(path),
        "content": text[:MAX_READ_CHARS],
        "truncated": len(text) > MAX_READ_CHARS,
    }


# ── Claude Code ──────────────────────────────────────────────────────────────

def claude_binary() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    for candidate in (Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude"):
        if candidate.exists():
            return str(candidate)
    return None


def resolve_project_for_task(project: str | None) -> Project:
    if project:
        return find_project(project)
    for _file, name in open_in_vscode():
        try:
            return find_project(name)
        except ProjectError:
            continue
    if not project_roots():
        raise ProjectError("not_configured", _NOT_CONFIGURED)
    raise ProjectError("not_found", "Which project should Claude Code work in? Name it, or open it in VS Code.")


def _terminal_command(claude: str, folder: Path, task: str) -> list[str]:
    """A command that opens a new visible terminal in `folder` running Claude Code with `task`."""
    system = platform.system()
    if system == "Windows":
        wt = shutil.which("wt")
        if wt:
            # wt splits its command line on ";" (new tab); "\;" keeps it in the task.
            return [wt, "-w", "new", "-d", str(folder), "--title", f"Claude Code · {folder.name}",
                    claude, task.replace(";", "\\;")]
        return ["cmd.exe", "/c", "start", f"Claude Code - {folder.name}", "/D", str(folder), claude, task]
    if system == "Darwin":
        quoted = task.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "Terminal" to do script "cd {_sh(folder)} && {_sh(claude)} {_sh(quoted)}"'
        return ["osascript", "-e", script, "-e", 'tell application "Terminal" to activate']
    for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
        if shutil.which(term):
            if term == "gnome-terminal":
                return [term, f"--working-directory={folder}", "--", claude, task]
            return [term, "-e", f"cd {_sh(folder)} && {_sh(claude)} {_sh(task)}"]
    raise ProjectError("unavailable", "No terminal app found to open Claude Code in.")


def _sh(value) -> str:
    return "'" + str(value).replace("'", "'\\''") + "'"


CLAUDE_PROCESS_NAMES = {"claude.exe", "claude"}
SETTLE_SECONDS = 5.0   # let Claude Code draw its screen before the screenshot


def open_claude_code(task: str, project: str | None = None, launcher=None, verify: bool = True,
                     sleep=time.sleep) -> dict:
    """Open Claude Code in a new terminal in the project, with `task` as its first prompt,
    then check it really started (process, window, screenshot)."""
    launcher = launcher or subprocess.Popen   # looked up per call, so tests can stub it
    task = " ".join((task or "").split())
    if not task:
        raise ProjectError("not_found", "What should Claude Code do?")
    claude = claude_binary()
    if not claude:
        raise ProjectError("unavailable", "Claude Code isn't installed on this computer (no `claude` command).")
    proj = resolve_project_for_task(project)
    command = _terminal_command(claude, proj.path, task[:4000])
    started = time.time()
    launcher(command, cwd=str(proj.path), close_fds=True,
             creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    result = {"project": proj.name, "path": str(proj.path), "task": task}
    if verify:
        result["evidence"] = verify_claude_started(proj, task, started, sleep=sleep)
    return result


def verify_claude_started(proj: Project, task: str, since: float, sleep=time.sleep):
    """Evidence that the Claude Code just launched is running: its process, its window, a screenshot."""
    from server.services import verification as V

    evidence = V.Evidence()
    marker = task.split(";")[0][:40]   # part of its command line
    proc = V.wait_for_process(CLAUDE_PROCESS_NAMES, since=since, cmd_contains=marker, sleep=sleep)
    if proc is None:
        return evidence
    evidence.process = V._proc_info(proc)
    sleep(SETTLE_SECONDS)
    if not proc.is_running():
        evidence.notes.append("Claude Code exited right after starting")
        evidence.process = None
        return evidence
    evidence.window = V.window_for(proc, prefer=("claude", proj.name))
    return V.screenshot_evidence(evidence, f"claude-{proj.name}")


def check_claude_code(project: str | None = None) -> dict:
    """Is Claude Code running in the project? With a fresh screenshot and its on-screen text."""
    from server.services import verification as V

    proj = resolve_project_for_task(project)
    running = V.find_processes(CLAUDE_PROCESS_NAMES, cwd=proj.path)
    evidence = V.Evidence()
    if running:
        proc = running[0]
        evidence.process = V._proc_info(proc)
        evidence.window = V.window_for(proc, prefer=("claude", proj.name))
        V.screenshot_evidence(evidence, f"claude-{proj.name}")
        if len(running) > 1:
            evidence.notes.append(f"{len(running)} Claude Code sessions are running there; showing the newest")
    return {"project": proj.name, "path": str(proj.path), "running": bool(running), "evidence": evidence}


_NOT_CONFIGURED = ("Luna can only read files in its own workspace (data/workspace). To let it read your code "
                   "projects, add their folder in Settings → Coding → Project folders (e.g. E:\\Projects).")
