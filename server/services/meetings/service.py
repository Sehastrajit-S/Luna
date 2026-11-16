"""Meeting mode: record → transcribe → minutes.

The browser uploads the recording in small numbered chunks while the meeting
runs (a dropped connection loses seconds, not the meeting). Finishing starts a
background job: transcribe with timestamps, then write minutes. Status and
progress are kept in the meeting's _meeting.json so any device can follow it.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from server.services.audit_log import record_audit
from server.services.meetings import store
from server.services.meetings.minutes import transcript_markdown, write_minutes

logger = logging.getLogger("luna.meetings")

MAX_CHUNK_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 600 * 1024 * 1024          # ~20 hours of Opus
_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_running: dict[str, asyncio.Task] = {}


class MeetingError(ValueError):
    """kind: bad_request | out_of_order | too_large | wrong_state"""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def public(meta: dict) -> dict:
    """What clients see; adds transcript/minutes text once they exist."""
    out = {k: meta.get(k) for k in ("id", "title", "status", "stage", "progress", "error", "started_at",
                                     "ended_at", "duration_s", "audio_bytes", "chunks")}
    out["folder"] = f"meetings/{meta['id']}"
    if meta.get("status") == "processing" and meta["id"] not in _running:
        # The server restarted mid-job: say so, and let the user retry.
        out["status"], out["error"] = "interrupted", "Luna restarted while processing this meeting. Retry to finish it."
    path = store.root() / meta["id"]
    for key, name in (("minutes", store.MINUTES), ("transcript", store.TRANSCRIPT)):
        file = path / name
        out[key] = file.read_text(encoding="utf-8") if file.exists() else None
    return out


def start(title: str = "") -> dict:
    title = " ".join(str(title or "").split())[:120] or "Meeting"
    now = datetime.now(timezone.utc)
    meta = store.write({
        "id": store.new_id(title if title != "Meeting" else "", now.astimezone()),
        "title": title, "status": "recording", "stage": None, "progress": 0.0, "error": None,
        "started_at": now.isoformat(), "ended_at": None, "duration_s": None, "audio_bytes": 0, "chunks": 0,
    })
    record_audit("meeting_started", tool="meetings", args={"meeting_id": meta["id"]})
    return public(meta)


def append_audio(meeting_id: str, seq: int, data: bytes) -> dict:
    """Chunks must arrive in order. Re-sending an already stored chunk is a no-op (safe retries)."""
    meta = store.read(meeting_id)
    if meta["status"] != "recording":
        raise MeetingError("wrong_state", "This meeting has already stopped recording.")
    if seq < meta["chunks"]:
        return public(meta)
    if seq > meta["chunks"]:
        raise MeetingError("out_of_order", f"Expected chunk {meta['chunks']}, got {seq}.")
    if not data or len(data) > MAX_CHUNK_BYTES:
        raise MeetingError("bad_request", "Audio chunks must be between 1 byte and 8 MB.")
    if meta["audio_bytes"] + len(data) > MAX_AUDIO_BYTES:
        raise MeetingError("too_large", "This recording reached the maximum length. Stop it to write the minutes.")
    with (store.folder(meeting_id) / store.AUDIO).open("ab") as f:
        f.write(data)
    return public(store.update(meeting_id, chunks=meta["chunks"] + 1, audio_bytes=meta["audio_bytes"] + len(data)))


def finish(meeting_id: str) -> dict:
    meta = store.read(meeting_id)
    if meeting_id in _running:
        return public(meta)
    if meta["status"] not in ("recording", "processing", "error"):
        raise MeetingError("wrong_state", "This meeting has already been processed.")
    if not meta["audio_bytes"]:
        store.update(meeting_id, status="error", error="Nothing was recorded.", ended_at=meta["ended_at"] or _now())
        raise MeetingError("bad_request", "Nothing was recorded.")
    meta = store.update(meeting_id, status="processing", stage="transcribing", progress=0.0, error=None,
                        ended_at=meta["ended_at"] or _now())
    _running[meeting_id] = asyncio.get_running_loop().create_task(_process(meeting_id))
    _running[meeting_id].add_done_callback(lambda _t: _running.pop(meeting_id, None))
    return public(meta)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _process(meeting_id: str, transcribe=None, complete=None) -> None:
    from server.services import stt

    transcribe = transcribe or stt.transcribe_segments
    path = store.folder(meeting_id)
    meta = store.read(meeting_id)
    loop = asyncio.get_running_loop()

    def progress(stage: str, base: float, span: float):
        last = {"value": -1.0}

        def report(fraction: float) -> None:
            value = round(base + span * fraction, 3)
            if value - last["value"] >= 0.02:          # don't rewrite the file for every segment
                last["value"] = value
                loop.call_soon_threadsafe(lambda: store.update(meeting_id, stage=stage, progress=value))
        return report

    try:
        segments, duration = await asyncio.to_thread(transcribe, str(path / store.AUDIO),
                                                     progress("transcribing", 0.0, 0.7))
        store.update(meeting_id, duration_s=round(duration, 1))
        if not segments:
            store.update(meeting_id, status="error", stage=None,
                         error="No speech was found in the recording. Check that the right microphone was used.")
            return
        (path / store.TRANSCRIPT).write_text(
            transcript_markdown(meta["title"], meta["started_at"], duration, segments), encoding="utf-8")

        store.update(meeting_id, stage="writing_minutes", progress=0.72)
        title, minutes = await write_minutes(meta["title"], meta["started_at"], duration, segments,
                                             complete=complete, on_progress=progress("writing_minutes", 0.72, 0.25))
        (path / store.MINUTES).write_text(_THINK_RE.sub("", minutes).strip() + "\n", encoding="utf-8")
        if title != meta["title"]:
            (path / store.TRANSCRIPT).write_text(
                transcript_markdown(title, meta["started_at"], duration, segments), encoding="utf-8")
        store.update(meeting_id, status="done", stage=None, progress=1.0, title=title)
        record_audit("meeting_processed", tool="meetings", args={"meeting_id": meeting_id},
                     result=f"{len(segments)} segments, {round(duration)}s")
    except Exception as e:                          # keep whatever finished; say what didn't
        logger.error("Meeting %s failed: %s", meeting_id, e, exc_info=True)
        has_transcript = (path / store.TRANSCRIPT).exists()
        message = ("The transcript is saved, but writing the minutes failed. Check that Luna's model is running, then retry."
                   if has_transcript else "Transcribing the recording failed. Retry, or check the speech-to-text settings.")
        store.update(meeting_id, status="error", stage=None, error=message)
        record_audit("meeting_processed", tool="meetings", args={"meeting_id": meeting_id}, status="error",
                     result=type(e).__name__)


def get(meeting_id: str) -> dict:
    return public(store.read(meeting_id))


def recent(limit: int = 20) -> list[dict]:
    return [{k: v for k, v in public(m).items() if k not in ("minutes", "transcript")} for m in store.list_all(limit)]
