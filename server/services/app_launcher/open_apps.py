"""Which apps are open right now: apps with a visible window, and their window titles.

Windows: top-level windows that are visible, have a title, aren't tool windows,
and aren't cloaked (hidden UWP frames / other virtual desktops). macOS: visible
apps from System Events. Linux: `wmctrl -lp` when installed.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

PLATFORM = platform.system()

# Shell and background pieces that own visible windows but aren't apps you opened.
_IGNORE = {
    "explorer": {"Program Manager", ""},
    "textinputhost": None, "applicationframehost": None, "shellexperiencehost": None,
    "startmenuexperiencehost": None, "searchhost": None, "systemsettingsbroker": None,
    "lockapp": None, "nvidia overlay": None, "widgets": None,
}
_FRIENDLY = {
    "chrome": "Google Chrome", "msedge": "Microsoft Edge", "firefox": "Firefox", "code": "VS Code",
    "explorer": "File Explorer", "winword": "Word", "excel": "Excel", "powerpnt": "PowerPoint",
    "outlook": "Outlook", "olk": "Outlook", "ms-teams": "Teams", "spotify": "Spotify", "discord": "Discord",
    "slack": "Slack", "whatsapp": "WhatsApp", "whatsapp.root": "WhatsApp", "notepad": "Notepad",
    "windowsterminal": "Terminal", "cmd": "Command Prompt", "powershell": "PowerShell", "pwsh": "PowerShell",
    "electron": "Luna", "luna": "Luna", "obs64": "OBS", "vlc": "VLC", "steam": "Steam",
}


def _friendly(process: str) -> str:
    stem = Path(process).stem.lower()
    return _FRIENDLY.get(stem) or Path(process).stem.replace("_", " ").replace("-", " ").title()


def _windows_open_windows() -> list[tuple[str, str]]:
    """(process name, window title) for each app window on Windows."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    GWL_EXSTYLE, WS_EX_TOOLWINDOW, DWMWA_CLOAKED = -20, 0x80, 14
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    user32.GetWindowLongW.restype = ctypes.c_long
    found: list[tuple[str, str]] = []

    def process_name(hwnd) -> str:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return Path(buf.value).name
            return ""
        finally:
            kernel32.CloseHandle(handle)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):  # GW_OWNER: skip dialogs owned by another window
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        cloaked = wintypes.DWORD()
        if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)) == 0 and cloaked.value:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        found.append((process_name(hwnd), title.value.strip()))
        return True

    user32.EnumWindows(visit, 0)
    return found


def _mac_open_apps() -> list[tuple[str, str]]:
    script = 'tell application "System Events" to get name of every application process whose background only is false'
    out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=6).stdout
    return [(name.strip(), "") for name in out.split(",") if name.strip()]


def _linux_open_windows() -> list[tuple[str, str]]:
    if not shutil.which("wmctrl"):
        return []
    out = subprocess.run(["wmctrl", "-lp"], capture_output=True, text=True, timeout=5).stdout
    found = []
    for line in out.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            name = Path(f"/proc/{int(parts[2])}/comm").read_text().strip()
        except (OSError, ValueError):
            name = ""
        found.append((name, parts[4].strip()))
    return found


def list_open_apps() -> list[dict]:
    """[{"app", "process", "windows": [titles]}], in the order windows are stacked (front first)."""
    if PLATFORM == "Windows":
        raw = _windows_open_windows()
    elif PLATFORM == "Darwin":
        raw = _mac_open_apps()
    else:
        raw = _linux_open_windows()

    apps: dict[str, dict] = {}
    for process, title in raw:
        stem = Path(process).stem.lower()
        if stem in _IGNORE and (_IGNORE[stem] is None or title in _IGNORE[stem]):
            continue
        key = stem or title.lower()
        entry = apps.setdefault(key, {"app": _friendly(process) if process else title, "process": process, "windows": []})
        if title and title not in entry["windows"]:
            entry["windows"].append(title[:120])
    return list(apps.values())
