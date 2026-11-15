#!/usr/bin/env bash
# L.U.N.A. one-liner installer
# Usage: curl -fsSL https://raw.githubusercontent.com/luna-ai-project/Luna/main/install.sh | bash
set -euo pipefail

REPO="${LUNA_REPO:-https://github.com/luna-ai-project/Luna.git}"
DIR="Luna"
BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

header() { echo -e "\n${BOLD}${CYAN}$*${RESET}"; }
ok()     { echo -e "${GREEN}  ✓ $*${RESET}"; }
warn()   { echo -e "${YELLOW}  ! $*${RESET}"; }
die()    { echo -e "${RED}  ✗ $*${RESET}"; exit 1; }

echo -e "${BOLD}"
echo "  ██╗     ██╗   ██╗███╗   ██╗ █████╗ "
echo "  ██║     ██║   ██║████╗  ██║██╔══██╗"
echo "  ██║     ██║   ██║██╔██╗ ██║███████║"
echo "  ██║     ██║   ██║██║╚██╗██║██╔══██║"
echo "  ███████╗╚██████╔╝██║ ╚████║██║  ██║"
echo "  ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝"
echo -e "${RESET}  Large Unified Nexus Mind AI\n"

# ── 1. Check requirements ──────────────────────────────────────────────────────
header "Checking requirements..."

command -v docker  >/dev/null 2>&1 || die "Docker not found. Install it from https://docs.docker.com/get-docker/"
ok "Docker: $(docker --version | head -1)"

command -v git >/dev/null 2>&1 || die "Git not found. Install it from https://git-scm.com/"
ok "Git: $(git --version)"

# Docker Compose (v2 plugin or standalone)
if docker compose version >/dev/null 2>&1; then
  ok "Docker Compose: $(docker compose version)"
elif command -v docker-compose >/dev/null 2>&1; then
  ok "Docker Compose (standalone): $(docker-compose --version)"
  COMPOSE_CMD="docker-compose"
else
  die "Docker Compose not found. Install it: https://docs.docker.com/compose/install/"
fi
COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"

# ── 2. Clone or update ────────────────────────────────────────────────────────
header "Setting up L.U.N.A...."

if [ -d "$DIR/.git" ]; then
  warn "Found existing $DIR/ — pulling latest changes."
  cd "$DIR"
  git pull --ff-only
else
  git clone "$REPO" "$DIR"
  cd "$DIR"
fi
ok "Repository ready at $(pwd)"

# ── 3. Configure ─────────────────────────────────────────────────────────────
header "Configuration..."

if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example"
  warn "Edit .env to set your model, location, and optional API keys."
else
  ok ".env already exists — skipping."
fi

# ── 4. Pick a mode ───────────────────────────────────────────────────────────
header "Choose your setup:"
echo "  1) Local  — Ollama runs in Docker  (no cloud, fully private) [default]"
echo "  2) GPU    — Local + NVIDIA GPU passthrough"
echo "  3) Cloud  — OpenAI / Groq / OpenRouter (no Ollama needed)"
echo ""
read -rp "  Enter 1, 2, or 3 [1]: " MODE
MODE="${MODE:-1}"

case "$MODE" in
  2)
    COMPOSE_FILES="-f deploy/compose.yml -f deploy/compose.gpu.yml"
    ok "Mode: Local + GPU"
    warn "Requires: NVIDIA driver + nvidia-container-toolkit on host."
    ;;
  3)
    COMPOSE_FILES="-f deploy/compose.cloud.yml"
    ok "Mode: Cloud LLM"
    warn "Set llm_provider, openai_base_url, openai_api_key, and openai_model in .env."
    ;;
  *)
    COMPOSE_FILES="-f deploy/compose.yml"
    ok "Mode: Local (CPU Ollama)"
    ;;
esac

# ── 5. Pull model if local mode ───────────────────────────────────────────────
if [ "$MODE" != "3" ]; then
  header "Pulling default model..."
  # Read model from .env, default to qwen2.5:7b
  MODEL=$(grep '^ollama_model=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
  MODEL="${MODEL:-qwen2.5:7b}"

  if command -v ollama >/dev/null 2>&1; then
    warn "Ollama found on host — pulling $MODEL locally."
    ollama pull "$MODEL" || warn "Could not pull $MODEL — you can pull it manually after startup."
    ollama pull nomic-embed-text || warn "Could not pull nomic-embed-text — embeddings will be disabled until pulled."
  else
    warn "Ollama not on host — model will be pulled inside Docker on first run."
    warn "This may take several minutes depending on model size."
  fi
fi

# ── 6. Start ──────────────────────────────────────────────────────────────────
header "Starting L.U.N.A...."
# shellcheck disable=SC2086
$COMPOSE_CMD $COMPOSE_FILES up -d --build

# ── 7. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}  L.U.N.A. is running!${RESET}"
echo ""
echo -e "  ${BOLD}Chat UI${RESET}   →  http://localhost:8899"
echo -e "  ${BOLD}API docs${RESET}  →  http://localhost:8899/docs"
echo ""
echo -e "  Logs:    ${CYAN}$COMPOSE_CMD $COMPOSE_FILES logs -f luna${RESET}"
echo -e "  Stop:    ${CYAN}$COMPOSE_CMD $COMPOSE_FILES down${RESET}"
echo ""
echo -e "  Voice, Electron shell, and OS automation require the desktop install."
echo -e "  See https://github.com/luna-ai-project/Luna for full docs."
echo ""
