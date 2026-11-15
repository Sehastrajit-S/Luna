"""LLMClient — unified streaming + completion interface over all providers."""
import logging
import logging
from typing import AsyncGenerator

import httpx

from backend.config import settings
from backend.services.llm.providers import (
    _TIMEOUT,
    _provider,
    _stream_ollama,
    _stream_openai_compatible,
    _stream_anthropic,
    _stream_google,
    _stream_groq,
    _stream_cohere,
    _stream_mistral,
    _complete_ollama,
    _complete_openai,
    _complete_anthropic,
    _complete_google,
    _openai_headers,
)

logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


class LLMClient:
    """Unified streaming + completion client.  Provider is read from settings at call time."""

    def __init__(self):
        self.timeout = _TIMEOUT

    @property
    def provider(self) -> str:
        return _provider()

    @property
    def model(self) -> str:
        p = self.provider
        mapping = {
            "ollama": settings.ollama_model,
            "openai-compatible": settings.openai_model,
            "nvidia-nim": settings.nvidia_nim_model,
            "anthropic": settings.anthropic_model,
            "google": settings.google_model,
            "groq": settings.groq_model,
            "cohere": settings.cohere_model,
            "mistral": settings.mistral_model,
        }
        return mapping.get(p, settings.ollama_model)

    async def is_available(self) -> bool:
        p = self.provider
        if p == "ollama":
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                    r = await client.get(f"{settings.ollama_base_url}/api/tags")
                    return r.status_code == 200
            except (httpx.HTTPError, OSError) as e:
                logger.debug("Ollama availability check failed: %s", e)
                return False
        if p == "openai-compatible":
            return bool(settings.openai_api_key and settings.openai_base_url and settings.openai_model)
        if p == "nvidia-nim":
            return bool(settings.nvidia_nim_base_url and settings.nvidia_nim_model and settings.nvidia_nim_api_key)
        if p == "anthropic":
            return bool(settings.anthropic_api_key)
        if p == "google":
            return bool(settings.google_api_key)
        if p == "groq":
            return bool(settings.groq_api_key)
        if p == "cohere":
            return bool(settings.cohere_api_key)
        if p == "mistral":
            return bool(settings.mistral_api_key)
        return False

    def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str,
        *,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        p = self.provider
        if p == "ollama":
            return _stream_ollama(
                messages, system_prompt,
                num_ctx=num_ctx, num_predict=num_predict, temperature=temperature,
            )
        if p == "openai-compatible":
            return _stream_openai_compatible(
                messages, system_prompt,
                base_url=settings.openai_base_url,
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                temperature=temperature,
            )
        if p == "nvidia-nim":
            return _stream_openai_compatible(
                messages, system_prompt,
                base_url=settings.nvidia_nim_base_url,
                api_key=settings.nvidia_nim_api_key,
                model=settings.nvidia_nim_model,
                temperature=temperature,
            )
        if p == "anthropic":
            return _stream_anthropic(messages, system_prompt, temperature=temperature)
        if p == "google":
            return _stream_google(messages, system_prompt, temperature=temperature)
        if p == "groq":
            return _stream_groq(messages, system_prompt, temperature=temperature)
        if p == "cohere":
            return _stream_cohere(messages, system_prompt, temperature=temperature)
        if p == "mistral":
            return _stream_mistral(messages, system_prompt, temperature=temperature)
        return _stream_ollama(messages, system_prompt, temperature=temperature)

    async def complete(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        p = self.provider
        if p == "ollama":
            return await _complete_ollama(prompt, system, temperature)
        if p == "openai-compatible":
            return await _complete_openai(
                prompt, system, temperature,
                settings.openai_base_url, settings.openai_api_key, settings.openai_model,
            )
        if p == "nvidia-nim":
            return await _complete_openai(
                prompt, system, temperature,
                settings.nvidia_nim_base_url, settings.nvidia_nim_api_key, settings.nvidia_nim_model,
            )
        if p == "anthropic":
            return await _complete_anthropic(prompt, system, temperature)
        if p == "google":
            return await _complete_google(prompt, system, temperature)
        if p == "groq":
            return await _complete_openai(
                prompt, system, temperature,
                "https://api.groq.com/openai/v1", settings.groq_api_key, settings.groq_model,
            )
        if p == "cohere":
            return await _complete_openai(
                prompt, system, temperature,
                "https://api.cohere.com/v2", settings.cohere_api_key, settings.cohere_model,
            )
        if p == "mistral":
            return await _complete_openai(
                prompt, system, temperature,
                "https://api.mistral.ai/v1", settings.mistral_api_key, settings.mistral_model,
            )
        return await _complete_ollama(prompt, system, temperature)

    async def embed(self, text: str) -> list[float]:
        if settings.embedding_provider.strip().lower() == "openai-compatible":
            if settings.openai_api_key:
                try:
                    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                        r = await client.post(
                            f"{settings.openai_base_url.rstrip('/')}/embeddings",
                            headers=_openai_headers(settings.openai_api_key),
                            json={"model": settings.openai_embed_model, "input": text},
                        )
                        r.raise_for_status()
                        data = r.json()
                        return data.get("data", [{}])[0].get("embedding", [])
                except httpx.HTTPError as exc:
                    # Memory is an enhancement, not a reason to lose chat.
                    # Fall through to the local embedding model when the
                    # hosted provider is rate-limited or unavailable.
                    logger.warning("OpenAI embeddings unavailable; using local fallback: %s", exc)

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{settings.ollama_embed_base_url or settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embed_model, "input": text},
            )
            if r.status_code == 200:
                data = r.json()
                if "embeddings" in data:
                    return data["embeddings"][0]
                return data.get("embedding", [])
        return []


# Keep the historical import name so existing routers/services need zero churn.
ollama = LLMClient()
