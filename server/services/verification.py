"""Check that something Luna started really happened: process, window, screenshot.

Luna used to report "opened" as soon as it asked the OS to start something.
These helpers look for evidence afterwards:

- command check: a matching process exists (psutil: name, start time,
  command line, working folder);
- window check: that process (or the terminal hosting it) has a visible window;
- screenshot check: the window is captured (even when covered, via
  PrintWindow), saved under data/screenshots, and read with local OCR so the
  model can say what's on it.

Each step reports what it found; nothing here changes anything.
"""
from __future__ import annotations

import logging
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from server.config import DATA_DIR

logger = logging.getLogger("luna.verification")

IS_WINDOWS = platform.system() == "Windows"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
KEEP_SCREENSHOTS = 40


@dataclass
class Evidence:
    process: Optional[dict] = None       # {"pid", "name", "started", "cwd"}
    window: Optional[dict] = None        # {"hwnd", "title", "pid"}
    screenshot: Optional[str] = None     # saved PNG path
    screen_text: str = ""                # OCR of the screenshot, last lines
    notes: list[str] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return bool(self.process and self.window)

    def summary(self) -> str:
        parts = []
        if self.process:
            parts.append(f"command check: {self.process['name']} is running (pid {self.process['pid']})")
        else:
            parts.append("command check: no matching process found")
        if self.window:
            parts.append(f"window check: '{self.window['title']}' is open")
        else:
            parts.append("window check: no window found")
        if self.screenshot:
            parts.append(f"screenshot: {self.screenshot}")
        parts.extend(self.notes)
        text = "; ".join(parts) + "."
        if self.screen_text:
            text += f"\nText on screen (OCR, may have small errors):\n{self.screen_text}"
        return text


# ── Processes ────────────────────────────────────────────────────────────────

def _proc_info(proc) -> dict:
    try:
        cwd = proc.cwd()
    except Exception:
        cwd = ""
    created = proc.info.get("create_time")
    try:
        started = datetime.fromtimestamp(created if created is not None else proc.create_time()).isoformat(timespec="seconds")
    except Exception:
        started = ""
    return {"pid": proc.pid, "name": proc.info.get("name") or proc.name(), "started": started, "cwd": cwd}


def find_processes(names: set[str], *, since: float | None = None, cmd_contains: str = "",
                   cwd: Path | None = None) -> list:
    """Running processes named `names`, newest first, filtered by start time / command line / folder."""
    import psutil

    wanted = {n.lower() for n in names}
    found = []
    for proc in psutil.process_iter(["pid", "name", "create_time", "cmdline"]):
        try:
            if (proc.info.get("name") or "").lower() not in wanted:
                continue
            if since and (proc.info.get("create_time") or 0) < since - 1:
                continue
            if cmd_contains and cmd_contains.lower() not in " ".join(proc.info.get("cmdline") or []).lower():
                continue
            if cwd is not None:
                try:
                    if Path(proc.cwd()).resolve() != Path(cwd).resolve():
                        continue
                except Exception:
                    continue
            found.append(proc)
        except Exception:
            continue
    found.sort(key=lambda p: p.info.get("create_time") or 0, reverse=True)
    return found


def wait_for_process(names: set[str], *, since: float, cmd_contains: str = "", timeout: float = 10.0,
                     sleep: Callable[[float], None] = time.sleep):
    deadline = time.monotonic() + timeout
    while True:
        found = find_processes(names, since=since, cmd_contains=cmd_contains)
        if found or time.monotonic() >= deadline:
            return found[0] if found else None
        sleep(0.5)


# ── Windows ──────────────────────────────────────────────────────────────────

def _windows_by_pid() -> dict[int, list[tuple[int, str]]]:
    if not IS_WINDOWS:
        return {}
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    found: dict[int, list[tuple[int, str]]] = {}

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.setdefault(pid.value, []).append((int(hwnd), title.value))
        return True

    user32.EnumWindows(visit, 0)
    return found


