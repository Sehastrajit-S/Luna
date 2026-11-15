"""Unified sync dispatcher and integration status.

Platforms are auto-discovered: drop a file in this package that subclasses
HealthIntegration and it appears here automatically — no edits needed.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Optional

from sqlalchemy.orm import Session

from backend.services.health_integrations.base import HealthIntegration
from backend.services.health_integrations.db import _update_sync, get_sync_status
from backend.services.health_integrations.models import HealthIntegrationError

log = logging.getLogger(__name__)

_SKIP = {"base", "models", "db", "oauth", "sync", "webhooks"}


def _discover() -> dict[str, HealthIntegration]:
    import backend.services.health_integrations as _pkg
    platforms: dict[str, HealthIntegration] = {}
    for _, name, _ in pkgutil.iter_modules(_pkg.__path__):
        if name.startswith("_") or name in _SKIP:
            continue
        try:
            mod = importlib.import_module(f"backend.services.health_integrations.{name}")
        except Exception as e:
            log.warning("Health integration module %s failed to import: %s", name, e)
            continue
        for attr in vars(mod).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, HealthIntegration)
                and attr is not HealthIntegration
            ):
                try:
                    inst = attr()
                    platforms[inst.manifest.id] = inst
                except Exception as e:
                    log.warning("Health integration %s failed to instantiate: %s", attr.__name__, e)
    return platforms


_PLATFORMS: dict[str, HealthIntegration] = _discover()

# Backward-compatible dicts — the router calls these unchanged
PLATFORM_SYNC       = {k: v.sync          for k, v in _PLATFORMS.items()}
PLATFORM_CONFIGURED = {k: v.is_configured for k, v in _PLATFORMS.items()}
PLATFORM_OAUTH      = {
    k: (v.oauth_url, v.exchange_code)
    for k, v in _PLATFORMS.items()
    if v.is_oauth
}

# Webhook-only platforms have no sync function but are always "configured"
PLATFORM_CONFIGURED.update({"apple": lambda: True, "samsung": lambda: True})


async def sync_all(db: Session, target_date: Optional[str] = None) -> dict[str, int]:
    results = {}
    for name, fn in PLATFORM_SYNC.items():
        if PLATFORM_CONFIGURED[name]():
            try:
                pts = await fn(db, target_date)
                results[name] = len(pts)
            except HealthIntegrationError as e:
                log.warning("Health sync %s: %s", name, e)
                results[name] = -1
            except Exception as e:
                log.error("Health sync %s unexpected: %s", name, e)
                _update_sync(db, name, "error", 0, str(e))
                results[name] = -1
    return results


def integration_status(db: Session) -> dict:
    syncs     = {r["platform"]: r for r in get_sync_status(db)}
    webhook   = {"apple", "samsung"}
    platforms = []

    for name, configured_fn in PLATFORM_CONFIGURED.items():
        sync = syncs.get(name, {})
        if name in webhook:
            auth_type = "webhook"
        elif name in _PLATFORMS:
            auth_type = _PLATFORMS[name].manifest.auth_type
        else:
            auth_type = "unknown"
        platforms.append({
            "platform":       name,
            "configured":     configured_fn(),
            "auth_type":      auth_type,
            "status":         sync.get("status", "never"),
            "last_sync_at":   sync.get("last_sync_at"),
            "metrics_synced": sync.get("metrics_synced", 0),
        })

    return {"platforms": platforms}
