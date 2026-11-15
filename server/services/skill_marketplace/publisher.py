"""
Publisher — validate a skill folder for submission to the marketplace registry.

This does NOT push the skill anywhere directly (the actual registry is
maintained as a curated git repo with PRs).  It produces a validation report
that the user includes in their PR.

Validation checks:
  - Manifest is valid (delegates to manifest.validate_manifest)
  - SKILL.md exists and is non-trivial
  - License field is present (warn if missing)
  - Required UI variant files exist if multi-modal: cli.md, electron.md
  - No suspiciously large binary files in the folder
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from backend.services.skill_marketplace.manifest import (
    ManifestError,
    SkillManifest,
    load_manifest,
)

logger = logging.getLogger(__name__)

# Files larger than this trigger a warning (skills should be small text bundles)
_MAX_FILE_BYTES = 256 * 1024  # 256 KB
_MAX_TOTAL_BYTES = 2 * 1024 * 1024  # 2 MB total
_MIN_SKILL_MD_CHARS = 200


class PublishError(Exception):
    """Raised when a skill cannot be published due to fatal validation issues."""


@dataclass
class PublishReport:
    """Result of a publish validation."""

    ok: bool
    skill_id: str
    name: str
    version: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "skill_id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


def validate_for_publish(folder: str | Path) -> PublishReport:
    """
    Run all publish-readiness checks on a skill folder.

    Returns a PublishReport. Caller should display errors+warnings to the user
    and only consider the skill ready when report.ok is True.
    """
    folder = Path(folder).resolve()
    if not folder.exists() or not folder.is_dir():
        raise PublishError(f"Not a valid folder: {folder}")

    # ── Manifest is the gating factor ────────────────────────────────────────
    try:
        manifest = load_manifest(folder)
    except ManifestError as e:
        return PublishReport(
            ok=False,
            skill_id="",
            name="",
            version="",
            errors=[f"Manifest invalid: {e}"],
        )

    report = PublishReport(
        ok=True,
        skill_id=manifest.id,
        name=manifest.name,
        version=manifest.version,
    )

    _check_skill_md(folder, report)
    _check_license(manifest, report)
    _check_dangerous_perms(manifest, report)
    _check_file_sizes(folder, report)
    _check_ui_variants(folder, report)

    if report.errors:
        report.ok = False

    return report


# ── Individual checks ─────────────────────────────────────────────────────────


def _check_skill_md(folder: Path, report: PublishReport) -> None:
    """SKILL.md must exist and have substantive content."""
    md = folder / "SKILL.md"
    if not md.exists():
        report.errors.append("SKILL.md is missing (required: instructions for Luna)")
        return

    try:
        content = md.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as e:
        report.errors.append(f"Could not read SKILL.md: {e}")
        return

    if len(content) < _MIN_SKILL_MD_CHARS:
        report.warnings.append(
            f"SKILL.md is very short ({len(content)} chars). "
            "Consider expanding the workflow description."
        )
    else:
        report.info.append(f"SKILL.md OK ({len(content)} chars)")


def _check_license(manifest: SkillManifest, report: PublishReport) -> None:
    """Recommend declaring a license."""
    if not manifest.license:
        report.warnings.append(
            "No 'license' field in skill.json. "
            "Add an SPDX identifier (e.g. \"license\": \"MIT\")."
        )
    else:
        report.info.append(f"License: {manifest.license}")


def _check_dangerous_perms(manifest: SkillManifest, report: PublishReport) -> None:
    """Surface dangerous permissions so the publisher reviews them."""
    dangerous = manifest.has_dangerous_permissions()
    if dangerous:
        report.warnings.append(
            f"Skill declares dangerous permissions: {dangerous}. "
            "Users will see a confirmation prompt before installing."
        )


def _check_file_sizes(folder: Path, report: PublishReport) -> None:
    """Skills should be lightweight text bundles, not binary blobs."""
    total = 0
    big_files: list[str] = []

    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        # Skip git internals if any
        if ".git" in path.parts:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        total += size
        if size > _MAX_FILE_BYTES:
            big_files.append(f"{path.relative_to(folder)} ({size // 1024} KB)")

    if big_files:
        report.warnings.append(
            "Large files detected (skills should stay <256KB per file): "
            + ", ".join(big_files[:5])
        )
    if total > _MAX_TOTAL_BYTES:
        report.warnings.append(
            f"Skill folder is large ({total // 1024} KB). "
            "Consider trimming examples or moving assets to a CDN."
        )


def _check_ui_variants(folder: Path, report: PublishReport) -> None:
    """Suggest UI variant files for multi-modal usage."""
    if not (folder / "cli.md").exists() and not (folder / "electron.md").exists():
        report.info.append(
            "No cli.md/electron.md variants — base SKILL.md will be used everywhere. "
            "(That's fine for most skills.)"
        )
