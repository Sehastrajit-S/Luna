"""
Voice API — state SSE stream + enable/disable toggle.
"""
import asyncio
import json
import os
import tempfile
from fastapi import APIRouter
from fastapi import UploadFile, File
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from server.services.voice import voice_service, VoiceState

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Each entry: (event_loop, asyncio.Queue) — one per active SSE client
_subscribers: list[tuple[asyncio.AbstractEventLoop, "asyncio.Queue[object]"]] = []


def _push_state(state: VoiceState):
    """Called from the voice background thread — bridges into each client's event loop."""
    for loop, q in list(_subscribers):
        try:
            loop.call_soon_threadsafe(q.put_nowait, state.value)
        except RuntimeError:
            pass


def _push_quit():
    """Push a quit event to all SSE subscribers."""
    for loop, q in list(_subscribers):
        try:
            loop.call_soon_threadsafe(q.put_nowait, "__quit__")
        except RuntimeError:
            pass


def _push_ui_event(event: dict):
    """Push a UI event to all SSE subscribers."""
    for loop, q in list(_subscribers):
        try:
            loop.call_soon_threadsafe(q.put_nowait, event)
        except RuntimeError:
            pass


voice_service.on_state_change(_push_state)
voice_service.on_quit(_push_quit)
voice_service.on_ui_event(_push_ui_event)


@router.get("/state")
def get_state():
    return {"state": voice_service.state, "enabled": voice_service.enabled}


@router.post("/toggle")
def toggle_voice():
    enabled = voice_service.toggle()
    return {"enabled": enabled, "state": voice_service.state}


@router.post("/away/off")
def away_off():
    from server.services.away_state import set_away
    set_away(False)
    return {"ok": True}


