"""
Installer — fetches skills from git URLs or local paths into the user skill dir.

Sources supported:
  - https://github.com/<user>/<repo>          (cloned via git)
  - https://github.com/<user>/<repo>.git
  - git@github.com:<user>/<repo>.git
  - file:///absolute/path/to/skill_folder    (local copy)
  - /absolute/path or C:\\path                (local copy, no scheme)

Each install:
  1. Resolves the source to a local working directory (clone or copy)
  2. Validates skill.json (manifest.py)
  3. Checks for permission warnings
  4. Moves the validated skill to data/workspace/skills/<id>/
  5. Writes a .marketplace.json sidecar with install metadata

Built-in skills (in server/skills/) are NEVER touched by this installer.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from server.config import BASE_DIR, DATA_DIR
from server.services.skill_marketplace.manifest import (
    ManifestError,
    SkillManifest,
    load_manifest,
)

logger = logging.getLogger(__name__)

# Skills installed via the marketplace go here. Built-in server/skills/ stays untouched.
USER_SKILLS_DIR = DATA_DIR / "workspace" / "skills"
BUILTIN_SKILLS_DIR = BASE_DIR / "server" / "skills"

GIT_URL_RE = re.compile(
    r"^(?:https?://|git@)(?:[\w.-]+[:/])[\w./-]+?(?:\.git)?/?$"
)
GITHUB_SHORT_RE = re.compile(r"^github:([\w.-]+/[\w.-]+)$")


class InstallError(Exception):
    """Raised when a skill cannot be installed."""


@dataclass
class InstallResult:
    """Outcome of an install_skill call."""

    skill_id: str
    name: str
    version: str
    path: str
    source: str
    permissions: list[str]
    dangerous_permissions: list[str]
    installed_at: str

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "source": self.source,
            "permissions": self.permissions,
            "dangerous_permissions": self.dangerous_permissions,
            "installed_at": self.installed_at,
        }


# ── Public API ────────────────────────────────────────────────────────────────


def install_skill(
    source: str,
    *,
    confirm_dangerous: bool = False,
    overwrite: bool = False,
) -> InstallResult:
    """
    Install a skill from a git URL or a local path.

    Args:
        source: git URL (https/ssh/short github:owner/repo) or a local folder path.
        confirm_dangerous: if the manifest declares dangerous permissions
            (shell, filesystem, browser), the install fails unless this is True.
            UI/CLI must show the user the list and get explicit consent first.
        overwrite: if a skill with the same id is already installed, reinstall.

    Returns:
        InstallResult with skill metadata and final install path.

    Raises:
        InstallError on any failure (clone failed, validation failed, etc.).
    """
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    source = source.strip()
    if not source:
        raise InstallError("Source is required")

    logger.info("Installing skill from source: %s", source)

    with tempfile.TemporaryDirectory(prefix="luna-skill-") as tmp:
        staging = Path(tmp) / "skill"
        _fetch_source(source, staging)

        # Resolve nested skill folder (some repos have skill at root, others in subdir)
        skill_root = _find_skill_root(staging)
        if skill_root is None:
            raise InstallError(
                "No skill.json found in the source. "
                "The skill folder must contain a skill.json at its root."
            )

        # Validate manifest
        try:
            manifest = load_manifest(skill_root)
        except ManifestError as e:
            raise InstallError(f"Manifest validation failed: {e}") from e

        # Built-in collision check
        builtin = BUILTIN_SKILLS_DIR / manifest.id
        if builtin.exists():
            raise InstallError(
                f"Skill id '{manifest.id}' is reserved by a built-in skill. "
                "Rename your skill before installing."
            )

        # Permission gate
        dangerous = manifest.has_dangerous_permissions()
        if dangerous and not confirm_dangerous:
            raise InstallError(
                f"Skill requires dangerous permissions: {dangerous}. "
                "Re-run with confirm_dangerous=True after explicit user consent."
            )

        # Existing-skill collision check
        target = USER_SKILLS_DIR / manifest.id
        if target.exists():
            if not overwrite:
                raise InstallError(
                    f"Skill '{manifest.id}' is already installed. "
                    "Pass overwrite=True to reinstall."
                )
            shutil.rmtree(target)

        # Move into place
        shutil.copytree(skill_root, target)
        _write_install_metadata(target, manifest, source)

        logger.info(
            "Installed skill %s (v%s) → %s",
            manifest.id, manifest.version, target,
        )

        return InstallResult(
            skill_id=manifest.id,
            name=manifest.name,
            version=manifest.version,
            path=str(target),
            source=source,
            permissions=list(manifest.permissions),
            dangerous_permissions=dangerous,
            installed_at=datetime.now(timezone.utc).isoformat(),
        )


def remove_skill(skill_id: str) -> bool:
    """
    Remove a marketplace-installed skill by id.

    Returns True if removed, False if not found.
    Built-in skills cannot be removed (always returns False with a log).
    """
    if not _safe_id(skill_id):
        raise InstallError(f"Invalid skill id: {skill_id!r}")

    if (BUILTIN_SKILLS_DIR / skill_id).exists():
        logger.warning("Refusing to remove built-in skill: %s", skill_id)
        return False

    target = USER_SKILLS_DIR / skill_id
    if not target.exists():
        return False

    try:
        shutil.rmtree(target)
        logger.info("Removed skill: %s", skill_id)
        return True
    except OSError as e:
        raise InstallError(f"Could not remove skill: {e}") from e


# ── Internal helpers ──────────────────────────────────────────────────────────


def _fetch_source(source: str, dest: Path) -> None:
    """Materialize a source URL/path into dest as a local directory."""
    # github:user/repo shorthand
    short = GITHUB_SHORT_RE.match(source)
    if short:
        url = f"https://github.com/{short.group(1)}.git"
        return _git_clone(url, dest)

    # git URL
    if GIT_URL_RE.match(source):
        return _git_clone(source, dest)

    # file:// scheme
    if source.startswith("file://"):
        local = Path(source.replace("file://", "", 1))
        return _copy_local(local, dest)

    # Local path (Windows or POSIX absolute)
    local = Path(source)
    if local.exists() and local.is_dir():
        return _copy_local(local, dest)

    raise InstallError(
        f"Unrecognized source: {source!r}. "
        "Use a git URL (https://...), github:user/repo shorthand, "
        "or an absolute local path."
    )


def _git_clone(url: str, dest: Path) -> None:
    """Clone a git repo into dest. Shallow clone for speed."""
    logger.debug("git clone %s → %s", url, dest)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise InstallError(
                f"git clone failed (exit {result.returncode}): {result.stderr.strip()}"
            )
    except FileNotFoundError as e:
        raise InstallError("git is not installed or not in PATH") from e
    except subprocess.TimeoutExpired as e:
        raise InstallError("git clone timed out (120s)") from e


def _copy_local(src: Path, dest: Path) -> None:
    """Copy a local folder."""
    if not src.exists():
        raise InstallError(f"Source folder does not exist: {src}")
    if not src.is_dir():
        raise InstallError(f"Source is not a directory: {src}")
    shutil.copytree(src, dest)


def _find_skill_root(folder: Path) -> Optional[Path]:
    """
    Find the folder containing skill.json.
    Searches the root first, then immediate subdirectories (1 level deep).
    """
    if (folder / "skill.json").exists():
        return folder
    for sub in folder.iterdir():
        if sub.is_dir() and (sub / "skill.json").exists():
            return sub
    return None


def _write_install_metadata(target: Path, manifest: SkillManifest, source: str) -> None:
    """Write .marketplace.json sidecar with install metadata."""
    sidecar = target / ".marketplace.json"
    payload = {
        "source": source,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest.to_dict(),
    }
    try:
        sidecar.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write marketplace metadata for %s: %s", manifest.id, e)


def _safe_id(skill_id: str) -> bool:
    """Defense-in-depth: never let a path-traversal id through."""
    if not isinstance(skill_id, str):
        return False
    if "/" in skill_id or "\\" in skill_id or ".." in skill_id:
        return False
    return bool(skill_id) and len(skill_id) <= 64
