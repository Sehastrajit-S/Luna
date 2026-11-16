"""Discovery probe for clients looking for Luna servers on a tailnet.

Public on purpose (see server/core/access.py): it reveals only that this is a
Luna server, its machine name, and whether the caller would be let in.
"""
from __future__ import annotations

import socket

from fastapi import APIRouter, Request

from server.config import settings
from server.core.access import authorization

router = APIRouter(prefix="/api/remote", tags=["remote"])


@router.get("/hello")
async def hello(request: Request) -> dict:
    how = await authorization(request.scope, settings.require_token_on_lan)
    return {
        "luna": True,
        "name": socket.gethostname(),
        "authorized": bool(how),
        "via": how or None,
    }
