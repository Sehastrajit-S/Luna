"""
Registry — list installed skills + curated community index.

The community index is a JSON file fetched over HTTPS that lists vetted skills:
    https://raw.githubusercontent.com/<owner>/luna-skills-registry/main/index.json

Index schema:
{
  "version": 1,
  "updated_at": "2026-06-08T00:00:00Z",
  "skills": [
    {
      "id": "weather-pro",
      "name": "Weather Pro",
      "description": "Detailed forecasts and severe weather alerts.",
      "version": "1.2.0",
      "author": "alice",
      "homepage": "https://github.com/alice/weather-pro",
      "source": "github:alice/weather-pro",
      "permissions": ["web"],
      "tags": ["weather", "forecasting"],
      "stars": 142,
      "downloads": 1820,
      "verified": true
    }
  ]
}

The registry URL is configurable so private/self-hosted registries work too.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

from backend.config import BASE_DIR, DATA_DIR, settings
from backend.services.skill_marketplace.installer import (
    BUILTIN_SKILLS_DIR,
    USER_SKILLS_DIR,
)
from backend.services.skill_marketplace.manifest import (
    ManifestError,
    load_manifest,
)

logger = logging.getLogger(__name__)

# Cache file for the remote registry index. Refreshed on demand or every TTL.
_REGISTRY_CACHE = DATA_DIR / "registry_cache.json"
_REGISTRY_TTL_SECONDS = 6 * 3600  # 6 hours


@dataclass
class RegistryEntry:
    """One skill in the community registry index."""

    id: str
    name: str
    description: str
    version: str
    source: str
    author: str = ""
    homepage: str = ""
    permissions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    stars: int = 0
    downloads: int = 0
    verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "source": self.source,
            "author": self.author,
            "homepage": self.homepage,
            "permissions": list(self.permissions),
            "tags": list(self.tags),
            "stars": self.stars,
            "downloads": self.downloads,
            "verified": self.verified,
        }


# ── Installed skills (local) ──────────────────────────────────────────────────


def list_installed() -> list[dict[str, Any]]:
    """
    Return all skills currently installed (built-in + user-installed).
    Each entry includes manifest fields plus 'origin' ('builtin' | 'user') and
    optional 'install_metadata' for marketplace-installed skills.
    """
    out: list[dict[str, Any]] = []

    for origin, root in (("builtin", BUILTIN_SKILLS_DIR), ("user", USER_SKILLS_DIR)):
        if not root.exists():
            continue
        for folder in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not folder.is_dir() or folder.name.startswith("_"):
                continue
            entry = _read_installed_entry(folder, origin)
            if entry:
                out.append(entry)

    return out


def _read_installed_entry(folder: Path, origin: str) -> Optional[dict[str, Any]]:
    """Build the per-skill response payload for an installed skill."""
    try:
        manifest = load_manifest(folder)
    except ManifestError as e:
        logger.warning("Skipping invalid skill at %s: %s", folder, e)
        return None

    payload = manifest.to_dict()
    payload["origin"] = origin
    payload["path"] = str(folder)

    sidecar = folder / ".marketplace.json"
    if sidecar.exists():
        try:
            payload["install_metadata"] = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Could not parse marketplace sidecar for %s: %s", folder.name, e)

    return payload


# ── Community registry index ──────────────────────────────────────────────────


def list_registry(force_refresh: bool = False) -> list[RegistryEntry]:
    """
    Return the cached community registry. Refreshes if the cache is stale
    or force_refresh=True.

    On any network failure we fall back to the cached copy if available.
    """
    cache = _load_cache()

    if force_refresh or _cache_is_stale(cache):
        try:
            cache = _fetch_remote_index()
            _save_cache(cache)
        except (httpx.HTTPError, OSError, ValueError) as e:
            logger.warning("Could not refresh registry, using cache: %s", e)
            if cache is None:
                return []

    if cache is None:
        return []

    entries: list[RegistryEntry] = []
    for raw in cache.get("skills", []):
        try:
            entries.append(_entry_from_dict(raw))
        except (TypeError, ValueError) as e:
            logger.debug("Skipping malformed registry entry: %s", e)

    return entries


def refresh_registry() -> dict[str, Any]:
    """Force-refresh the registry index. Returns summary stats."""
    entries = list_registry(force_refresh=True)
    return {
        "ok": True,
        "count": len(entries),
        "cached_at": time.time(),
    }


def search_registry(query: str, limit: int = 20) -> list[RegistryEntry]:
    """Case-insensitive substring search across id, name, description, tags."""
    q = (query or "").strip().lower()
    if not q:
        return list_registry()[:limit]

    out: list[RegistryEntry] = []
    for entry in list_registry():
        haystack = " ".join([
            entry.id, entry.name, entry.description,
            entry.author, " ".join(entry.tags),
        ]).lower()
        if q in haystack:
            out.append(entry)
            if len(out) >= limit:
                break
    return out


def get_registry_entry(skill_id: str) -> Optional[RegistryEntry]:
    """Look up one entry by id from the registry."""
    for entry in list_registry():
        if entry.id == skill_id:
            return entry
    return None


# ── Cache helpers ─────────────────────────────────────────────────────────────


def _load_cache() -> Optional[dict[str, Any]]:
    if not _REGISTRY_CACHE.exists():
        return None
    try:
        return json.loads(_REGISTRY_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Registry cache is corrupt, ignoring: %s", e)
        return None


def _save_cache(payload: dict[str, Any]) -> None:
    _REGISTRY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = {**payload, "_cached_at": time.time()}
    try:
        _REGISTRY_CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write registry cache: %s", e)


def _cache_is_stale(cache: Optional[dict[str, Any]]) -> bool:
    if cache is None:
        return True
    cached_at = cache.get("_cached_at", 0)
    return (time.time() - cached_at) > _REGISTRY_TTL_SECONDS


def _fetch_remote_index() -> dict[str, Any]:
    """Fetch the registry index. URL configurable via skill_registry_url setting."""
    url = getattr(settings, "skill_registry_url", "") or _DEFAULT_REGISTRY_URL
    logger.info("Fetching skill registry from %s", url)

    with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
        r = client.get(url, follow_redirects=True)
        r.raise_for_status()
        data = r.json()

    if not isinstance(data, dict) or "skills" not in data:
        raise ValueError("Registry index missing 'skills' field")
    if not isinstance(data["skills"], list):
        raise ValueError("'skills' must be a list")

    return data


def _entry_from_dict(raw: dict[str, Any]) -> RegistryEntry:
    """Construct a RegistryEntry from a raw dict; raises on missing required fields."""
    for key in ("id", "name", "description", "version", "source"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise ValueError(f"Registry entry missing required field: {key}")
    return RegistryEntry(
        id=raw["id"],
        name=raw["name"],
        description=raw["description"],
        version=raw["version"],
        source=raw["source"],
        author=raw.get("author", ""),
        homepage=raw.get("homepage", ""),
        permissions=list(raw.get("permissions", [])),
        tags=list(raw.get("tags", [])),
        stars=int(raw.get("stars", 0) or 0),
        downloads=int(raw.get("downloads", 0) or 0),
        verified=bool(raw.get("verified", False)),
    )


# Default registry. Users can override via .env: skill_registry_url=https://...
_DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/Sehastrajit/luna-skills-registry/main/index.json"
)
