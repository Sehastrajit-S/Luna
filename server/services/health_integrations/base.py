"""Abstract base class for health platform integrations.

To add a new platform
---------------------
1. Create ``backend/services/health_integrations/myplatform.py``
2. Subclass :class:`HealthIntegration` and implement the three required methods
3. Restart Luna — the platform is auto-discovered, nothing else needs changing

See ``_template.py`` for a complete starter file with inline comments.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from backend.services.health_integrations.models import HealthMetricPoint


@dataclass
class EnvField:
    """Declares one environment variable required by an integration."""
    key: str              # env var name, e.g. "FITBIT_CLIENT_ID"
    label: str            # human label shown in settings UI
    secret: bool = False  # True → render as password field
    placeholder: str = ""
    required: bool = True


@dataclass
class IntegrationManifest:
    """Metadata an integration declares about itself."""
    id: str           # unique slug, matches the platform name used in API routes
    name: str         # display name, e.g. "Fitbit"
    description: str  # one line shown in the integration card
    auth_type: str    # "oauth" | "apikey" | "credentials" | "webhook"
    env_fields: list[EnvField] = field(default_factory=list)
    help_text: str = ""   # step-by-step setup instructions
    help_url: str = ""    # link to the platform's developer console


class HealthIntegration(ABC):
    """Base class every health platform integration must subclass.

    Subclass contract
    -----------------
    - Implement :attr:`manifest` → declare name, auth type, env vars
    - Implement :meth:`is_configured` → return True when env vars are present
    - Implement :meth:`sync` → fetch data, persist via :func:`persist`, return points

    OAuth platforms also override :meth:`oauth_url` and :meth:`exchange_code`.
    Webhook-only platforms (Apple, Samsung) can leave :meth:`sync` returning ``[]``.
    """

    @property
    @abstractmethod
    def manifest(self) -> IntegrationManifest:
        """Declare platform metadata and required env vars."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the minimum required env vars are set."""
        ...

    @abstractmethod
    async def sync(
        self, db: Session, target_date: Optional[str] = None
    ) -> list[HealthMetricPoint]:
        """Fetch data from the platform API and persist it.

        Args:
            db: SQLAlchemy session (injected by the router).
            target_date: ISO date string ``YYYY-MM-DD``. Defaults to today.

        Returns:
            List of :class:`HealthMetricPoint` objects that were persisted.
        """
        ...

    # ── Optional OAuth hooks ──────────────────────────────────────────────

    async def oauth_url(self, redirect_uri: str) -> Optional[str]:
        """Return the authorization URL to redirect the user to.

        Return ``None`` (default) for non-OAuth platforms.
        """
        return None

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange an OAuth authorization code for tokens.

        Return the raw token response dict (must contain ``access_token``).
        Default implementation returns ``{}`` (non-OAuth platforms).
        """
        return {}

    # ── Helpers ───────────────────────────────────────────────────────────

    def env(self, key: str, default: str = "") -> str:
        """Read an environment variable.

        New integrations can use this instead of adding fields to ``config.py``.
        The value is read live from ``os.environ`` so it picks up changes made
        by the settings UI without requiring a restart.
        """
        return os.environ.get(key, default)

    @property
    def is_oauth(self) -> bool:
        """Convenience: True when auth_type is 'oauth'."""
        return self.manifest.auth_type == "oauth"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.manifest.id!r}>"