def window_for(proc, prefer: tuple[str, ...] = ()) -> Optional[dict]:
    """The visible window of `proc`, or of the nearest parent that has one (the terminal hosting a CLI).

    One terminal process can own several windows; a title containing one of
    `prefer` wins over the first one found.
    """
    windows = _windows_by_pid()
    current, hops = proc, 0
    while current is not None and hops < 4:
        wins = windows.get(current.pid, [])
        if wins:
            preferred = [w for w in wins if any(p and p.lower() in w[1].lower() for p in prefer)]
            hwnd, title = (preferred or wins)[0]
            return {"hwnd": hwnd, "title": title, "pid": current.pid}
        try:
            current = current.parent()
        except Exception:
            current = None
        hops += 1
    return None


def window_titled(contains: str, process_names: set[str] | None = None) -> Optional[dict]:
    """A visible window whose title contains `contains` (optionally owned by one of `process_names`)."""
    import psutil

    for pid, wins in _windows_by_pid().items():
        if process_names:
            try:
                if psutil.Process(pid).name().lower() not in {n.lower() for n in process_names}:
                    continue
            except Exception:
                continue
        for hwnd, title in wins:
            if contains.lower() in title.lower():
                return {"hwnd": hwnd, "title": title, "pid": pid}
    return None


def _squash(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def verify_app_window(name: str, target: str = "", *, timeout: float = 6.0,
                      sleep: Callable[[float], None] = time.sleep, list_apps=None) -> Evidence:
    """After launching an app: wait for a window of it to show up (app name, process or title match)."""
    if list_apps is None:
        from server.services.app_launcher import list_open_apps as list_apps
    keys = {_squash(name)}
    stem = Path(target.split("!")[0].split("\\")[-1]).stem if target else ""
    if stem and not target.startswith(("ms-", "shell:")) and len(_squash(stem)) > 2:
        keys.add(_squash(stem))
    keys.discard("")
    evidence = Evidence()
    deadline = time.monotonic() + timeout
    while True:
        for app in list_apps():
            fields = [app.get("app", ""), Path(app.get("process") or "").stem, *app.get("windows", [])]
            if any(k in _squash(f) for k in keys for f in fields if f):
                evidence.process = {"pid": None, "name": app.get("process") or app.get("app"), "started": "", "cwd": ""}
                evidence.window = {"hwnd": None, "title": (app.get("windows") or [app.get("app")])[0], "pid": None}
                return evidence
        if time.monotonic() >= deadline:
            return evidence
        sleep(0.5)


# ── Screenshots ──────────────────────────────────────────────────────────────

def capture_window(hwnd: int):
    """A PIL image of the window, even when other windows cover it. None if it can't be captured."""
    if not IS_WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes

    from PIL import Image

    user32, gdi32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0 or user32.IsIconic(hwnd):
        return None
    hdc_window = user32.GetWindowDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
    bitmap = gdi32.CreateCompatibleBitmap(hdc_window, width, height)
    gdi32.SelectObject(hdc_mem, bitmap)
    try:
        if not user32.PrintWindow(hwnd, hdc_mem, 2):   # PW_RENDERFULLCONTENT: works for GPU-drawn windows
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(hdc_mem, bitmap, 0, height, buffer, ctypes.byref(header), 0):
            return None
        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")
        if image.getbbox() is None or max(image.getextrema()[0][1], image.getextrema()[1][1]) < 8:
            return None   # all black: the window didn't render into the capture
        return image
    finally:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_window)


def save_screenshot(image, label: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label.lower())[:40].strip("-") or "window"
    path = SCREENSHOT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{safe}.png"
    image.save(path)
    shots = sorted(SCREENSHOT_DIR.glob("*.png"))
    for old in shots[:-KEEP_SCREENSHOTS]:
        try:
            old.unlink()
        except OSError:
            pass
    return str(path)


def read_screen_text(image, last_lines: int = 25) -> str:
    try:
        from server.services.files.ocr import ocr_image
        text = ocr_image(image).text
    except Exception as e:   # OCR is optional
        logger.info("OCR unavailable for verification screenshot: %s", e)
        return ""
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[-last_lines:])


def screenshot_evidence(evidence: Evidence, label: str) -> Evidence:
    if not evidence.window:
        return evidence
    try:
        image = capture_window(evidence.window["hwnd"])
    except Exception as e:
        logger.info("Window capture failed: %s", e)
        image = None
    if image is None:
        evidence.notes.append("screenshot: the window couldn't be captured (minimised?)")
        return evidence
    evidence.screenshot = save_screenshot(image, label)
    evidence.screen_text = read_screen_text(image)
    return evidence
