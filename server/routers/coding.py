"""
Coding agent router.

Endpoints:
  GET  /api/coding/status           — Provider reachability + model availability
  GET  /api/coding/models           — List Ollama models (when provider is ollama)
  GET  /api/coding/settings         — Current coding agent settings (no secrets)
  POST /api/coding/settings         — Update coding agent settings (writes .env)
  POST /api/coding/stream           — SSE streaming coding chat
  POST /api/coding/complete         — Non-streaming code completion
  GET  /api/coding/workspace        — List workspace files
  GET  /api/coding/workspace/read   — Read a workspace file
  POST /api/coding/workspace/write  — Write a workspace file
  POST /api/coding/workspace/tool   — Invoke a coding tool directly
"""
import json

import httpx
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse, StreamingResponse

from server.config import settings, write_env_value
from server.services.coding import (
    WORKSPACE_ROOT,
    execute_coding_tool,
    stream_coding_agent,
    tool_list_files,
    tool_read_file,
    tool_write_file,
)

router = APIRouter(prefix="/api/coding", tags=["coding"])


# ── Status / model discovery ───────────────────────────────────────────────────

@router.get("/status")
async def coding_status():
    """Check Ollama reachability and whether the coding model is pulled."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            base = settings.coding_model.split(":")[0]
            available = any(base in m for m in models)
            return {
                "ollama_running": True,
                "coding_model": settings.coding_model,
                "model_available": available,
                "available_models": models,
            }
    except Exception as exc:
        return JSONResponse(
            {"ollama_running": False, "error": str(exc)},
            status_code=503,
        )


@router.get("/settings")
async def get_coding_settings():
    """Return current coding agent settings — no API keys or secrets."""
    provider = settings.coding_provider.strip().lower()
    effective = provider if provider else settings.llm_provider.strip().lower()
    return {
        "llm_provider": settings.llm_provider,
        "coding_provider": settings.coding_provider,
        "effective_coding_provider": effective,
        "coding_model": settings.coding_model,
        "coding_max_iterations": settings.coding_max_iterations,
        "coding_shell_timeout": settings.coding_shell_timeout,
        "ollama_model": settings.ollama_model,
        "anthropic_model": settings.anthropic_model,
        "groq_model": settings.groq_model,
        "google_model": settings.google_model,
        "openai_model": settings.openai_model,
        "mistral_model": settings.mistral_model,
        "cohere_model": settings.cohere_model,
        "nvidia_nim_model": settings.nvidia_nim_model,
        "tts_provider": settings.tts_provider,
        "stt_provider": settings.stt_provider,
        "elevenlabs_voice_id": settings.elevenlabs_voice_id,
        "elevenlabs_tts_model": settings.elevenlabs_tts_model,
        "elevenlabs_stt_model": settings.elevenlabs_stt_model,
        "voice_providers": {
            "edge":       {"label": "Local (edge-tts / Whisper)", "configured": True},
            "elevenlabs": {"label": "ElevenLabs (cloud)",         "configured": bool(settings.elevenlabs_api_key)},
        },
        "providers": {
            "ollama":           {"label": "Ollama (local)",      "configured": True},
            "anthropic":        {"label": "Anthropic Claude",    "configured": bool(settings.anthropic_api_key)},
            "groq":             {"label": "Groq",                "configured": bool(settings.groq_api_key)},
            "google":           {"label": "Google Gemini",       "configured": bool(settings.google_api_key)},
            "openai-compatible":{"label": "OpenAI / Compatible", "configured": bool(settings.openai_api_key or settings.openai_base_url != "https://api.openai.com/v1")},
            "mistral":          {"label": "Mistral AI",          "configured": bool(settings.mistral_api_key)},
            "cohere":           {"label": "Cohere",              "configured": bool(settings.cohere_api_key)},
            "nvidia-nim":       {"label": "NVIDIA NIM",          "configured": bool(settings.nvidia_nim_api_key)},
        },
    }


_SETTINGS_ALLOWED = {
    "coding_provider", "coding_model", "coding_max_iterations", "coding_shell_timeout",
    "llm_provider",
    "ollama_model", "anthropic_model", "groq_model", "google_model",
    "openai_model", "mistral_model", "cohere_model", "nvidia_nim_model",
    "tts_provider", "stt_provider",
    "elevenlabs_voice_id", "elevenlabs_tts_model", "elevenlabs_stt_model",
}


@router.post("/settings")
async def update_coding_settings(payload: dict = Body(default={})):
    """
    Update coding agent settings. Writes to .env and applies in-memory immediately.
    Changes to llm_provider / coding_provider take effect for new requests right away.
    """
    updated: dict = {}
    for key, value in payload.items():
        if key not in _SETTINGS_ALLOWED:
            continue
        current = getattr(settings, key, None)
        if current is None:
            continue
        # Cast to the same type as the current value
        try:
            typed = type(current)(value)
        except (TypeError, ValueError):
            typed = str(value)
        setattr(settings, key, typed)
        write_env_value(key, str(typed))
        updated[key] = typed
    return {"updated": updated}


@router.get("/models")
async def list_coding_models():
    """Return all Ollama models with the current coding model highlighted."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            return {"models": models, "current": settings.coding_model}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)


