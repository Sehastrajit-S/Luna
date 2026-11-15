"""
Skills Marketplace API.

Endpoints
─────────
GET    /api/skills/installed              — list all installed skills
GET    /api/skills/registry               — list community registry entries
POST   /api/skills/registry/refresh       — force-refresh the registry cache
GET    /api/skills/registry/search?q=...  — search the registry
GET    /api/skills/registry/{id}          — get one registry entry by id
POST   /api/skills/install                — install a skill (body: {source, confirm_dangerous, overwrite})
DELETE /api/skills/{id}                   — remove an installed skill
POST   /api/skills/validate               — validate a local folder for publishing
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from backend.services.skill_marketplace import (
    InstallError,
    ManifestError,
    PublishError,
    get_registry_entry,
    install_skill,
    list_installed,
    list_registry,
    refresh_registry,
    remove_skill,
    search_registry,
    validate_for_publish,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


# ── Installed ─────────────────────────────────────────────────────────────────


@router.get("/installed")
async def get_installed():
    """Return all installed skills (built-in + user-installed)."""
    return {"skills": list_installed()}


# ── Registry ──────────────────────────────────────────────────────────────────


@router.get("/registry")
async def get_registry():
    """Return the cached community registry."""
    entries = list_registry()
    return {"skills": [e.to_dict() for e in entries]}


@router.post("/registry/refresh")
async def post_registry_refresh():
    """Force-refresh the registry cache from the remote URL."""
    try:
        return refresh_registry()
    except Exception as e:
        logger.error("Registry refresh failed: %s", e, exc_info=True)
        raise HTTPException(502, f"Registry refresh failed: {e}")


@router.get("/registry/search")
async def get_registry_search(q: str = "", limit: int = 20):
    """Search the registry by id/name/description/tags."""
    entries = search_registry(q, limit=limit)
    return {"query": q, "skills": [e.to_dict() for e in entries]}


@router.get("/registry/{skill_id}")
async def get_registry_one(skill_id: str):
    """Look up one registry entry by id."""
    entry = get_registry_entry(skill_id)
    if entry is None:
        raise HTTPException(404, f"Skill '{skill_id}' not found in registry")
    return entry.to_dict()


# ── Install / Remove ──────────────────────────────────────────────────────────


@router.post("/install")
async def post_install(request: Request):
    """
    Install a skill from a git URL or local path.

    Body:
        source              (str, required)  — git URL, github:owner/repo, or local path
        confirm_dangerous   (bool, optional) — pre-approve dangerous permissions
        overwrite           (bool, optional) — reinstall if already present
    """
    try:
        body = await request.json()
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid JSON body: {e}")

    source = str(body.get("source", "")).strip()
    if not source:
        raise HTTPException(400, "Field 'source' is required")

    try:
        result = install_skill(
            source,
            confirm_dangerous=bool(body.get("confirm_dangerous", False)),
            overwrite=bool(body.get("overwrite", False)),
        )
        return {"ok": True, "skill": result.to_dict()}
    except InstallError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Install failed for source=%s: %s", source, e, exc_info=True)
        raise HTTPException(500, f"Install failed: {e}")


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """Remove an installed skill (user-installed only; built-ins are protected)."""
    try:
        removed = remove_skill(skill_id)
    except InstallError as e:
        raise HTTPException(400, str(e))

    if not removed:
        raise HTTPException(404, f"Skill '{skill_id}' is not installed")
    return {"ok": True, "removed": skill_id}


# ── Publishing helpers ────────────────────────────────────────────────────────


@router.post("/validate")
async def post_validate(request: Request):
    """
    Validate a local skill folder for publish-readiness.

    Body:
        path  (str, required)  — absolute path to the skill folder
    """
    try:
        body = await request.json()
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid JSON body: {e}")

    path = str(body.get("path", "")).strip()
    if not path:
        raise HTTPException(400, "Field 'path' is required")

    try:
        report = validate_for_publish(Path(path))
        return report.to_dict()
    except PublishError as e:
        raise HTTPException(400, str(e))
    except ManifestError as e:
        raise HTTPException(400, f"Manifest error: {e}")
    except Exception as e:
        logger.error("Validate failed for path=%s: %s", path, e, exc_info=True)
        raise HTTPException(500, f"Validate failed: {e}")
