"""User-editable settings: schema, masked reads, validated writes to .env.

One service for every UI (desktop, web). The schema says what can be changed,
how (text / number / select / secret / toggle) and what's allowed; secrets are
never returned in full; writes merge into the env file that actually defines
each key (so .env.personal overrides keep working) and reload settings live.
"""
from __future__ import annotations

import logging
import re
import secrets
from pathlib import Path

import httpx

from server.config import BASE_DIR, DATA_DIR, _env_files, reload_settings, settings

logger = logging.getLogger(__name__)

_LLM_PROVIDERS = ["ollama", "openai-compatible", "nvidia-nim", "anthropic", "google", "groq", "cohere", "mistral"]
_STT_MODELS = ["distil-large-v3.5", "large-v3-turbo", "distil-medium.en", "small.en", "base.en"]

# key, label, section, type, extra
SCHEMA: list[dict] = [
    {"key": "user_name", "label": "Your name", "section": "General", "type": "text",
     "help": "What Luna calls you."},
    {"key": "weather_city", "label": "Home city", "section": "General", "type": "text",
     "help": "Used for weather and “near me” searches."},
    {"key": "weather_timezone", "label": "Time zone", "section": "General", "type": "text",
     "help": "IANA name, e.g. America/Phoenix."},

    {"key": "show_personality_panel", "label": "Personality panel", "section": "Appearance", "type": "toggle",
     "help": "Show Luna's mood, energy and learned conversation style in the sidebar."},

    {"key": "llm_provider", "label": "AI provider", "section": "AI model", "type": "select", "options": _LLM_PROVIDERS},
    {"key": "ollama_model", "label": "Chat model (Ollama)", "section": "AI model", "type": "select",
     "options_from": "ollama_models"},
    {"key": "vision_model", "label": "Image model (Ollama)", "section": "AI model", "type": "select",
     "options_from": "ollama_models", "help": "Reads attached images."},
    {"key": "ollama_base_url", "label": "Ollama URL", "section": "AI model", "type": "text"},
    {"key": "llm_context_window", "label": "Context window (tokens)", "section": "AI model", "type": "number",
     "min": 2048, "max": 131072, "step": 1024, "help": "Bigger remembers more of long chats but uses more GPU memory."},
    {"key": "openai_api_key", "label": "OpenAI-compatible API key", "section": "AI model", "type": "secret"},
    {"key": "openai_model", "label": "OpenAI-compatible model", "section": "AI model", "type": "text"},
    {"key": "anthropic_api_key", "label": "Anthropic API key", "section": "AI model", "type": "secret"},
    {"key": "anthropic_model", "label": "Anthropic model", "section": "AI model", "type": "text"},

    {"key": "stt_provider", "label": "Speech-to-text", "section": "Voice", "type": "select",
     "options": ["whisper", "elevenlabs"], "help": "whisper = local and free; elevenlabs = cloud."},
    {"key": "stt_model", "label": "Whisper model", "section": "Voice", "type": "select", "options": _STT_MODELS,
     "restart": True, "help": "distil-large-v3.5 is the most accurate for English."},
    {"key": "tts_provider", "label": "Text-to-speech", "section": "Voice", "type": "select",
     "options": ["edge", "elevenlabs", "pyttsx3"]},
    {"key": "elevenlabs_api_key", "label": "ElevenLabs API key", "section": "Voice", "type": "secret"},
    {"key": "elevenlabs_voice_id", "label": "ElevenLabs voice ID", "section": "Voice", "type": "text"},

    {"key": "github_token", "label": "GitHub token", "section": "Integrations", "type": "secret",
     "help": "Repository read access (and PR write access for PR features)."},
    {"key": "github_default_repo", "label": "Default GitHub repo", "section": "Integrations", "type": "text",
     "pattern": r"^$|^[\w.-]+/[\w.-]+$", "help": "owner/name"},
    {"key": "spotify_client_id", "label": "Spotify client ID", "section": "Integrations", "type": "text"},
    {"key": "spotify_client_secret", "label": "Spotify client secret", "section": "Integrations", "type": "secret"},
    {"key": "serpapi_api_key", "label": "SerpApi key (store prices)", "section": "Integrations", "type": "secret",
     "help": "Compares prices at Walmart, Costco, Target, Sam's Club and Safeway. Free key at serpapi.com (100 searches a month)."},
    {"key": "shopping_location", "label": "Shopping location", "section": "Integrations", "type": "text",
     "help": "City for local prices, e.g. Phoenix, Arizona, United States. Leave empty for online prices."},
]
_BY_KEY = {field["key"]: field for field in SCHEMA}
TOKEN_PATH = DATA_DIR / "local_api_token"


class SettingsError(ValueError):
    pass


