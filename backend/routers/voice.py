"""
Voice API — state SSE stream + enable/disable toggle.
"""
import asyncio
import json
import os
import tempfile
from fastapi import APIRouter
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse

from backend.services.voice import voice_service, VoiceState

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
    from backend.services.away_state import set_away
    set_away(False)
    return {"ok": True}


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
    from backend.services.voice import voice_service as _vs

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
