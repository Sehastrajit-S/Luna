"""
Template for a new health integration.

HOW TO USE
----------
1. Copy this file: cp _template.py myplatform.py
2. Replace every TODO comment with real values.
3. Restart Luna — your integration is auto-discovered, nothing else needs changing.

The only hard requirement: define a class that subclasses HealthIntegration and
implement the three abstract methods (manifest, is_configured, sync).

For an OAuth platform, also override oauth_url and exchange_code.
For a webhook-only platform (like Apple or Samsung), leave sync() returning [].
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

# The auto-discovery system imports this base at startup:
from backend.services.health_integrations.base import (
    EnvField, HealthIntegration, IntegrationManifest,
)
# Persist points and update the sync log:
from backend.services.health_integrations.db import _update_sync, persist
# All available metric type constants live here:
from backend.services.health_integrations.models import (
    STEPS, HEART_RATE, SLEEP_DURATION,          # … import what you need
    HealthIntegrationError, HealthMetricPoint,
)
# Shared HTTP helpers — use _get for Bearer/token auth, _oauth_refresh for OAuth:
from backend.services.health_integrations.oauth import _get  # , _oauth_refresh

log = logging.getLogger(__name__)

# TODO: set your API base URL
MY_BASE = "https://api.myplatform.com/v1"


# ── Optional: standalone functions (mirrors fitbit.py / oura.py style) ────────
# You can also put all logic inline inside the class — either style works.

def myplatform_is_configured() -> bool:
    # TODO: check env vars via self.env() or os.environ / settings
    from backend.config import settings
    return bool(getattr(settings, "myplatform_api_key", ""))


async def myplatform_sync(db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
    if not myplatform_is_configured():
        raise HealthIntegrationError("MyPlatform not configured — set MYPLATFORM_API_KEY in .env")

    d = target_date or date.today().isoformat()
    points: list[HealthMetricPoint] = []

    # TODO: replace with your API token source
    token = ""  # e.g. settings.myplatform_api_key

    try:
        data = await _get(f"{MY_BASE}/daily?date={d}", token)
        # TODO: parse the response and append HealthMetricPoints:
        # HealthMetricPoint(platform, metric_type, value, unit, date_str)
        if "steps" in data:
            points.append(HealthMetricPoint("myplatform", STEPS, float(data["steps"]), "steps", d))
    except Exception as e:
        log.warning("MyPlatform sync: %s", e)

    count = persist(db, points)
    _update_sync(db, "myplatform", "ok", count)
    return points


# ── Integration class (required, auto-discovered by sync.py) ──────────────────

class MyPlatformIntegration(HealthIntegration):

    @property
    def manifest(self) -> IntegrationManifest:
        return IntegrationManifest(
            # TODO: fill in your platform details
            id="myplatform",           # must be unique, lowercase, no spaces
            name="MyPlatform",         # display name shown in the settings UI
            description="…",          # one line, shown on the integration card
            auth_type="apikey",        # "oauth" | "apikey" | "credentials" | "webhook"
            env_fields=[
                # TODO: list every env var your integration reads
                EnvField(
                    key="MYPLATFORM_API_KEY",
                    label="API Key",
                    secret=True,
                    placeholder="your-api-key-here",
                ),
                # Add more EnvField entries if you need multiple credentials:
                # EnvField("MYPLATFORM_USER_ID", "User ID", placeholder="12345"),
            ],
            help_text=(
                # TODO: step-by-step setup instructions shown in the UI
                "1. Sign in to myplatform.com/developer\n"
                "2. Create a new app and copy the API key\n"
                "3. Paste it below and click Save"
            ),
            help_url="https://myplatform.com/developer",
        )

    def is_configured(self) -> bool:
        return myplatform_is_configured()
        # Or inline without the helper:
        # return bool(self.env("MYPLATFORM_API_KEY"))

    async def sync(self, db: Session, target_date: Optional[str] = None) -> list[HealthMetricPoint]:
        return await myplatform_sync(db, target_date)

    # ── OAuth only — delete these two methods if auth_type != "oauth" ──────

    async def oauth_url(self, redirect_uri: str) -> str:
        from urllib.parse import urlencode
        # TODO: return your platform's authorization URL
        params = {
            "response_type": "code",
            "client_id":     self.env("MYPLATFORM_CLIENT_ID"),
            "redirect_uri":  redirect_uri,
            "scope":         "read",
        }
        return f"https://myplatform.com/oauth2/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        import httpx
        # TODO: exchange the code for an access token
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://myplatform.com/oauth2/token",
                data={
                    "grant_type":   "authorization_code",
                    "code":         code,
                    "redirect_uri": redirect_uri,
                    "client_id":    self.env("MYPLATFORM_CLIENT_ID"),
                    "client_secret": self.env("MYPLATFORM_CLIENT_SECRET"),
                },
            )
        resp.raise_for_status()
        return resp.json()  # must contain "access_token"
