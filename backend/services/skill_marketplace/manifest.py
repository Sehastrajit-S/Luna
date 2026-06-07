"""
SkillManifest — schema, parser, and validator for skill.json files.

Schema (skill.json fields):
  id            (str, required)  — unique slug, [a-z0-9-]
  name          (str, required)  — display name
  description   (str, required)  — one-sentence purpose; used by LLM for routing
  version       (str, optional)  — semver string, default "0.1.0"
  author        (str, optional)  — username or org
  homepage      (str, optional)  — URL for documentation
  license       (str, optional)  — SPDX identifier (MIT, Apache-2.0, ...)
  permissions   (list[str])      — declared capabilities (see ALLOWED_PERMISSIONS)
  tools         (list[str])      — tool names this skill may invoke
  tags          (list[str])      — for marketplace search/filtering
  min_luna      (str, optional)  — minimum L.U.N.A. version this skill supports

Permissions are explicit and shown to the user before install. They map to what
the skill is allowed to ask Luna to do. Unknown permissions cause validation
failure — additions require updating ALLOWED_PERMISSIONS below.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Whitelist of permissions a skill may declare ─────────────────────────────
# Adding a new permission requires:
#   1. Adding it here
#   2. Wiring the corresponding tool/permission gate into permission_manager.py
ALLOWED_PERMISSIONS = frozenset({
    "web",           # web_search, web_fetch, web_research
    "filesystem",    # workspace_read, workspace_write
    "shell",         # shell command execution (always confirmed by user)
    "system",        # volume, brightness, clipboard, system info
    "calendar",      # read/write calendar events
    "tasks",         # read/write task list
    "memory",        # store/retrieve facts
    "spotify",       # play/pause/queue music
    "vision",        # screen + camera awareness
    "github",        # GitHub API calls
    "google",        # Google Workspace (Gmail, Drive, Calendar)
    "microsoft",     # Microsoft 365 (Outlook, OneDrive, Teams)
    "health",        # health metrics from integrations
    "voice",         # TTS/STT control
    "browser",       # automated browser control
    "datasets",      # dataset_search, dataset operations
})

# Permissions that are HIGH-RISK and require user confirmation before install
DANGEROUS_PERMISSIONS = frozenset({"shell", "filesystem", "browser"})

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+)?$")


class ManifestError(ValueError):
    """Raised when a skill.json fails validation."""


@dataclass
class SkillManifest:
    """Validated skill manifest.  Only constructed via load_manifest/validate_manifest."""

    id: str
    name: str
    description: str
    version: str = "0.1.0"
    author: str = ""
    homepage: str = ""
    license: str = ""
    permissions: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    min_luna: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "homepage": self.homepage,
            "license": self.license,
            "permissions": list(self.permissions),
            "tools": list(self.tools),
            "tags": list(self.tags),
            "min_luna": self.min_luna,
        }

    def has_dangerous_permissions(self) -> list[str]:
        """Return the subset of declared permissions considered dangerous."""
        return [p for p in self.permissions if p in DANGEROUS_PERMISSIONS]


# ── Validation ────────────────────────────────────────────────────────────────


def validate_manifest(data: dict[str, Any]) -> SkillManifest:
    """
    Validate a manifest dict. Returns a SkillManifest on success.
    Raises ManifestError with a clear message on failure.
    """
    if not isinstance(data, dict):
        raise ManifestError("skill.json must be a JSON object")

    # ── Required fields ──────────────────────────────────────────────────────
    for key in ("id", "name", "description"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(f"'{key}' is required and must be a non-empty string")

    skill_id = data["id"].strip()
    if not ID_RE.match(skill_id):
        raise ManifestError(
            f"Invalid id '{skill_id}': must be 3-64 lowercase chars (a-z, 0-9, hyphen), "
            "must not start or end with a hyphen"
        )

    # ── Optional with type checks ────────────────────────────────────────────
    version = str(data.get("version", "0.1.0")).strip() or "0.1.0"
    if not SEMVER_RE.match(version):
        raise ManifestError(f"version '{version}' is not valid semver (e.g. 1.2.3)")

    permissions = data.get("permissions", []) or []
    if not isinstance(permissions, list) or any(not isinstance(p, str) for p in permissions):
        raise ManifestError("'permissions' must be a list of strings")

    bad_perms = [p for p in permissions if p not in ALLOWED_PERMISSIONS]
    if bad_perms:
        raise ManifestError(
            f"Unknown permissions: {bad_perms}. "
            f"Allowed: {sorted(ALLOWED_PERMISSIONS)}"
        )

    tools = data.get("tools", []) or []
    if not isinstance(tools, list) or any(not isinstance(t, str) for t in tools):
        raise ManifestError("'tools' must be a list of strings")

    tags = data.get("tags", []) or []
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ManifestError("'tags' must be a list of strings")

    return SkillManifest(
        id=skill_id,
        name=str(data["name"]).strip(),
        description=str(data["description"]).strip(),
        version=version,
        author=str(data.get("author", "")).strip(),
        homepage=str(data.get("homepage", "")).strip(),
        license=str(data.get("license", "")).strip(),
        permissions=list(dict.fromkeys(permissions)),  # dedupe, preserve order
        tools=list(dict.fromkeys(tools)),
        tags=list(dict.fromkeys(tags)),
        min_luna=str(data.get("min_luna", "")).strip(),
    )


def load_manifest(folder: Path) -> SkillManifest:
    """
    Read and validate the skill.json inside a folder.
    Raises ManifestError if missing, invalid JSON, or fails schema.
    """
    manifest_file = folder / "skill.json"
    if not manifest_file.exists():
        raise ManifestError(f"skill.json not found in {folder}")

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ManifestError(f"skill.json is not valid JSON: {e}") from e
    except OSError as e:
        raise ManifestError(f"Could not read skill.json: {e}") from e

    return validate_manifest(data)
