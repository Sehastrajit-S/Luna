"""Local speech-to-text (open source): faster-whisper, shared by every voice surface.

One model instance serves the desktop mic button, the always-on voice loop and
the mobile endpoint. It loads on first use (no VRAM cost until you speak),
prefers the GPU and falls back to a small CPU model if CUDA is unavailable or
out of memory. Silero VAD (built into faster-whisper) trims silence first.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from server.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Transcript:
    text: str
    duration_s: float        # audio length
    elapsed_ms: int          # time spent transcribing
    model: str
    device: str


_dll_dirs_added = False


def _add_cuda_dll_dirs() -> None:
    """Make NVIDIA's pip-installed CUDA 12 runtime (nvidia-cublas-cu12,
    nvidia-cudnn-cu12, in this venv) visible to CTranslate2 on Windows —
    no system-wide CUDA toolkit needed."""
    global _dll_dirs_added
    if _dll_dirs_added or os.name != "nt":
        return
    _dll_dirs_added = True
    try:
        import nvidia
    except ImportError:
        return
    for base in getattr(nvidia, "__path__", []):
        for bin_dir in Path(base).glob("*/bin"):
            try:
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
            except OSError:
                pass


def _warm_up(model) -> None:
    """One second of silence through the full pipeline."""
    import numpy as np

    segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language="en", beam_size=1)
    list(segments)


class LocalSTT:
    def __init__(self) -> None:
        self._model = None
        self._model_name = ""
        self._device = ""
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()   # one transcription at a time on the GPU

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self, prefer_gpu: bool = True) -> None:
        from faster_whisper import WhisperModel

        if prefer_gpu:
            try:
                _add_cuda_dll_dirs()
                model = WhisperModel(settings.stt_model, device="cuda", compute_type="int8_float16")
                # Loading can succeed while the CUDA math libraries are missing
                # (cublas64_12.dll) — only running it proves the GPU path works.
                _warm_up(model)
                self._model, self._model_name, self._device = model, settings.stt_model, "cuda"
                logger.info("STT ready: %s on GPU (int8_float16)", settings.stt_model)
                return
            except Exception as e:  # no CUDA, missing libs, or not enough VRAM
                logger.warning("STT GPU path unavailable (%s); using CPU model %s", e, settings.stt_cpu_model)
        self._model = WhisperModel(settings.stt_cpu_model, device="cpu", compute_type="int8")
        self._model_name, self._device = settings.stt_cpu_model, "cpu"
        logger.info("STT ready: %s on CPU (int8)", settings.stt_cpu_model)

    def ensure_loaded(self) -> None:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    self._load()

    def _run(self, audio_path: str):
        segments, info = self._model.transcribe(
            audio_path,
            language=settings.stt_language or None,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,   # avoids repetition loops on long clips
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return text, float(getattr(info, "duration", 0.0) or 0.0)

    def transcribe_file(self, audio_path: str) -> Transcript:
        """Transcribe any audio file ffmpeg/PyAV can decode (wav, webm/opus, m4a, mp3…)."""
        self.ensure_loaded()
        start = time.perf_counter()
        with self._run_lock:
            try:
                text, duration = self._run(audio_path)
            except RuntimeError as e:
                if self._device != "cuda":
                    raise
                # GPU trouble mid-session (VRAM filled by another model, driver
                # hiccup) — finish on CPU rather than failing the dictation.
                logger.warning("STT GPU run failed (%s); switching to CPU", e)
                with self._load_lock:
                    self._load(prefer_gpu=False)
                text, duration = self._run(audio_path)
        elapsed = int((time.perf_counter() - start) * 1000)
        logger.info("STT %.1fs audio in %dms (%s/%s): %r", duration, elapsed, self._model_name, self._device, text[:80])
        return Transcript(text=text, duration_s=duration, elapsed_ms=elapsed, model=self._model_name, device=self._device)


@dataclass
class Segment:
    start: float
    end: float
    text: str


def _meeting_segments(model, audio_path: str, on_progress=None) -> tuple[list[Segment], float]:
    """Timestamped segments for long recordings; on_progress(fraction) as audio is decoded."""
    segments, info = model.transcribe(
        audio_path,
        language=settings.stt_language or None,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 700},
        condition_on_previous_text=False,
    )
    duration = float(getattr(info, "duration", 0.0) or 0.0)
    out = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            out.append(Segment(float(seg.start), float(seg.end), text))
        if on_progress and duration:
            on_progress(min(1.0, float(seg.end) / duration))
    return out, duration


def transcribe_segments(audio_path: str, on_progress=None) -> tuple[list[Segment], float]:
    """Meeting transcription with timestamps, on the shared local model (blocking: run in a thread)."""
    stt.ensure_loaded()
    with stt._run_lock:
        try:
            return _meeting_segments(stt._model, audio_path, on_progress)
        except RuntimeError as e:
            if stt._device != "cuda":
                raise
            logger.warning("STT GPU run failed on a meeting (%s); switching to CPU", e)
            with stt._load_lock:
                stt._load(prefer_gpu=False)
            return _meeting_segments(stt._model, audio_path, on_progress)


stt = LocalSTT()