# ── Local access token (guards writes against web pages hitting localhost) ────

def local_api_token() -> str:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        TOKEN_PATH.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    return TOKEN_PATH.read_text(encoding="utf-8").strip()


def token_ok(candidate: str | None) -> bool:
    return bool(candidate) and secrets.compare_digest(candidate.strip(), local_api_token())


# ── Reading ──────────────────────────────────────────────────────────────────

def _mask(value: str) -> str:
    return f"••••{value[-4:]}" if len(value) > 8 else ("••••" if value else "")


async def _ollama_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            r.raise_for_status()
            return sorted(m.get("name", "") for m in r.json().get("models", []) if m.get("name"))
    except (httpx.HTTPError, ValueError):
        return []


async def read_settings() -> dict:
    dynamic = {"ollama_models": await _ollama_models()}
    fields = []
    for spec in SCHEMA:
        value = getattr(settings, spec["key"], "")
        field = {k: v for k, v in spec.items() if k not in ("options_from", "pattern")}
        if spec["type"] == "secret":
            field["value"] = ""
            field["masked"] = _mask(str(value or ""))
            field["is_set"] = bool(value)
        else:
            field["value"] = value
        if spec.get("options_from"):
            options = list(dynamic.get(spec["options_from"], []))
            if value and value not in options:
                options.insert(0, str(value))     # keep the current choice visible
            field["options"] = options
        fields.append(field)
    return {"fields": fields}


# ── Writing ──────────────────────────────────────────────────────────────────

def _validate(key: str, raw) -> str:
    spec = _BY_KEY.get(key)
    if spec is None:
        raise SettingsError(f"“{key}” can't be changed here.")
    value = "" if raw is None else str(raw).strip()
    if "\n" in value or "\r" in value:
        raise SettingsError(f"{spec['label']}: line breaks aren't allowed.")
    if spec["type"] == "number":
        try:
            number = int(float(value))
        except ValueError as e:
            raise SettingsError(f"{spec['label']} must be a number.") from e
        if not spec.get("min", number) <= number <= spec.get("max", number):
            raise SettingsError(f"{spec['label']} must be between {spec['min']} and {spec['max']}.")
        value = str(number)
    elif spec["type"] == "toggle":
        lowered = value.lower()
        if lowered not in ("true", "false"):
            raise SettingsError(f"{spec['label']} must be on or off.")
        value = lowered
    elif spec["type"] == "select" and spec.get("options") and value not in spec["options"]:
        raise SettingsError(f"{spec['label']}: choose one of {', '.join(spec['options'])}.")
    elif spec["type"] == "text" and key.endswith("_url") and value and not re.match(r"^https?://", value):
        raise SettingsError(f"{spec['label']} must start with http:// or https://.")
    if spec.get("pattern") and not re.match(spec["pattern"], value):
        raise SettingsError(f"{spec['label']}: {spec.get('help', 'invalid format')}.")
    return value


def _env_value(value: str) -> str:
    return f'"{value}"' if re.search(r"[\s#'\"]", value) else value


def _defining_file(key: str) -> Path:
    """The last env file that sets the key wins at load time, so edit that one."""
    files = _env_files()
    files = [files] if isinstance(files, str) else list(files)
    chosen = Path(files[0]) if files else BASE_DIR / ".env"
    for name in files:
        path = Path(name)
        if path.exists() and re.search(rf"(?im)^\s*{re.escape(key)}\s*=", path.read_text(encoding="utf-8")):
            chosen = path
    return chosen


def _write_env(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    pending = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        match = next((k for k in pending if k.lower() == name.lower()), None)
        if match:
            lines[i] = f"{name}={_env_value(pending.pop(match))}"   # keep the file's own key casing
    lines.extend(f"{k}={_env_value(v)}" for k, v in pending.items())
    path.write_text(newline.join(lines) + newline, encoding="utf-8")


def update_settings(changes: dict) -> dict:
    """Validate everything first, then write; nothing is written if any value is invalid."""
    clean: dict[str, str] = {}
    for key, raw in (changes or {}).items():
        spec = _BY_KEY.get(key)
        if spec and spec["type"] == "secret" and not str(raw or "").strip():
            continue      # blank secret field = keep the current value
        clean[key] = _validate(key, raw)
    by_file: dict[Path, dict[str, str]] = {}
    for key, value in clean.items():
        by_file.setdefault(_defining_file(key), {})[key] = value
    for path, updates in by_file.items():
        _write_env(path, updates)
    if clean:
        reload_settings()
        logger.info("Settings updated: %s", ", ".join(sorted(clean)))
    return {
        "updated": sorted(clean),
        "restart_required": sorted(k for k in clean if _BY_KEY[k].get("restart")),
    }
