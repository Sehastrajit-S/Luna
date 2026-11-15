from __future__ import annotations

import asyncio
import unittest
from unittest import mock

import httpx

from tests.tools import _bootstrap  # noqa: F401


def _fake_ollama(models: dict[str, list[dict]], down: set[str] = frozenset()):
    """MockTransport serving /api/tags and /api/show for several fake servers."""
    def handler(request: httpx.Request) -> httpx.Response:
        server = f"{request.url.scheme}://{request.url.host}:{request.url.port}"
        if server in down:
            raise httpx.ConnectError("down", request=request)
        served = models.get(server, [])
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": m["name"], "digest": m["name"], "details": {"parameter_size": m["size"], "family": m.get("family", "x")}}
                for m in served
            ]})
        if request.url.path == "/api/show":
            import json
            name = json.loads(request.content)["model"]
            for m in served:
                if m["name"] == name:
                    return httpx.Response(200, json={"capabilities": m["caps"]})
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


class LLMSelectorTests(unittest.TestCase):
    PC = "http://10.0.0.1:11434"
    FRIEND = "http://10.0.0.2:11434"

    def setUp(self) -> None:
        from backend.config import settings
        from backend.services.llm import selector

        self.settings = settings
        self.selector = selector
        keys = ["llm_provider", "ollama_base_url", "ollama_model", "openai_model", "llm_auto_select",
                "llm_ollama_servers", "llm_model_preference", "llm_fallback_provider"]
        self.original = {k: getattr(settings, k) for k in keys}
        settings.llm_auto_select = True
        settings.llm_ollama_servers = f"{self.PC},{self.FRIEND}"
        settings.llm_model_preference = ""
        settings.llm_fallback_provider = "openai-compatible"
        settings.openai_model = "openrouter/free"
        selector._capability_cache.clear()

    def tearDown(self) -> None:
        for k, v in self.original.items():
            setattr(self.settings, k, v)

    def _select(self, models, down=frozenset()):
        transport = _fake_ollama(models, set(down))
        real_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        with mock.patch.object(self.selector.httpx, "AsyncClient", side_effect=client_factory):
            return asyncio.run(self.selector.select_now())

    def test_parse_params(self) -> None:
        self.assertAlmostEqual(self.selector.parse_params("8.2B"), 8.2)
        self.assertAlmostEqual(self.selector.parse_params("135M"), 0.135)
        self.assertEqual(self.selector.parse_params(""), 0.0)

    def test_picks_bigger_model_across_servers(self) -> None:
        self._select({
            self.PC: [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]}],
            self.FRIEND: [{"name": "qwen3:14b", "size": "14.8B", "caps": ["completion", "tools"]}],
        })
        self.assertEqual(self.settings.llm_provider, "ollama")
        self.assertEqual(self.settings.ollama_base_url, self.FRIEND)
        self.assertEqual(self.settings.ollama_model, "qwen3:14b")

    def test_preference_list_beats_size(self) -> None:
        self.settings.llm_model_preference = "qwen3:8b"
        self._select({
            self.PC: [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]}],
            self.FRIEND: [{"name": "llama3:70b", "size": "70B", "caps": ["completion", "tools"]}],
        })
        self.assertEqual((self.settings.ollama_base_url, self.settings.ollama_model), (self.PC, "qwen3:8b"))

    def test_tool_support_beats_size_and_embeddings_are_skipped(self) -> None:
        self._select({
            self.PC: [
                {"name": "nomic-embed-text", "size": "137M", "caps": ["embedding"]},
                {"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]},
            ],
            self.FRIEND: [{"name": "gemma:27b", "size": "27B", "caps": ["completion"]}],
        })
        self.assertEqual(self.settings.ollama_model, "qwen3:8b")

    def test_same_model_tie_prefers_first_server(self) -> None:
        same = [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]}]
        self._select({self.PC: same, self.FRIEND: same})
        self.assertEqual(self.settings.ollama_base_url, self.PC)

    def test_unreachable_server_is_skipped(self) -> None:
        state = self._select({
            self.PC: [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]}],
            self.FRIEND: [{"name": "qwen3:32b", "size": "32B", "caps": ["completion", "tools"]}],
        }, down={self.FRIEND})
        self.assertEqual(self.settings.ollama_base_url, self.PC)
        self.assertEqual(state.unreachable, [self.FRIEND])

    def test_falls_back_only_when_no_ollama_model(self) -> None:
        self._select({self.PC: [{"name": "nomic-embed-text", "size": "137M", "caps": ["embedding"]}]}, down={self.FRIEND})
        self.assertEqual(self.settings.llm_provider, "openai-compatible")
        self.assertEqual(self.selector.state.source, "fallback")
        # and switches back as soon as a model is served again
        self._select({self.PC: [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]}]})
        self.assertEqual(self.settings.llm_provider, "ollama")
        self.assertEqual(self.selector.state.source, "ollama")


if __name__ == "__main__":
    unittest.main()
