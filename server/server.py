"""
Standalone entry point for the Luna FastAPI backend.
Called by Electron's main process — do not run directly unless testing.
"""
import sys
import os
import atexit
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure project root is on the path when run as a subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Write PID file — use LUNA_DATA_DIR from Electron so we always write to a
# user-writable location (AppData/Roaming/luna/data), never into Program Files.
_data_dir = Path(os.environ.get("LUNA_DATA_DIR") or (Path(__file__).parent.parent / "data"))
_PID_FILE = _data_dir / "backend.pid"
_data_dir.mkdir(parents=True, exist_ok=True)
_PID_FILE.write_text(str(os.getpid()))

@atexit.register
def _cleanup_pid():
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass

import uvicorn
from backend.config import settings
from backend.main import app

if __name__ == '__main__':
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level='warning',
    )
