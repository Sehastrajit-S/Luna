"""Thread-safe bus for pushing proactive messages to connected SSE clients."""
from collections import deque
import threading

_pending: deque[str] = deque(maxlen=100)
_lock = threading.Lock()


def push(msg: str) -> None:
    with _lock:
        _pending.append(msg)


def drain() -> list[str]:
    with _lock:
        out = list(_pending)
        _pending.clear()
        return out