# ── Streaming chat ─────────────────────────────────────────────────────────────

@router.post("/stream")
async def coding_stream(payload: dict = Body(default={})):
    """
    Stream a coding agent response as SSE.

    Body:
      message            str   — user's coding request (required)
      history            list  — prior messages [{role, content}, ...]
      auto_confirm_shell bool  — skip shell confirmation (default false)
      workspace_root     str   — absolute path to project root (optional)
                                 defaults to Luna's internal workspace
    """
    from pathlib import Path as _Path
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    auto_confirm_shell = bool(payload.get("auto_confirm_shell", False))
    ws_str = (payload.get("workspace_root") or "").strip()

    if not message:
        return JSONResponse({"detail": "message is required"}, status_code=400)

    workspace_root = _Path(ws_str) if ws_str else None

    messages = list(history) + [{"role": "user", "content": message}]

    async def generate():
        async for event in stream_coding_agent(
            messages,
            auto_confirm_shell=auto_confirm_shell,
            workspace_root=workspace_root,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Non-streaming completion ───────────────────────────────────────────────────

@router.post("/complete")
async def code_complete(payload: dict = Body(default={})):
    """
    Non-streaming code completion / generation.

    Body:
      code        str  — existing code snippet
      language    str  — programming language hint
      instruction str  — what to do (default: "Complete this code.")
    """
    code = (payload.get("code") or "").strip()
    language = (payload.get("language") or "").strip()
    instruction = (payload.get("instruction") or "Complete this code.").strip()

    if not code:
        return JSONResponse({"detail": "code is required"}, status_code=400)

    fence = f"```{language}" if language else "```"
    messages = [
        {
            "role": "user",
            "content": f"{instruction}\n\n{fence}\n{code}\n```",
        }
    ]

    full = ""
    async for event in stream_coding_agent(messages):
        if event["type"] == "token":
            full += event["content"]
        elif event["type"] == "done":
            break
        elif event["type"] == "error":
            return JSONResponse({"error": event["message"]}, status_code=502)

    return {"result": full.strip(), "model": settings.coding_model}


# ── Workspace file management ──────────────────────────────────────────────────

@router.get("/workspace")
def workspace_list(path: str = ""):
    """List files in the coding workspace directory."""
    return {"path": path or "(root)", "listing": tool_list_files(path)}


@router.get("/workspace/read")
def workspace_read(path: str):
    """Read a file from the coding workspace."""
    return {"path": path, "content": tool_read_file(path)}


@router.post("/workspace/write")
def workspace_write(payload: dict = Body(default={})):
    """Write a file to the coding workspace."""
    result = tool_write_file(
        payload.get("path", ""),
        payload.get("content", ""),
    )
    return {"result": result}


@router.post("/workspace/tool")
async def workspace_tool(payload: dict = Body(default={})):
    """
    Directly invoke a coding tool (for testing / UI integration).

    Body: {"tool": "<name>", "args": {...}}
    Shell tool (code_run_shell) always requires explicit confirm=true.
    """
    tool_name = (payload.get("tool") or "").strip()
    args = payload.get("args") or {}
    confirmed = bool(payload.get("confirm", False))

    if not tool_name:
        return JSONResponse({"detail": "tool is required"}, status_code=400)

    result, needs_confirm = await execute_coding_tool(tool_name, args)

    if needs_confirm and not confirmed:
        return JSONResponse(
            {
                "confirmation_required": True,
                "tool": tool_name,
                "args": args,
                "detail": "Pass confirm=true to execute this shell command.",
            },
            status_code=202,
        )

    return {"tool": tool_name, "result": result}
