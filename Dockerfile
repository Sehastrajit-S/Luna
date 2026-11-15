# ── Luna backend + web UI ──────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL org.opencontainers.image.title="L.U.N.A."
LABEL org.opencontainers.image.description="Large Unified Nexus Mind AI — local-first AI companion"
LABEL org.opencontainers.image.source="https://github.com/luna-ai-project/Luna"
LABEL org.opencontainers.image.licenses="MIT"

# System packages:
#   ffmpeg        — audio decoding for faster-whisper
#   build-essential — needed by some chromadb native deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (cross-platform subset — no pywin32/pycaw/audio drivers)
COPY requirements.docker.txt ./
RUN pip install --no-cache-dir -r requirements.docker.txt

# Application code
COPY server/ ./server/

# Web UI — the desktop app's renderer, served by FastAPI at "/"
COPY interfaces/desktop/src/renderer/ ./interfaces/desktop/src/renderer/
COPY interfaces/desktop/resources/ ./interfaces/desktop/resources/

# Persistent data lives here — mount a named volume to this path
RUN mkdir -p data

# Force UTF-8 output (avoids cp1252 issues inherited from Windows development)
ENV PYTHONUTF8=1
ENV PYTHONUNBUFFERED=1

# Luna backend port
EXPOSE 8899

# Health check — FastAPI exposes /api/system/health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8899/api/system/health')" || exit 1

CMD ["python", "-m", "uvicorn", "server.main:app", \
     "--host", "0.0.0.0", "--port", "8899", \
     "--log-level", "warning"]
