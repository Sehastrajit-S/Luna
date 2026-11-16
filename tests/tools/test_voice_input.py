import asyncio
import io
import unittest
from unittest import mock


class LocalSttTests(unittest.TestCase):
    def test_gpu_path_that_cannot_run_falls_back_to_cpu(self) -> None:
        from server.services import stt as stt_module

        loaded = []

        class FakeModel:
            def __init__(self, name, device, compute_type):
                loaded.append((name, device))
                self.device = device

            def transcribe(self, audio, **kwargs):
                if self.device == "cuda":
                    raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
                return iter([mock.Mock(text=" hello there ")]), mock.Mock(duration=1.5)

        engine = stt_module.LocalSTT()
        with mock.patch("faster_whisper.WhisperModel", FakeModel):
            result = engine.transcribe_file("clip.webm")
        self.assertEqual(loaded[0][1], "cuda")                      # tried the GPU first
        self.assertEqual(loaded[-1], (stt_module.settings.stt_cpu_model, "cpu"))
        self.assertEqual((result.text, result.device), ("hello there", "cpu"))

    def test_mid_session_gpu_failure_finishes_on_cpu(self) -> None:
        from server.services import stt as stt_module

        class FakeModel:
            calls = 0

            def __init__(self, name, device, compute_type):
                self.device = device

            def transcribe(self, audio, **kwargs):
                FakeModel.calls += 1
                if self.device == "cuda" and FakeModel.calls > 1:   # warm-up passes, real run hits OOM
                    raise RuntimeError("CUDA failed with error out of memory")
                return iter([mock.Mock(text="ok")]), mock.Mock(duration=1.0)

        engine = stt_module.LocalSTT()
        with mock.patch("faster_whisper.WhisperModel", FakeModel):
            result = engine.transcribe_file("clip.webm")
        self.assertEqual((result.text, result.device), ("ok", "cpu"))


class TranscribeEndpointTests(unittest.TestCase):
    def _post(self, content: bytes, filename: str = "dictation.webm"):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from server.routers.voice import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app).post("/api/voice/transcribe", files={"audio": (filename, io.BytesIO(content), "audio/webm")})

    def test_returns_text_and_timing(self) -> None:
        from server.services.stt import Transcript

        seen = {}

        def fake_transcribe(path):
            seen["path"] = path
            return Transcript(text="find me papers on RAG", duration_s=2.4, elapsed_ms=180, model="m", device="cuda")

        with mock.patch("server.services.stt.stt.transcribe_file", side_effect=fake_transcribe):
            response = self._post(b"\x1a\x45\xdf\xa3" + b"0" * 5000)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "find me papers on RAG")
        self.assertTrue(seen["path"].endswith(".webm"))                 # original format kept for the decoder

    def test_empty_and_oversized_uploads_are_rejected(self) -> None:
        from server.routers import voice

        self.assertEqual(self._post(b"").status_code, 400)
        with mock.patch.object(voice, "MAX_DICTATION_BYTES", 1000):
            self.assertEqual(self._post(b"0" * 5000).status_code, 413)

    def test_unknown_extensions_are_treated_as_webm(self) -> None:
        from server.services.stt import Transcript

        seen = {}
        with mock.patch("server.services.stt.stt.transcribe_file",
                        side_effect=lambda p: seen.setdefault("p", p) and Transcript("x", 1, 1, "m", "cpu")):
            self._post(b"0" * 3000, filename="evil.exe")
        self.assertTrue(seen["p"].endswith(".webm"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
