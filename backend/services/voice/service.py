"""VoiceService: mic → wake word → STT → LLM → TTS pipeline."""
import asyncio
import json
import os
import queue
import re
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from backend.services.stt import stt
from backend.services.voice.models import VoiceState


class VoiceService:
    SAMPLE_RATE   = 16_000
    WAKE_WORD     = "luna"
    _WAKE_PHRASES = ("luna", "wake up", "hey luna")
    VOSK_URL      = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    VOSK_DIR      = Path("data/vosk-model")

    SILENCE_LIMIT   = 6      # chunks of trailing silence before cutting off (6 * 0.25s = 1.5s)
    MAX_CHUNKS      = 480
    RMS_THRESHOLD   = 200
    PRE_SPEECH_WAIT = 240

    def __init__(self):
        self._state: VoiceState               = VoiceState.IDLE
        self._callbacks: list[Callable]       = []
        self._quit_callbacks: list[Callable]  = []
        self._ui_callbacks: list[Callable]    = []
        self._thread: threading.Thread | None = None
        self._stop                            = threading.Event()
        self._vosk_model                      = None
        self._models_ready                    = False
        self._pygame_ready                    = False
        self.enabled                          = False
        self._voice_conv_id: int | None       = None

    # ── state ─────────────────────────────────────────────────────────────────

    @property
    def state(self) -> VoiceState:
        return self._state

    def _set_state(self, s: VoiceState):
        self._state = s
        for cb in self._callbacks:
            try:
                cb(s)
            except Exception:
                pass

    def on_state_change(self, cb: Callable):  self._callbacks.append(cb)
    def on_quit(self, cb: Callable):          self._quit_callbacks.append(cb)
    def on_ui_event(self, cb: Callable):      self._ui_callbacks.append(cb)

    def _fire_ui_event(self, event: dict):
        for cb in self._ui_callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def _fire_quit(self):
        for cb in self._quit_callbacks:
            try:
                cb()
            except Exception:
                pass

    # ── control ────────────────────────────────────────────────────────────────

    def enable(self):
        if self.enabled:
            return
        self.enabled = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="luna-voice")
        self._thread.start()

    def disable(self):
        self.enabled = False
        self._stop.set()
        self._voice_conv_id = None
        self._set_state(VoiceState.IDLE)

    def toggle(self) -> bool:
        if self.enabled:
            self.disable()
        else:
            self.enable()
        return self.enabled

    # ── model loading ──────────────────────────────────────────────────────────

    def _ensure_models(self):
        if self._models_ready:
            return
        if not self.VOSK_DIR.exists():
            self._download_vosk()
        from vosk import Model
        self._vosk_model = Model(str(self.VOSK_DIR))
        # Speech-to-text is the shared local engine (backend/services/stt.py),
        # the same one the desktop mic button and mobile endpoint use.
        stt.ensure_loaded()
        self._init_pygame()
        self._models_ready = True

    def _init_pygame(self):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
            self._pygame_ready = True
        except Exception as e:
            print(f"[voice] pygame init skipped: {e}")

    def _download_vosk(self):
        import urllib.request, zipfile
        Path("data").mkdir(exist_ok=True)
        zip_path = Path("data/vosk-model.zip")
        print("[voice] Downloading Vosk small-en model (~40 MB) — one-time setup...")
        urllib.request.urlretrieve(self.VOSK_URL, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            top = z.namelist()[0].split("/")[0]
            z.extractall("data/")
        Path(f"data/{top}").rename(self.VOSK_DIR)
        zip_path.unlink(missing_ok=True)
        print("[voice] Vosk model ready.")

    # ── main loop ──────────────────────────────────────────────────────────────

    def _run(self):
        try:
            self._ensure_models()
        except Exception as e:
            print(f"[voice] Model load failed: {e}")
            self.enabled = False
            return

        import sounddevice as sd
        from vosk import KaldiRecognizer

        try:
            dev = sd.query_devices(kind='input')
            print(f"[voice] Input device: {dev['name']}  "
                  f"(max channels: {dev['max_input_channels']}, "
                  f"default sr: {dev['default_samplerate']})")
        except Exception as e:
            print(f"[voice] Could not query input device: {e}")

        audio_q: queue.Queue[bytes] = queue.Queue()

        def mic_cb(indata, frames, t, status):
            if status:
                print(f"[voice] mic status: {status}")
            audio_q.put(bytes(indata))

        self._set_state(VoiceState.LISTENING)
        print(f"[voice] Listening for wake words: {self._WAKE_PHRASES}...")

        try:
            with sd.RawInputStream(
                samplerate=self.SAMPLE_RATE, channels=1,
                dtype="int16", blocksize=4000, callback=mic_cb,
            ):
                print("[voice] Microphone opened OK")
                wake_rec = KaldiRecognizer(self._vosk_model, self.SAMPLE_RATE)

                while not self._stop.is_set():
                    try:
                        chunk = audio_q.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    triggered = False

                    if wake_rec.AcceptWaveform(chunk):
                        text = json.loads(wake_rec.Result()).get("text", "").lower()
                        if text:
                            print(f"\r[voice] >> {text}          ")
                        if any(p in text for p in self._WAKE_PHRASES):
                            triggered = True
                    else:
                        partial = json.loads(wake_rec.PartialResult()).get("partial", "").lower()
                        if partial:
                            print(f"\r[voice] .. {partial}", end="", flush=True)
                        if any(p in partial for p in self._WAKE_PHRASES):
                            triggered = True

                    if triggered:
                        from backend.services.away_state import is_away, set_away
                        if is_away():
                            set_away(False)
                            self._fire_ui_event({"type": "away", "action": "off"})
                            try:
                                self._speak("Welcome back, Sahaas!")
                            except Exception:
                                pass
                        self._on_wake(audio_q)
                        while not audio_q.empty():
                            try:
                                audio_q.get_nowait()
                            except queue.Empty:
                                break
                        wake_rec = KaldiRecognizer(self._vosk_model, self.SAMPLE_RATE)
                        if not self._stop.is_set():
                            self._conversation_mode(audio_q)
                        if not self._stop.is_set():
                            self._set_state(VoiceState.LISTENING)

        except sd.PortAudioError as e:
            print(f"[voice] Microphone error: {e}")
            print("[voice] Check Windows Settings → Privacy → Microphone and allow Python.")
        except Exception as e:
            print(f"[voice] Mic stream error: {e}")

        self._set_state(VoiceState.IDLE)

    # ── follow-up conversation window ─────────────────────────────────────────

    def _conversation_mode(self, audio_q: queue.Queue[bytes]):
        from backend.services.away_state import is_away
        TIMEOUT = 240
        idle    = 0
        self._set_state(VoiceState.FOLLOWUP)
        print("[voice] Follow-up window open (60 s)...")

        while idle < TIMEOUT and not self._stop.is_set() and not is_away():
            try:
                chunk = audio_q.get(timeout=0.5)
            except queue.Empty:
                idle += 1
                continue

            rms = float(np.sqrt(np.mean(
                np.frombuffer(chunk, dtype=np.int16).astype(np.float32) ** 2
            )))

            if rms < self.RMS_THRESHOLD:
                idle += 1
                continue

            print("[voice] Follow-up speech detected")
            self._on_wake(audio_q, first_chunk=chunk)
            idle = 0
            while not audio_q.empty():
                try:
                    audio_q.get_nowait()
                except queue.Empty:
                    break
            self._set_state(VoiceState.FOLLOWUP)

        print("[voice] Follow-up window closed — back to wake word")
        self._voice_conv_id = None  # fresh conversation on next wake

    # ── wake → record command ─────────────────────────────────────────────────

    def _on_wake(self, audio_q: queue.Queue[bytes], first_chunk: bytes | None = None):
        self._set_state(VoiceState.ACTIVE)

        if first_chunk is None:
            while not audio_q.empty():
                try:
                    audio_q.get_nowait()
                except queue.Empty:
                    break

        frames: list[bytes] = []
        if first_chunk is not None:
            frames.append(first_chunk)

        silent = 0
        speech_started    = first_chunk is not None
        pre_speech_chunks = 0

        while len(frames) < self.MAX_CHUNKS:
            if self._stop.is_set():
                return
            try:
                chunk = audio_q.get(timeout=0.5)
            except queue.Empty:
                if not speech_started:
                    pre_speech_chunks += 1
                    if pre_speech_chunks >= self.PRE_SPEECH_WAIT:
                        return
                else:
                    silent += 1
                    if silent >= self.SILENCE_LIMIT:
                        break
                continue

            rms = float(np.sqrt(np.mean(
                np.frombuffer(chunk, dtype=np.int16).astype(np.float32) ** 2
            )))

            if not speech_started:
                if rms >= self.RMS_THRESHOLD:
                    speech_started = True
                else:
                    pre_speech_chunks += 1
                    if pre_speech_chunks >= self.PRE_SPEECH_WAIT:
                        return
                    continue

            frames.append(chunk)
            silent = silent + 1 if rms < self.RMS_THRESHOLD else 0
            if speech_started and silent >= self.SILENCE_LIMIT:
                break

        try:
            if not frames:
                return
            self._set_state(VoiceState.PROCESSING)
            raw_audio = b"".join(frames)

            pcm_arr         = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
            speech_duration = len(raw_audio) / (self.SAMPLE_RATE * 2)
            volume_rms      = float(np.sqrt(np.mean(pcm_arr ** 2))) / 32768.0
            voice_emotion   = self._analyze_emotion(raw_audio)
            if voice_emotion != "neutral":
                print(f"[voice] Detected emotion: {voice_emotion}")

            transcript = self._transcribe(raw_audio)
            word_count      = len(transcript.split())
            speech_speed_wpm = (word_count / speech_duration * 60) if speech_duration > 0.5 else 0.0
            for _phrase in self._WAKE_PHRASES:
                transcript = re.sub(
                    rf'^\s*{re.escape(_phrase)}[.,!?]?\s*',
                    '', transcript, flags=re.IGNORECASE,
                ).strip()
            print(f"[voice] Heard: {transcript!r}")

            _EXIT = frozenset({"shut down luna", "shutdown luna", "close luna", "exit luna", "quit luna"})
            _WELCOME_BACK = frozenset({
                "guess who's back", "i'm back", "i am back", "i'm home", "i am home",
                "honey i'm home", "back home", "i'm back home", "i'm here",
            })
            if transcript.lower().strip('.,!? ') in _WELCOME_BACK:
                try:
                    self._speak("Welcome back, Sahaas!")
                except Exception:
                    pass
                return
            if transcript.lower().strip('.,!? ') in _EXIT:
                print("[voice] Exit command — quitting")
                self._fire_quit()
                self.disable()
                return
            if transcript:
                self._respond_streaming(
                    transcript,
                    voice_emotion=voice_emotion,
                    volume=volume_rms,
                    speech_speed=speech_speed_wpm,
                    speech_duration=speech_duration,
                )
        except Exception as e:
            print(f"[voice] Pipeline error: {e}")
        finally:
            if self.enabled and not self._stop.is_set():
                self._set_state(VoiceState.LISTENING)

    # ── Voice emotion analysis ─────────────────────────────────────────────────

    def _analyze_emotion(self, audio_bytes: bytes) -> str:
        try:
            from backend.services.personality import classify_voice_emotion
            pcm = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            if len(pcm) < self.SAMPLE_RATE // 4:
                return "neutral"

            energy_rms = float(np.sqrt(np.mean(pcm ** 2)))

            signs  = np.sign(pcm)
            zcr    = float(np.mean(np.abs(np.diff(signs)))) * self.SAMPLE_RATE / 2
            pitch_hz = zcr

            try:
                import librosa
                f0, voiced, _ = librosa.pyin(
                    pcm / 32768.0, fmin=60, fmax=400, sr=self.SAMPLE_RATE,
                )
                valid = f0[voiced > 0]
                if len(valid):
                    pitch_hz = float(np.median(valid))
            except Exception:
                pass

            frame_size  = int(self.SAMPLE_RATE * 0.02)
            frames      = [pcm[i:i+frame_size] for i in range(0, len(pcm) - frame_size, frame_size)]
            rms_env     = np.array([np.sqrt(np.mean(f**2)) for f in frames])
            threshold   = rms_env.mean() * 0.5
            voiced_frames = np.sum(rms_env > threshold)
            total_frames  = len(rms_env)
            pause_ratio   = 1.0 - voiced_frames / max(total_frames, 1)
            duration_s    = len(pcm) / self.SAMPLE_RATE
            speech_rate_wpm = (voiced_frames * 0.02 / 0.2) * (60 / max(duration_s, 1))

            return classify_voice_emotion(
                pitch_hz=pitch_hz,
                energy_rms=energy_rms,
                speech_rate_wpm=speech_rate_wpm,
                pause_ratio=pause_ratio,
            )
        except Exception:
            return "neutral"

    # ── STT ───────────────────────────────────────────────────────────────────

    def _transcribe_elevenlabs(self, audio_path: str) -> str:
        import httpx
        from backend.config import settings

        with open(audio_path, "rb") as f:
            resp = httpx.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": settings.elevenlabs_api_key},
                data={"model_id": settings.elevenlabs_stt_model},
                files={"file": (os.path.basename(audio_path), f, "audio/wav")},
                timeout=30.0,
            )
        resp.raise_for_status()
        return resp.json().get("text", "").strip()

    def _transcribe_local(self, audio_path: str) -> str:
        return stt.transcribe_file(audio_path).text

    def _transcribe_path(self, audio_path: str) -> str:
        from backend.config import settings
        if settings.stt_provider == "elevenlabs" and settings.elevenlabs_api_key:
            try:
                return self._transcribe_elevenlabs(audio_path)
            except Exception as e:
                print(f"[voice] ElevenLabs STT failed ({e}), falling back to Whisper")
        return self._transcribe_local(audio_path)

    def _transcribe(self, audio_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2)
                wf.setframerate(self.SAMPLE_RATE); wf.writeframes(audio_bytes)
            return self._transcribe_path(wav_path)
        finally:
            os.unlink(wav_path)

    def transcribe_file(self, audio_path: str) -> str:
        self._ensure_models()
        return self._transcribe_path(audio_path)

    def collect_response_text(self, text: str) -> str:
        import httpx
        payload: dict     = {"message": text}
        parts: list[str]  = []

        with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)) as client:
            with client.stream(
                "POST", "http://127.0.0.1:8899/api/chat/stream?voice=true", json=payload,
            ) as resp:
                if resp.status_code != 200:
                    raise RuntimeError(f"chat stream returned {resp.status_code}")
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                    except Exception:
                        continue
                    if data.get("type") == "commands":
                        for cmd in data.get("commands", []):
                            if cmd.get("type") == "map":
                                self._fire_ui_event({"type": "map", "action": cmd.get("action", "open"), "query": cmd.get("query")})
                            elif cmd.get("type") == "away":
                                action = cmd.get("action", "on")
                                if action == "on":
                                    from backend.services.away_state import set_away
                                    set_away(True)
                                self._fire_ui_event({"type": "away", "action": action})
                            elif cmd.get("type") == "widget":
                                self._fire_ui_event({"type": "widget", "kind": cmd.get("kind", "summary"), "title": cmd.get("title", "Visual"), "body": cmd.get("body", "")})
                        continue
                    if data.get("type") == "message_part":
                        parts.append(data.get("content", ""))

        return "\n\n".join(part.strip() for part in parts if part.strip())

    # ── LLM → streaming TTS ───────────────────────────────────────────────────

    def _respond_streaming(
        self,
        text: str,
        voice_emotion: str = "neutral",
        volume: float = 0.0,
        speech_speed: float = 0.0,
        speech_duration: float = 0.0,
    ):
        import httpx

        sentence_q: queue.Queue[str | None] = queue.Queue()

        def _llm_producer():
            buf     = ""
            payload: dict = {"message": text}
            if self._voice_conv_id:
                payload["conversation_id"] = self._voice_conv_id
            try:
                headers = {}
                if voice_emotion and voice_emotion != "neutral":
                    headers["X-Voice-Emotion"] = voice_emotion
                if volume > 0:
                    headers["X-Volume"] = str(round(volume, 4))
                if speech_speed > 0:
                    headers["X-Speech-Speed"] = str(round(speech_speed, 1))
                if speech_duration > 0:
                    headers["X-Speech-Duration"] = str(round(speech_duration, 2))

                with httpx.Client(timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)) as client:
                    with client.stream(
                        "POST",
                        "http://127.0.0.1:8899/api/chat/stream?voice=true",
                        json=payload,
                        headers=headers,
                    ) as resp:
                        if resp.status_code != 200:
                            print(f"[voice] LLM error: chat stream returned {resp.status_code}")
                            return
                        for line in resp.iter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                data = json.loads(line[6:])
                            except Exception:
                                continue
                            if data.get("conversation_id") and not self._voice_conv_id:
                                self._voice_conv_id = data["conversation_id"]
                            if data.get("type") == "commands":
                                for cmd in data.get("commands", []):
                                    if cmd.get("type") == "map":
                                        self._fire_ui_event({"type": "map", "action": cmd.get("action", "open"), "query": cmd.get("query")})
                                    elif cmd.get("type") == "away":
                                        action = cmd.get("action", "on")
                                        if action == "on":
                                            from backend.services.away_state import set_away
                                            set_away(True)
                                        self._fire_ui_event({"type": "away", "action": action})
                                    elif cmd.get("type") == "widget":
                                        self._fire_ui_event({
                                            "type": "widget",
                                            "kind": cmd.get("kind", "summary"),
                                            "title": cmd.get("title", "Visual"),
                                            "body": cmd.get("body", ""),
                                        })
                                continue
                            if data.get("type") == "error":
                                print(f"[voice] LLM backend error: {data.get('message', '?')}")
                                continue
                            if data.get("type") != "message_part":
                                continue
                            chunk = data.get("content", "")
                            chunk = re.sub(r'<think>.*?</think>', '', chunk, flags=re.DOTALL)
                            buf  += chunk
                            while True:
                                m = re.search(r'(?<=[.!?])\s+', buf)
                                if not m:
                                    break
                                sentence_q.put(buf[:m.start() + 1].strip())
                                buf = buf[m.end():]
            except Exception as e:
                print(f"[voice] LLM error: {e}")
            finally:
                if buf.strip():
                    sentence_q.put(buf.strip())
                sentence_q.put(None)

        threading.Thread(target=_llm_producer, daemon=True, name="luna-llm").start()

        # Synthesis runs in its own thread, decoupled from playback: while one
        # sentence is being spoken, the next one's audio is already being
        # synthesized in the background instead of waiting its turn — this is
        # what actually cuts the "taking a lot of time to speak back" latency
        # for multi-sentence replies, since synth time overlaps playback time
        # instead of stacking after it.
        audio_q: queue.Queue[tuple[str, str | None] | None] = queue.Queue()

        def _tts_synthesizer():
            from backend.services.tool_runner import strip_tool_call_json
            while True:
                sentence = sentence_q.get()
                if sentence is None or self._stop.is_set():
                    audio_q.put(None)
                    return
                clean = strip_tool_call_json(sentence)
                clean = re.sub(r"\[(?:LAUNCH|TASK|EVENT|SPOTIFY|BROWSE|MAP|WIDGET):[^\]]+\]", "", clean).strip()
                if not clean:
                    continue
                try:
                    mp3_path = self._synthesize(clean)
                except Exception as e:
                    print(f"[voice] TTS synth failed: {e}")
                    mp3_path = None
                audio_q.put((clean, mp3_path))

        threading.Thread(target=_tts_synthesizer, daemon=True, name="luna-tts-synth").start()

        self._set_state(VoiceState.SPEAKING)
        spoken: list[str] = []
        while True:
            item = audio_q.get()
            if item is None:
                break
            if self._stop.is_set():
                break
            clean, mp3_path = item
            spoken.append(clean)
            if mp3_path:
                try:
                    self._play_mp3(mp3_path)
                finally:
                    try:
                        os.unlink(mp3_path)
                    except OSError:
                        pass
            else:
                # Every synth engine failed for this sentence — last-resort
                # inline speak (blocking, no pipelining, but rare).
                try:
                    self._speak_pyttsx3(clean)
                except Exception as e:
                    print(f"[voice] TTS failed: {e}")
        if spoken:
            print(f"[luna] {' '.join(spoken)}")

    # ── TTS ───────────────────────────────────────────────────────────────────

    _TTS_NAMES: dict = {}

    def _tts_normalize(self, text: str) -> str:
        for name, phonetic in self._TTS_NAMES.items():
            text = re.sub(rf'\b{re.escape(name)}\b', phonetic, text, flags=re.IGNORECASE)
        return text

    _barge_in_triggered: bool = False

    def _speak(self, text: str):
        from backend.config import settings

        engines = []
        if settings.tts_provider == "elevenlabs" and settings.elevenlabs_api_key:
            engines.append(self._speak_elevenlabs)
        engines.append(self._speak_edge)
        engines.append(self._speak_pyttsx3)

        last_exc: Exception | None = None
        for engine in engines:
            try:
                engine(text)
                return
            except Exception as e:
                last_exc = e
        if last_exc:
            print(f"[voice] TTS failed: {last_exc}")

    def _synthesize(self, text: str) -> str | None:
        """Synthesize text to a temp mp3 path (caller deletes it), no playback.
        Tries ElevenLabs first if configured, falls back to edge-tts. Returns
        None if every engine failed (caller falls back to inline pyttsx3)."""
        from backend.config import settings

        text = self._tts_normalize(text)
        if settings.tts_provider == "elevenlabs" and settings.elevenlabs_api_key:
            try:
                return self._synthesize_elevenlabs(text)
            except Exception as e:
                print(f"[voice] ElevenLabs TTS failed ({e}), falling back to edge-tts")
        try:
            return self._synthesize_edge(text)
        except Exception as e:
            print(f"[voice] edge-tts failed: {e}")
            return None

    def _play_mp3(self, mp3_path: str):
        import pygame

        self._barge_in_triggered = False
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(mp3_path)
        pygame.mixer.music.play()

        try:
            import sounddevice as sd

            def _barge_check():
                CHUNK = 1024
                with sd.RawInputStream(
                    samplerate=self.SAMPLE_RATE, channels=1,
                    dtype="int16", blocksize=CHUNK,
                ) as stream:
                    while pygame.mixer.music.get_busy() and not self._stop.is_set():
                        data, _ = stream.read(CHUNK)
                        rms = float(np.sqrt(np.mean(
                            np.frombuffer(bytes(data), dtype=np.int16).astype(np.float32) ** 2
                        )))
                        if rms > self.RMS_THRESHOLD * 1.5:
                            self._barge_in_triggered = True
                            pygame.mixer.music.stop()
                            break

            barge_thread = threading.Thread(target=_barge_check, daemon=True)
            barge_thread.start()
        except Exception:
            pass

        while pygame.mixer.music.get_busy():
            if self._stop.is_set() or self._barge_in_triggered:
                pygame.mixer.music.stop()
                break
            time.sleep(0.05)

    def _synthesize_elevenlabs(self, text: str) -> str:
        """Raw ElevenLabs synthesis — expects already-normalized text, returns mp3 path."""
        import httpx
        from backend.config import settings

        resp = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
            headers={"xi-api-key": settings.elevenlabs_api_key, "Accept": "audio/mpeg"},
            json={"text": text, "model_id": settings.elevenlabs_tts_model},
            # Fail fast on network trouble rather than hanging up to 30s before
            # falling back to edge-tts — a short sentence should synthesize
            # well within this.
            timeout=httpx.Timeout(connect=5.0, read=12.0, write=8.0, pool=5.0),
        )
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3 = f.name
            f.write(resp.content)
        return mp3

    def _synthesize_edge(self, text: str) -> str:
        """Raw edge-tts synthesis — expects already-normalized text, returns mp3 path."""
        import edge_tts

        loop = asyncio.new_event_loop()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            mp3 = f.name
        try:
            loop.run_until_complete(
                # Defaults are connect_timeout=10, receive_timeout=60 — a single
                # stalled connection could hang the whole reply for a minute.
                edge_tts.Communicate(
                    text, "en-US-AriaNeural",
                    connect_timeout=5, receive_timeout=15,
                ).save(mp3)
            )
            return mp3
        finally:
            loop.close()

    def _speak_elevenlabs(self, text: str):
        text = self._tts_normalize(text)
        mp3 = self._synthesize_elevenlabs(text)
        try:
            self._play_mp3(mp3)
        finally:
            try:
                os.unlink(mp3)
            except OSError:
                pass

    def _speak_edge(self, text: str):
        text = self._tts_normalize(text)
        mp3 = self._synthesize_edge(text)
        try:
            self._play_mp3(mp3)
        finally:
            try:
                os.unlink(mp3)
            except OSError:
                pass
            try:
                os.unlink(mp3)
            except OSError:
                pass

    def _speak_pyttsx3(self, text: str):
        import pyttsx3
        text   = self._tts_normalize(text)
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        for v in voices:
            if any(n in v.name.lower() for n in ("aria", "zira", "hazel")):
                engine.setProperty("voice", v.id)
                break
        engine.setProperty("rate", 170)
        engine.setProperty("volume", 0.9)
        engine.say(text)
        engine.runAndWait()


voice_service = VoiceService()
