"""Shared OAuth2 and HTTP helpers."""
from __future__ import annotations

import base64

import httpx


async def _oauth_refresh(token_url: str, client_id: str, client_secret: str, refresh_token: str) -> dict:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            token_url,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        )
    resp.raise_for_status()
    return resp.json()


async def _get(url: str, token: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)
    resp.raise_for_status()
    return resp.json()


async def _post_json(url: str, token: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=body)
    resp.raise_for_status()
    return resp.json()
