"""
Production-grade logging for the whole backend.

Sets up:
  - Console output (dev/foreground visibility)
  - A rotating file at data/logs/luna.log — `luna log` tails this live
  - Redirection of raw print()/stderr writes into the same log, so scattered
    print() calls throughout the codebase show up in the log file too,
    without having to rewrite every call site to use `logging` directly
  - An excepthook so uncaught exceptions are logged with a full traceback
    instead of vanishing when nothing is watching the console

Config (.env):
  log_level=INFO          # DEBUG | INFO | WARNING | ERROR
  log_format=text         # text | json  (json is machine-readable for log aggregation)
"""
import logging
import logging.config
import logging.handlers
import sys
from contextvars import ContextVar

from server.config import DATA_DIR, settings

# ── Request correlation ────────────────────────────────────────────────────────
# Accessible from any async/sync code in the same request context.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "luna.log"


class RequestIDFilter(logging.Filter):
    """Injects request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class _StreamToLogger:
    """
    File-like shim that routes raw print()/stdout/stderr writes into the
    logging system. Buffers partial writes until a newline (or an explicit
    flush, for `print(..., end="", flush=True)`-style live updates) so each
    line becomes one clean log record instead of fragments.
    """

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self._logger = logger
        self._level = level
        self._buffer = ""

    def write(self, message: str) -> int:
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if line.strip():
                self._logger.log(self._level, line)
        return len(message)

    def flush(self) -> None:
        if self._buffer.strip():
            self._logger.log(self._level, self._buffer)
        self._buffer = ""

    def isatty(self) -> bool:
        return False


def _log_uncaught_exception(exc_type, exc_value, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.getLogger("luna.uncaught").critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_tb)
    )


def configure_logging() -> None:
    """
    Configure structured logging for the entire backend.

    Call this once at application startup (before any loggers are used).
    Reads log_level and log_format from settings.
    """
    log_level = getattr(settings, "log_level", "INFO").upper()
    log_format = getattr(settings, "log_format", "text").lower()

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if log_format == "json":
        # JSON format for production log aggregation (ELK, CloudWatch, etc.)
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","request_id":"%(request_id)s","message":"%(message)s"}'
    else:
        # Human-readable format for development
        fmt = "%(asctime)s | %(levelname)-7s | %(name)-30s | [%(request_id)s] %(message)s"

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": RequestIDFilter,
            },
        },
        "formatters": {
            "default": {
                "format": fmt,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                # The real original stdout — configured before we redirect
                # sys.stdout below, so console output keeps working either way.
                "stream": "ext://sys.__stdout__",
                "formatter": "default",
                "filters": ["request_id"],
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_FILE),
                "maxBytes": 10_000_000,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "default",
                "filters": ["request_id"],
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"],
        },
        # Quiet down noisy libraries
        "loggers": {
            "uvicorn": {"level": "INFO"},
            "uvicorn.access": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
            "httpcore": {"level": "WARNING"},
            "chromadb": {"level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING" if not settings.db_echo else "INFO"},
        },
    })

    # Route stray print()/stderr output into the same log file — so `luna log`
    # shows everything Luna does, not just calls that go through `logging`.
    sys.stdout = _StreamToLogger(logging.getLogger("luna.stdout"), logging.INFO)
    sys.stderr = _StreamToLogger(logging.getLogger("luna.stderr"), logging.ERROR)

    # Uncaught exceptions get logged (with traceback) instead of disappearing.
    sys.excepthook = _log_uncaught_exception
