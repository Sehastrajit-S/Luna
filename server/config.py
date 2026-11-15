from pydantic_settings import BaseSettings
from pydantic import field_validator
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("LUNA_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)

# Model downloads (faster-whisper via Hugging Face; anything using torch
# hub) default to the user's home on C:. Keep them next to Luna's data unless
# the machine already points them somewhere.
os.environ.setdefault("HF_HOME", str(DATA_DIR / "models" / "huggingface"))
os.environ.setdefault("TORCH_HOME", str(DATA_DIR / "models" / "torch"))


def _read_env_value(path: Path, key: str) -> str | None:
    if not path.exists():
        return None

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip().lower() == key:
            return value.strip().strip("\"'")
    return None


def _selected_variant() -> str:
    return (
        os.getenv("LUNA_VARIANT")
        or os.getenv("luna_variant")
        or _read_env_value(BASE_DIR / ".env", "luna_variant")
        or "personal"
    ).strip().lower()


def _env_files() -> tuple[str, ...] | str:
    explicit = os.getenv("LUNA_ENV_FILE")
    if explicit:
        return explicit

    files = [str(BASE_DIR / ".env")]
    variant = _selected_variant()
    if variant in {"personal", "business"}:
        variant_file = BASE_DIR / f".env.{variant}"
        if variant_file.exists():
            files.append(str(variant_file))
    return tuple(files)


class Settings(BaseSettings):
    app_name: str = "Luna"
    host: str = "127.0.0.1"
    port: int = 8899
    debug: bool = False

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"     # DEBUG | INFO | WARNING | ERROR
    log_format: str = "text"    # text | json (json for log aggregation)

    # ── LLM — provider selection ──────────────────────────────────────────────
    # Values: ollama | openai-compatible | nvidia-nim | anthropic | google | groq | cohere | mistral
    llm_provider: str = "ollama"

    # Ollama (local, default)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"
    # Ollama server for embeddings when it differs from the chat server (blank = ollama_base_url).
    ollama_embed_base_url: str = ""

    # Priority-based model selection (opt-in, services/llm/selector.py): probe
    # llm_ollama_servers, use the best chat model any of them serves, and switch
    # to llm_fallback_provider only when no Ollama model is available.
    llm_auto_select: bool = False
    llm_ollama_servers: str = ""        # comma-separated base URLs; earlier wins ties (blank = ollama_base_url)
    llm_model_preference: str = ""      # comma-separated Ollama model names, best first (unlisted: by size)
    llm_fallback_provider: str = "openai-compatible"
    llm_select_interval: int = 60       # seconds between probes
    llm_thinking_budget: int = 4096     # extra output tokens for thinking-only models (their reasoning counts too)

    # Context window (tokens) for chat requests. Requests are fitted to it
    # explicitly (services/llm/context_window.py) instead of letting the model
    # server truncate silently. Sent to Ollama as a fixed num_ctx — Ollama
    # reloads the model whenever num_ctx changes between requests.
    llm_context_window: int = 16384
    llm_max_output_tokens: int = 1024
    # Agent loop: native tool calling, repeated model → tools → model steps.
    # Off falls back to the single-shot pipeline (tool JSON parsed from text).
    agent_loop_enabled: bool = True
    # Scheduler + lifecycle processes (reminders, check-ins). Off for test instances.
    background_jobs_enabled: bool = True
    # One local JSONL line per chat turn (route, tools, rule decisions) to train a router.
    decision_log_enabled: bool = True
    agent_max_steps: int = 10
    agent_tool_result_chars: int = 6000      # per tool result sent back to the model
    agent_confirm_timeout_s: int = 120       # how long a risky tool waits for approval

    # Vision model for attached images (Ollama). If it isn't pulled, the next
    # installed one of qwen2.5vl → llama3.2-vision → gemma3 → moondream is used.
    vision_model: str = "qwen2.5vl:7b"

    # OpenAI / OpenAI-compatible (LM Studio, Jan.ai, llama.cpp, OpenRouter, etc.)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    # NVIDIA NIM (OpenAI-compatible /v1/chat/completions)
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_api_key: str = ""
    nvidia_nim_model: str = "meta/llama-3.1-8b-instruct"

    # Anthropic Claude (native)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # Google Gemini (native)
    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash"

    # Groq (ultra-fast cloud inference, native)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Cohere (native)
    cohere_api_key: str = ""
    cohere_model: str = "command-r-plus"

    # Mistral AI (native)
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"

    # Embedding provider: ollama | openai-compatible
    embedding_provider: str = "ollama"

    # ── Voice: STT & TTS ──────────────────────────────────────────────────────
    # tts_provider: edge (free, local, default) | elevenlabs (cloud, higher quality, paid)
    tts_provider: str = "edge"
    # stt_provider: whisper (free, local, default) | elevenlabs (cloud Scribe model)
    stt_provider: str = "whisper"
    # Local STT (faster-whisper). distil-large-v3.5: best English accuracy in the
    # Whisper family at ~0.8 GB VRAM; distil-small.en is the CPU fallback.
    stt_model: str = "distil-large-v3.5"
    stt_cpu_model: str = "distil-small.en"
    stt_language: str = "en"
    # elevenlabs.io → Profile → API keys
    elevenlabs_api_key: str = ""
    # elevenlabs.io → Voices → pick a voice → copy its Voice ID (default = "Rachel")
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    elevenlabs_tts_model: str = "eleven_turbo_v2_5"
    elevenlabs_stt_model: str = "scribe_v1"

    # ── Coding agent ───────────────────────────────────────────────────────────
    # coding_provider: which LLM provider to use for the coding agent.
    #   Empty string (default) → same as llm_provider.
    #   Set explicitly to use a different provider just for coding, e.g. "groq".
    coding_provider: str = ""
    # coding_model: Ollama model name (used when coding_provider resolves to "ollama").
    #   Examples: qwen2.5-coder:7b  deepseek-coder-v2:16b  codellama:7b
    coding_model: str = "qwen2.5-coder:7b"
    coding_max_iterations: int = 20
    coding_shell_timeout: int = 120  # seconds before a shell command is killed

    # ── Database ──────────────────────────────────────────────────────────────
    # Default: SQLite (local, zero-config). Set db_url to switch backends.
    #
    # SQLite (default — leave db_url blank):
    #   stored at db_path, no extra packages required
    #
    # PostgreSQL / Supabase:
    #   db_url=postgresql+psycopg2://user:pass@host:5432/luna
    #   pip install psycopg2-binary
    #
    # MySQL / MariaDB:
    #   db_url=mysql+pymysql://user:pass@host:3306/luna
    #   pip install pymysql
    #
    # MS SQL Server:
    #   db_url=mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server
    #   pip install pyodbc
    #
    # After changing db_url, run:  alembic upgrade head
    db_url: str = ""                         # empty = use SQLite at db_path
    db_path: str = str(DATA_DIR / "luna.db") # SQLite file (ignored when db_url is set)
    db_pool_size: int = 10                   # max persistent connections (not used for SQLite)
    db_max_overflow: int = 20                # extra connections above pool_size
    db_pool_timeout: int = 30               # seconds to wait for a connection
    db_pool_recycle: int = 1800             # recycle connections after 30 min (prevents stale TCP)
    db_echo: bool = False                   # log every SQL statement (use only for debugging)

    # ── Paths ─────────────────────────────────────────────────────────────────
    chroma_path: str = str(DATA_DIR / "chroma")
    frontend_dist: str = str(BASE_DIR / "interfaces" / "web" / "dist")
    # Browser UI: the same renderer the desktop app loads, served at "/".
    web_ui_dir: str = str(BASE_DIR / "interfaces" / "desktop" / "src" / "renderer")
    web_ui_resources: str = str(BASE_DIR / "interfaces" / "desktop" / "resources")

    # ── Memory ────────────────────────────────────────────────────────────────
    max_conversation_history: int = 30
    memory_retrieval_count: int = 6
    fact_extraction_interval: int = 5

    # ── Auth & access ─────────────────────────────────────────────────────────
    # Production: set to a long random string; used to sign per-user JWT tokens.
    jwt_secret: str = ""
    jwt_expiry_hours: int = 720  # 30 days
    # One-time secret for bootstrapping the first admin JWT (see /api/admin/bootstrap).
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Remove from .env after first admin token is created.
    admin_bootstrap_secret: str = ""

    # ── Rate limiting (production) ────────────────────────────────────────────
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60        # requests per user per minute
    rate_limit_burst: int = 20             # additional burst allowance

    # ── External data APIs ────────────────────────────────────────────────────
    the_news_api: str = ""
    open_weather: str = ""
    alpha_vantage: str = ""
    weather_lat: float = 40.7128
    weather_lon: float = -74.0060
    weather_city: str = "New York"
    weather_timezone: str = "America/New_York"

    # ── Messaging channels (OpenClaw-style) ───────────────────────────────────
    # Telegram: set bot token + run  /setwebhook  to point at /api/channels/telegram
    telegram_bot_token: str = ""
    # Discord: set bot token + configure interactions endpoint /api/channels/discord
    discord_bot_token: str = ""
    discord_public_key: str = ""           # for signature verification
    # Slack: set bot token + signing secret; Events API → /api/channels/slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_default_channel: str = ""         # Optional channel ID for history lookup
    # GitHub: PAT for API calls, webhook secret for event signature verification
    github_token: str = ""                  # Personal Access Token (repo scope)
    github_webhook_secret: str = ""         # Secret set in GitHub webhook settings
    github_default_repo: str = ""           # e.g. "owner/repo" — default for tool calls
    github_notify_slack_channel: str = ""   # Slack channel ID for event notifications
    github_notify_telegram_chat_id: str = "" # Telegram chat ID for event notifications

    # Jira Cloud: used by enterprise bugfix workflows
    jira_base_url: str = ""                  # e.g. https://company.atlassian.net
    jira_email: str = ""
    jira_api_token: str = ""

    # Enterprise workflow defaults
    enterprise_workflow_workspace_root: str = str(BASE_DIR)
    enterprise_workflow_base_branch: str = "main"
    enterprise_workflow_test_command: str = "python -W ignore -m unittest discover -s tests/tools -p \"test_*.py\" -v"

    # Google Workspace / Microsoft 365 (OAuth access tokens; opt-in)
    google_workspace_client_id: str = ""
    google_workspace_client_secret: str = ""
    google_workspace_refresh_token: str = ""
    google_workspace_access_token: str = ""
    microsoft_workspace_client_id: str = ""
    microsoft_workspace_client_secret: str = ""
    microsoft_workspace_tenant_id: str = "common"
    microsoft_workspace_refresh_token: str = ""
    microsoft_workspace_access_token: str = ""

    # ── Spotify (personal variant — opt-in) ──────────────────────────────────
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    # ── Health Platforms (opt-in) ────────────────────────────────────────────
    # Fitbit (OAuth2) — app.fitbit.com/oauth2/applications
    fitbit_client_id: str = ""
    fitbit_client_secret: str = ""
    fitbit_access_token: str = ""
    fitbit_refresh_token: str = ""

    # Google Fit (OAuth2) — separate from Workspace; Google Cloud Console
    google_fit_client_id: str = ""
    google_fit_client_secret: str = ""
    google_fit_access_token: str = ""
    google_fit_refresh_token: str = ""

    # Oura Ring (Personal Access Token) — cloud.ouraring.com/user/api-tokens
    oura_api_key: str = ""

    # Withings (OAuth2) — developer.withings.com
    withings_client_id: str = ""
    withings_client_secret: str = ""
    withings_access_token: str = ""
    withings_refresh_token: str = ""

    # Garmin Connect (credentials for garth library)
    garmin_email: str = ""
    garmin_password: str = ""

    # Apple Health / Samsung Health — these platforms have no public REST API.
    # Use the "Health Auto Export" iOS app or a compatible Android exporter
    # to push data to Luna's webhook endpoint: POST /api/health/webhook/apple
    # or POST /api/health/webhook/samsung
    # Set a shared secret to authenticate inbound webhooks.
    health_webhook_secret: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins. Empty = localhost defaults.
    # Example: "http://localhost:5173,https://luna.example.com"
    cors_origins: str = ""

    # ── Skills marketplace ────────────────────────────────────────────────────
    # URL of the curated registry index. Override with a self-hosted JSON file
    # to run a private/team marketplace.
    skill_registry_url: str = ""

    # ── Variant ───────────────────────────────────────────────────────────────
    # personal  — casual companion, voice, desktop automation, single user
    # business  — professional team assistant, multi-user JWT, rate limiting on
    luna_variant: str = "personal"

    # ── Luna persona ──────────────────────────────────────────────────────────
    luna_name: str = "L.U.N.A."
    user_name: str = "friend"

    # Business variant config
    business_name: str = ""        # e.g. "Acme Corp"
    business_description: str = "" # e.g. "a SaaS company building developer tools"
    business_tone: str = "professional"  # professional | friendly | technical | concise

    # ── RL ────────────────────────────────────────────────────────────────────
    rl_learning_rate: float = 0.08
    rl_decay: float = 0.995

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "on"}:
                return True
        return value

    class Config:
        env_file = _env_files()
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def reload_settings() -> None:
    """Re-read the env file(s) and update the global settings object in-place."""
    fresh = Settings()
    for field in Settings.model_fields:
        try:
            setattr(settings, field, getattr(fresh, field))
        except Exception:
            pass


def write_env_value(key: str, value: str) -> None:
    """Update or append KEY=value in the primary .env file (BASE_DIR/.env)."""
    env_path = BASE_DIR / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    key_upper = key.upper()
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, _ = stripped.partition("=")
        if name.strip().upper() == key_upper:
            lines[i] = f"{key_upper}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key_upper}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
