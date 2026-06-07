"""
L.U.N.A. Skills Marketplace.

Public API for managing community-contributed skills:
  - Validate skill manifests against a JSON schema
  - Install skills from git repositories or local paths
  - List installed skills with version, author, and source info
  - Remove installed skills safely (never touches built-in skills)
  - Search the curated registry index
  - Publish a skill (validate before pushing to a remote registry)

Skills installed via the marketplace go to:
    data/workspace/skills/<id>/
This keeps user-installed skills separate from built-in ones in skills/.
"""
from backend.services.skill_marketplace.manifest import (
    SkillManifest,
    ManifestError,
    validate_manifest,
    load_manifest,
)
from backend.services.skill_marketplace.installer import (
    install_skill,
    remove_skill,
    InstallError,
    InstallResult,
)
from backend.services.skill_marketplace.registry import (
    list_installed,
    list_registry,
    refresh_registry,
    search_registry,
    get_registry_entry,
)
from backend.services.skill_marketplace.publisher import (
    validate_for_publish,
    PublishError,
)

__all__ = [
    "SkillManifest",
    "ManifestError",
    "validate_manifest",
    "load_manifest",
    "install_skill",
    "remove_skill",
    "InstallError",
    "InstallResult",
    "list_installed",
    "list_registry",
    "refresh_registry",
    "search_registry",
    "get_registry_entry",
    "validate_for_publish",
    "PublishError",
]
