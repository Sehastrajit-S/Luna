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
                    return httpx.Response(200, json={"capabilities": m["caps"], "template": m.get("template", "")})
            return httpx.Response(404, json={"error": "not found"})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


class LLMSelectorTests(unittest.TestCase):
    PC = "http://10.0.0.1:11434"
    FRIEND = "http://10.0.0.2:11434"

    def setUp(self) -> None:
        from server.config import settings
        from server.services.llm import selector

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
        self._tmp = __import__("tempfile").TemporaryDirectory()
        self._override_patch = mock.patch.object(selector, "OVERRIDE_PATH", __import__("pathlib").Path(self._tmp.name) / "o.json")
        self._override_patch.start()

    def tearDown(self) -> None:
        self._override_patch.stop()
        self._tmp.cleanup()
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

    def _override(self, models, down=frozenset(), **body):
        transport = _fake_ollama(models, set(down))
        real_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        with mock.patch.object(self.selector.httpx, "AsyncClient", side_effect=client_factory):
            return asyncio.run(self.selector.set_override(**body))

    def test_manual_choice_bypasses_ranking_until_auto(self) -> None:
        models = {
            self.PC: [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]}],
            self.FRIEND: [{"name": "qwen3:14b", "size": "14.8B", "caps": ["completion", "tools"]}],
        }
        self._override(models, mode="ollama", server=self.PC, model="qwen3:8b")
        self.assertEqual((self.settings.ollama_base_url, self.settings.ollama_model), (self.PC, "qwen3:8b"))
        self.assertEqual(self.selector.status()["mode"], "manual")
        # a later probe keeps the manual choice
        self._select(models)
        self.assertEqual(self.settings.ollama_model, "qwen3:8b")
        self._override(models, mode="auto")
        self.assertEqual(self.settings.ollama_model, "qwen3:14b")
        self.assertEqual(self.selector.status()["mode"], "auto")

    def test_manual_fallback_needs_api_key(self) -> None:
        original = self.settings.openai_api_key
        try:
            self.settings.openai_api_key = ""
            with self.assertRaises(ValueError):
                self._override({}, mode="fallback")
            self.settings.openai_api_key = "sk-test"
            self._override({self.PC: [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools"]}]}, mode="fallback")
            self.assertEqual(self.settings.llm_provider, "openai-compatible")
        finally:
            self.settings.openai_api_key = original

    def test_manual_choice_rejects_unknown_server(self) -> None:
        with self.assertRaises(ValueError):
            self._override({}, mode="ollama", server="http://evil:11434", model="x")

    def test_server_labels(self) -> None:
        self.settings.llm_ollama_servers = f"My PC={self.PC}, {self.FRIEND}"
        self.assertEqual(self.selector.servers(), [self.PC, self.FRIEND])
        self.assertEqual(self.selector.server_label(self.PC), "My PC")
        self.assertEqual(self.selector.server_label(self.FRIEND), "10.0.0.2")

    HYBRID = "{{ if (and $.IsThinkSet (not $.Think)) }}<think>\n\n</think>{{ end }}"
    THINKING_ONLY = "{{ if $.IsThinkSet }}<think>{{ .Thinking }}</think>{{ end }}<think>"

    def test_thinking_only_model_gets_think_true_and_extra_budget(self) -> None:
        self._select({self.PC: [{"name": "qwen3:4b", "size": "4.0B", "caps": ["completion", "tools", "thinking"],
                                 "template": self.THINKING_ONLY}]})
        self.assertTrue(self.selector.state.always_thinks)
        think, predict = self.selector.ollama_think_options("qwen3:4b", 1024)
        self.assertTrue(think)
        self.assertEqual(predict, 1024 + self.settings.llm_thinking_budget)
        # another model (e.g. coding_model) is not affected
        self.assertEqual(self.selector.ollama_think_options("qwen2.5-coder:7b", 1024), (False, 1024))

    def test_hybrid_thinking_model_keeps_think_false(self) -> None:
        self._select({self.PC: [{"name": "qwen3:8b", "size": "8.2B", "caps": ["completion", "tools", "thinking"],
                                 "template": self.HYBRID}]})
        self.assertFalse(self.selector.state.always_thinks)
        self.assertEqual(self.selector.ollama_think_options("qwen3:8b", 1024), (False, 1024))

    def test_model_missing_detection(self) -> None:
        self.assertTrue(self.selector.is_model_missing(404, '{"error":"model \'qwen3:8b\' not found"}'))
        self.assertTrue(self.selector.is_model_missing(404))
        self.assertFalse(self.selector.is_model_missing(500, "boom"))


if __name__ == "__main__":
    unittest.main()