MAX_DICTATION_BYTES = 25 * 1024 * 1024   # ~25 min of Opus; far beyond a chat message
_AUDIO_SUFFIXES = {".webm", ".ogg", ".opus", ".wav", ".m4a", ".mp4", ".mp3", ".flac", ".aac"}


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Dictation for the chat box: audio in, text out (local open-source STT).

    The desktop app records WebM/Opus in the browser engine and posts it here;
    the transcript goes into the message box for the user to review and send.
    """
    from server.services.stt import stt

    suffix = os.path.splitext(audio.filename or "")[1].lower()
    if suffix not in _AUDIO_SUFFIXES:
        suffix = ".webm"
    size = 0
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        audio_path = f.name
        while chunk := await audio.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_DICTATION_BYTES:
                break
            f.write(chunk)
    try:
        if size == 0:
            return JSONResponse({"error": "No audio was recorded."}, status_code=400)
        if size > MAX_DICTATION_BYTES:
            return JSONResponse({"error": "That recording is too long."}, status_code=413)
        try:
            result = await asyncio.to_thread(stt.transcribe_file, audio_path)
        except Exception as e:
            return JSONResponse({"error": f"Transcription failed: {e}"}, status_code=500)
        return {
            "text": result.text,
            "duration_s": round(result.duration_s, 2),
            "elapsed_ms": result.elapsed_ms,
            "model": result.model,
            "device": result.device,
        }
    finally:
        try:
            os.unlink(audio_path)
        except OSError:
            pass


MAX_SPEAK_CHARS = 2000


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_SPEAK_CHARS)


@router.post("/speak")
async def speak_text(body: SpeakRequest):
    """Voice mode for the chat box: text in, MP3 out (same engines as the voice loop).

    Uses ElevenLabs when configured, otherwise edge-tts. Playback happens in the
    client so it can be interrupted when the user starts talking.
    """
    text = body.text.strip()
    if not text:
        return JSONResponse({"error": "Nothing to say."}, status_code=400)
    mp3_path = await asyncio.to_thread(voice_service._synthesize, text)
    if not mp3_path:
        return JSONResponse({"error": "Speech synthesis is unavailable — check the TTS settings."}, status_code=503)
    try:
        with open(mp3_path, "rb") as f:
            audio = f.read()
    finally:
        try:
            os.unlink(mp3_path)
        except OSError:
            pass
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@router.get("/stt-status")
async def stt_status():
    from server.config import settings
    from server.services.stt import stt
    return {"provider": settings.stt_provider, "model": settings.stt_model, "loaded": stt.loaded}


@router.post("/mobile")
async def mobile_voice(audio: UploadFile = File(...)):
    suffix = ".webm"
    if audio.filename and "." in audio.filename:
        suffix = "." + audio.filename.rsplit(".", 1)[-1].lower()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        audio_path = f.name
        f.write(await audio.read())

    try:
        transcript = voice_service.transcribe_file(audio_path)
        transcript = transcript.strip()
        if not transcript:
            return {"transcript": "", "response": ""}
        response = voice_service.collect_response_text(transcript)
        return {"transcript": transcript, "response": response}
    finally:
        try:
            os.unlink(audio_path)
        except OSError:
            pass


@router.get("/elevenlabs-voices")
async def elevenlabs_voices():
    """List available ElevenLabs voices for the configured API key."""
    from server.config import settings
    if not settings.elevenlabs_api_key:
        return JSONResponse({"error": "elevenlabs_api_key is not set"}, status_code=400)

    import httpx
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0)) as client:
            r = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": settings.elevenlabs_api_key},
            )
            r.raise_for_status()
            voices = [
                {"voice_id": v.get("voice_id"), "name": v.get("name")}
                for v in r.json().get("voices", [])
            ]
            return {"voices": voices}
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)


@router.get("/vosk-status")
def vosk_status():
    from pathlib import Path as _P
    vosk_dir = _P("data/vosk-model")
    vosk_ready = vosk_dir.exists() and any(vosk_dir.iterdir())
    try:
        import vosk  # noqa: F401
        vosk_package = True
    except ImportError:
        vosk_package = False
    return {"vosk_ready": vosk_ready, "vosk_package": vosk_package}


@router.post("/install-vosk")
async def install_vosk():
    from server.services.voice import voice_service as _vs

    async def _stream():
        import asyncio, json as _json
        from pathlib import Path as _P

        vosk_dir = _P("data/vosk-model")
        if vosk_dir.exists() and any(vosk_dir.iterdir()):
            yield f"data: {_json.dumps({'line': 'Already installed.', 'done': True})}\n\n"
            return

        yield f"data: {_json.dumps({'line': 'Downloading Vosk small-en model (~40 MB)…'})}\n\n"
        try:
            loop = asyncio.get_event_loop()
            progress: list[str] = []

            def _download_with_progress():
                import urllib.request, zipfile as _zf
                _P("data").mkdir(exist_ok=True)
                zip_path = _P("data/vosk-model.zip")
                total_chunks = [0]

                def _hook(count, block, total):
                    pct = min(100, int(count * block / total * 100)) if total else 0
                    if pct % 20 == 0:
                        msg = f"Downloading… {pct}%"
                        if not progress or progress[-1] != msg:
                            progress.append(msg)
                            loop.call_soon_threadsafe(lambda: None)
                    total_chunks[0] += 1

                urllib.request.urlretrieve(_vs.VOSK_URL, zip_path, _hook)
                progress.append("__download_done__")
                with _zf.ZipFile(zip_path, "r") as z:
                    top = z.namelist()[0].split("/")[0]
                    z.extractall("data/")
                extracted = _P(f"data/{top}")
                if extracted.exists():
                    extracted.rename(vosk_dir)
                zip_path.unlink(missing_ok=True)
                progress.append("__extract_done__")

            import threading
            t = threading.Thread(target=_download_with_progress, daemon=True)
            t.start()

            sent = 0
            while t.is_alive() or sent < len(progress):
                await asyncio.sleep(0.5)
                while sent < len(progress):
                    msg = progress[sent]; sent += 1
                    if msg == "__download_done__":
                        yield f"data: {_json.dumps({'line': 'Extracting model files…'})}\n\n"
                    elif msg == "__extract_done__":
                        yield f"data: {_json.dumps({'line': 'Vosk installed! Restart Luna to activate voice.', 'done': True})}\n\n"
                        return
                    else:
                        yield f"data: {_json.dumps({'line': msg})}\n\n"

        except Exception as e:
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/events")
async def voice_events():
    """SSE stream — emits {state} on every voice state change, pings every 25 s."""
    loop = asyncio.get_event_loop()
    q: asyncio.Queue[object] = asyncio.Queue()
    _subscribers.append((loop, q))

    async def stream():
        try:
            # Send current state immediately so the client doesn't start blind
            yield f"data: {json.dumps({'state': voice_service.state.value})}\n\n"
            while True:
                try:
                    state = await asyncio.wait_for(q.get(), timeout=25)
                    if state == "__quit__":
                        yield f"data: {json.dumps({'type': 'quit'})}\n\n"
                    elif isinstance(state, dict):
                        yield f"data: {json.dumps(state)}\n\n"
                    else:
                        yield f"data: {json.dumps({'state': state})}\n\n"
                except asyncio.TimeoutError:
                    yield "data: ping\n\n"
        except Exception:
            pass
        finally:
            _subscribers[:] = [(l, sq) for l, sq in _subscribers if sq is not q]

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
