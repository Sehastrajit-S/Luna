"""Remote access and remote control.

GET  /api/remote/hello                    discovery probe (public, see server/core/access.py):
                                          reveals only that this is a Luna server, its machine
                                          name, and whether the caller would be let in.
GET  /api/remote/devices?refresh=1        this computer and your online tailnet devices, with
                                          whether each can take tasks (and why not)
POST /api/remote/devices/{id}/task        {"message", "conversation_id"?} → SSE stream of the
                                          device's chat events, ending in done or error
POST /api/remote/devices/{id}/confirm/{confirm_id}   {"approved"} → relays a yes/no for a
                                          tool the device asked about

Errors: {"detail": {"kind", "message"}}.
"""
from __future__ import annotations

import json
import socket
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.config import settings
from server.core.access import authorization
from server.services.remote_devices import MAX_MESSAGE, DeviceError, remote_devices

router = APIRouter(prefix="/api/remote", tags=["remote"])

_STATUS = {"not_found": 404, "offline": 409, "not_authorized": 403, "upstream": 502}


class TaskIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE)
    conversation_id: Optional[int] = Field(default=None, ge=1)


class ConfirmIn(BaseModel):
    approved: bool


def _fail(e: DeviceError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(e.kind, 502), detail={"kind": e.kind, "message": e.message})


@router.get("/hello")
async def hello(request: Request) -> dict:
    how = await authorization(request.scope, settings.require_token_on_lan)
    return {
        "luna": True,
        "name": socket.gethostname(),
        "authorized": bool(how),
        "via": how or None,
    }


@router.get("/devices")
async def devices(refresh: bool = False) -> dict:
    found, problem = await remote_devices.list(refresh=refresh)
    return {"devices": [d.public() for d in found], "tailscale": problem or None}


@router.post("/devices/{device_id}/task")
async def task(body: TaskIn, device_id: str = Path(..., max_length=255)):
    if not body.message.strip():
        raise HTTPException(status_code=422, detail={"kind": "invalid", "message": "Say what the device should do."})
    try:
        device = await remote_devices.get(device_id)
    except DeviceError as e:
        raise _fail(e)

    async def stream():
        yield f"data: {json.dumps({'type': 'device', 'id': device.id, 'name': device.name})}\n\n"
        async for event in remote_devices.run_task(device, body.message, body.conversation_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/devices/{device_id}/confirm/{confirm_id}")
async def confirm(
    body: ConfirmIn,
    device_id: str = Path(..., max_length=255),
    confirm_id: str = Path(..., pattern=r"^[A-Za-z0-9-]{1,64}$"),
) -> dict:
    try:
        device = await remote_devices.get(device_id)
    except DeviceError as e:
        raise _fail(e)
    if not await remote_devices.confirm(device, confirm_id, body.approved):
        raise HTTPException(status_code=410, detail={"kind": "expired", "message": "That question already timed out on the device."})
    return {"ok": True, "approved": body.approved}
