"""SSE endpoint for real-time proactive messages from Luna."""
import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.services import proactive_bus

router = APIRouter(prefix="/api/proactive", tags=["proactive"])


@router.get("/stream")
async def proactive_stream():
    """
    Persistent SSE stream. Frontend subscribes on startup; Luna pushes
    messages here when the situation warrants it without waiting for user input.
    """
    async def generate():
        heartbeat = 0
        while True:
            msgs = proactive_bus.drain()
            for msg in msgs:
                heartbeat = 0
                yield f"data: {json.dumps({'type': 'luna_speak', 'message': msg})}\n\n"
            if not msgs:
                heartbeat += 1
                if heartbeat >= 20:  # comment ping every 20s to keep connection alive
                    yield ": ping\n\n"
                    heartbeat = 0
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
