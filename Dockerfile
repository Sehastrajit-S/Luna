# ── Luna: server + web UI in one image ─────────────────────────────────────────
# Prebuilt: docker run -d -p 127.0.0.1:8899:8899 -v luna_data:/app/data ghcr.io/sehastrajit-s/luna
# See docs/SETUP.md (Docker) for models, Tailscale and upgrades.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Luna"
LABEL org.opencontainers.image.description="Your own AI assistant: local-first, any model, every device"
LABEL org.opencontainers.image.source="https://github.com/Sehastrajit-S/Luna"
LABEL org.opencontainers.image.licenses="MIT"

# ffmpeg: audio decoding for speech-to-text and meeting recordings
# libgl1, libglib2.0-0: OpenCV, used by OCR for scanned PDFs and images
# build-essential: native builds for a few Python packages without wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Same requirements as a normal install; Windows-only packages are skipped by
# their environment markers.
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY server/ server/
COPY alembic.ini ./
# The web UI is the desktop app's renderer, served at "/".
COPY interfaces/desktop/src/renderer/ interfaces/desktop/src/renderer/
COPY interfaces/desktop/resources/ interfaces/desktop/resources/

# Everything Luna writes (database, memory, uploads, meetings, downloaded
# speech models, and settings saved from the Settings page in luna.env)
# lives in /app/data: mount a volume there to keep it.
RUN useradd --create-home --uid 10001 luna && mkdir -p data && chown -R luna:luna /app
USER luna

ENV PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/data/models \
    LUNA_ENV_FILE=/app/data/luna.env \
    host=0.0.0.0 \
    port=8899

EXPOSE 8899

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8899/api/system/health', timeout=8)" || exit 1

CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8899", "--log-level", "warning"]
