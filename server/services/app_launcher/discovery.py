"""Platform-specific app discovery: Windows registry/Store/Start Menu, macOS Spotlight, Linux .desktop."""
import os
import subprocess
from functools import lru_cache
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

import platform

PLATFORM   = platform.system()
IS_WINDOWS = PLATFORM == "Windows"
IS_MAC     = PLATFORM == "Darwin"
IS_LINUX   = PLATFORM == "Linux"

LUNA_APPS_DIR = Path("data/apps")


def _get_luna_apps() -> dict[str, str]:
    apps = {}
    if LUNA_APPS_DIR.exists():
        for lnk in LUNA_APPS_DIR.glob("*.lnk"):
            apps[lnk.stem.lower()] = str(lnk)
    return apps


def _get_start_menu_apps() -> dict[str, str]:
    apps = {}
    search_dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for lnk in d.rglob("*.lnk"):
            apps[lnk.stem.lower()] = str(lnk)
    return apps


@lru_cache(maxsize=1)
def _get_registry_apps() -> dict[str, str]:
    apps = {}
    if winreg is None:
        return apps
    keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
    ]
    for key_path in keys:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sub_name = winreg.EnumKey(key, i)
                    sub_key  = winreg.OpenKey(key, sub_name)
                    path, _  = winreg.QueryValueEx(sub_key, "")
                    apps[sub_name.lower().replace(".exe", "")] = path
                except Exception:
                    continue
        except Exception:
            continue
    return apps


@lru_cache(maxsize=1)
def _get_store_apps() -> dict[str, str]:
    apps = {}
    if not IS_WINDOWS:
        return apps
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-StartApps | ForEach-Object { \"$($_.Name)`t$($_.AppID)\" }"],
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return apps
    if result.returncode != 0:
        return apps
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        name, app_id = line.split("\t", 1)
        name   = name.strip().lower()
        app_id = app_id.strip()
        if name and app_id:
            apps[name] = f"shell:AppsFolder\\{app_id}"
    return apps


def _spotlight_search(name: str) -> str | None:
    if not IS_MAC:
        return None
    try:
        result = subprocess.run(
            ["mdfind", "-onlyin", "/Applications",
             f'kMDItemKind == "Application" && kMDItemDisplayName == "{name}"'],
            capture_output=True, text=True, timeout=4,
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if lines:
                return f"app_path:{lines[0]}"
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["mdfind", "-onlyin", "/Applications", f'kMDItemDisplayName == "*{name}*"cdw'],
            capture_output=True, text=True, timeout=4,
        )
        if result.returncode == 0:
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if lines:
                return f"app_path:{lines[0]}"
    except Exception:
        pass
    return None


@lru_cache(maxsize=1)
def _get_desktop_apps() -> dict[str, str]:
    if not IS_LINUX:
        return {}
    apps: dict[str, str] = {}
    search_dirs = [
        Path.home() / ".local" / "share" / "applications",
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
        Path("/var/lib/snapd/desktop/applications"),
    ]
    _bad_tokens = {"%u", "%U", "%f", "%F", "%d", "%D", "%n", "%N", "%i", "%m", "%k", "%v", "%c"}

    for directory in search_dirs:
        if not directory.exists():
            continue
        for desktop_file in directory.glob("*.desktop"):
            try:
                name: str | None     = None
                exec_cmd: str | None = None
                skip = False
                with open(desktop_file, encoding="utf-8", errors="ignore") as fh:
                    in_entry = False
                    for line in fh:
                        line = line.strip()
                        if line == "[Desktop Entry]":
                            in_entry = True
                        elif line.startswith("[") and in_entry:
                            break
                        elif in_entry:
                            if line.startswith("NoDisplay=true") or line.startswith("Hidden=true"):
                                skip = True
                                break
                            if line.startswith("Type=") and not line.startswith("Type=Application"):
                                skip = True
                                break
                            if line.startswith("Name=") and name is None:
                                name = line[5:].strip()
                            if line.startswith("Exec=") and exec_cmd is None:
                                parts = line[5:].strip().split()
                                clean = [p for p in parts if p not in _bad_tokens and not p.startswith("%")]
                                if clean:
                                    exec_cmd = clean[0]
                if not skip and name and exec_cmd:
                    from backend.services.app_launcher.launcher import _normalize
                    apps[_normalize(name)] = exec_cmd
            except Exception:
                continue
    return apps
