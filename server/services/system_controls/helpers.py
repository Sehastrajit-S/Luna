"""Shared OS helpers for system_controls."""
import platform
import subprocess
import shutil

PLATFORM   = platform.system()
IS_WINDOWS = PLATFORM == "Windows"
IS_MAC     = PLATFORM == "Darwin"
IS_LINUX   = PLATFORM == "Linux"


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}),
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return -1, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except Exception as e:
        return -1, str(e)


def _osascript(script: str) -> tuple[int, str]:
    return _run(["osascript", "-e", script])


def _ps(command: str) -> tuple[int, str]:
    return _run(["powershell", "-NoProfile", "-Command", command])
