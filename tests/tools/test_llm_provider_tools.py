from __future__ import annotations

import unittest

from tests.tools import _bootstrap  # noqa: F401


class LLMProviderToolTests(unittest.TestCase):
    def test_nvidia_nim_provider_status_and_model(self) -> None:
        from backend.config import settings
        from backend.services.llm import ollama

        original = {
            "llm_provider": settings.llm_provider,
            "nvidia_nim_api_key": settings.nvidia_nim_api_key,
            "nvidia_nim_base_url": settings.nvidia_nim_base_url,
            "nvidia_nim_model": settings.nvidia_nim_model,
        }
        try:
            settings.llm_provider = "nvidia-nim"
            settings.nvidia_nim_api_key = "test-key"
            settings.nvidia_nim_base_url = "https://integrate.api.nvidia.com/v1"
            settings.nvidia_nim_model = "test/model"

            self.assertEqual(ollama.provider, "nvidia-nim")
            self.assertEqual(ollama.model, "test/model")
        finally:
            for key, value in original.items():
                setattr(settings, key, value)

    def test_nvidia_nim_stream_uses_openai_compatible_generator(self) -> None:
        from backend.config import settings
        from backend.services.llm import ollama

        original = settings.llm_provider
        try:
            settings.llm_provider = "nvidia-nim"
            stream = ollama.stream_chat([{"role": "user", "content": "hi"}], "system")
            self.assertTrue(hasattr(stream, "__aiter__"))
        finally:
            settings.llm_provider = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
