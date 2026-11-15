"""App launching logic, target resolution, and public API."""
import os
import platform
import shutil
import subprocess
from difflib import get_close_matches
from pathlib import Path

from backend.services.app_launcher.profiles import (
    APP_PROFILES,
    COMMON_APP_ALIASES,
    STICKY_NOTES_APP_IDS,
    STICKY_NOTES_PROTOCOLS,
    STICKY_NOTES_TARGET,
)

PLATFORM   = platform.system()
IS_WINDOWS = PLATFORM == "Windows"
IS_MAC     = PLATFORM == "Darwin"
IS_LINUX   = PLATFORM == "Linux"


def _normalize(name: str) -> str:
    return " ".join(name.lower().replace(".exe", "").split())


def _platform_key() -> str:
    if IS_WINDOWS:
        return "windows"
    if IS_MAC:
        return "mac"
    return "linux"


def _profile_targets(query: str) -> list[str]:
    for profile in APP_PROFILES.values():
        aliases = {_normalize(a) for a in profile["aliases"]}
        if query in aliases or any(query in a or a in query for a in aliases):
            targets = list(profile.get(_platform_key(), []))
            return [t for t in targets if t]
    return []


def _first_available_target(targets: list[str]) -> str | None:
    if not targets:
        return None
    if IS_MAC:
        return targets[0]
    if IS_WINDOWS:
        for t in targets:
            if (t == STICKY_NOTES_TARGET or t.endswith(":")
                    or t.startswith("ms-") or t.startswith("shell:")):
                return t
            if shutil.which(t.split()[0]):
                return t
        return targets[0]
    for t in targets:
        if t.startswith("xdg-open:"):
            return t
        if shutil.which(t.split()[0]):
            return t
    return targets[0]


def _best_match(query: str, apps: dict[str, str]) -> str | None:
    if query in apps:
        return apps[query]
    for k, v in apps.items():
        if query in k or k in query:
            return v
    close = get_close_matches(query, apps.keys(), n=1, cutoff=0.72)
    if close:
        return apps[close[0]]
    return None


def _sticky_notes_candidates() -> list[str]:
    from backend.services.app_launcher.discovery import (
        _get_luna_apps,
        _get_start_menu_apps,
        _get_store_apps,
    )
    candidates: list[str] = []
    for apps in (_get_store_apps(), _get_start_menu_apps(), _get_luna_apps()):
        for app_name, target in apps.items():
            n = _normalize(app_name)
            if n in {"sticky notes", "microsoft sticky notes"}:
                candidates.insert(0, target)
            elif "sticky" in n and "note" in n:
                candidates.append(target)
    candidates.extend(f"shell:AppsFolder\\{app_id}" for app_id in STICKY_NOTES_APP_IDS)
    candidates.extend(STICKY_NOTES_PROTOCOLS)
    deduped: list[str] = []
    for c in candidates:
        if c and c not in deduped:
            deduped.append(c)
    return deduped


def _launch_target(target: str) -> None:
    if target.startswith("app:"):
        app_name = target[4:]
        if IS_MAC:
            subprocess.Popen(["open", "-a", app_name])
            return
        raise OSError(f"app: target only supported on macOS: {app_name}")

    if target.startswith("app_path:"):
        path = target[9:]
        if IS_MAC:
            subprocess.Popen(["open", path])
            return
        raise OSError(f"app_path: target only supported on macOS: {path}")

    if target.startswith("xdg-open:"):
        uri = target[9:]
        if uri == "~":
            uri = str(Path.home())
        if IS_LINUX:
            subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        raise OSError(f"xdg-open: target only supported on Linux: {uri}")

    if (target.endswith(":") or target.startswith("ms-") or target.startswith("shell:")
            or target.endswith(".lnk") or target.endswith(".msc")):
        if IS_WINDOWS:
            os.startfile(target)
            return
        raise OSError(f"Windows-only target on non-Windows: {target}")

    if Path(target).exists():
        if IS_WINDOWS:
            os.startfile(target)
        else:
            subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    if IS_WINDOWS:
        subprocess.Popen([target], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return

    subprocess.Popen(target.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch_sticky_notes() -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "Sticky Notes is only available on Windows."
    errors = []
    for target in _sticky_notes_candidates():
        try:
            _launch_target(target)
            return True, "Opened Sticky Notes"
        except Exception as e:
            errors.append(f"{target}: {e}")
    return (
        False,
        "Couldn't open Sticky Notes. Install it from the Microsoft Store or add a shortcut "
        "to data/apps/Sticky Notes.lnk.",
    )


def find_app(name: str) -> tuple[bool, str]:
    from backend.services.app_launcher.discovery import (
        _get_desktop_apps,
        _get_luna_apps,
        _get_registry_apps,
        _get_start_menu_apps,
        _get_store_apps,
        _spotlight_search,
    )
    query = _normalize(name)

    profile_target = _first_available_target(_profile_targets(query))
    if profile_target:
        return True, profile_target

    if shutil.which(query):
        return True, query

    if IS_MAC:
        spotlight = _spotlight_search(name)
        if spotlight:
            return True, spotlight
        return True, f"app:{name}"

    if IS_LINUX:
        desktop_apps = _get_desktop_apps()
        target = _best_match(query, desktop_apps)
        if target:
            return True, target
        return False, f"No application found matching '{name}' on this Linux system."

    if query in COMMON_APP_ALIASES:
        return True, COMMON_APP_ALIASES[query]
    for alias, target in COMMON_APP_ALIASES.items():
        if query in alias or alias in query:
            return True, target

    for apps in (_get_luna_apps(), _get_registry_apps(), _get_start_menu_apps(), _get_store_apps()):
        target = _best_match(query, apps)
        if target:
            return True, target

    return True, query


def launch_app(name: str) -> tuple[bool, str]:
    found, target = find_app(name)
    if not found:
        return False, f"Couldn't find an app matching '{name}' on this platform."

    if target == STICKY_NOTES_TARGET:
        return launch_sticky_notes()

    try:
        _launch_target(target)
        return True, f"Launched {name}"
    except Exception as e:
        return False, f"Couldn't launch '{name}': {e}"


def _process_name_candidates(query: str) -> list[str]:
    """Resolve a query to candidate running-process name stems (normalized, no extension)."""
    candidates: set[str] = set()
    for target in _profile_targets(query):
        if target.startswith("app:"):
            candidates.add(target[4:])
        elif target.startswith("app_path:"):
            candidates.add(Path(target[9:]).stem)
        elif not (target.endswith(":") or target.startswith("ms-")
                  or target.startswith("shell:") or target.startswith("xdg-open:")):
            candidates.add(target.split()[0])
    candidates.add(query)
    return [_normalize(c) for c in candidates if c]


def close_app(name: str) -> tuple[bool, str]:
    """Close a running app by name. Returns (success, message)."""
    query = _normalize(name)
    candidates = _process_name_candidates(query)

    try:
        import psutil

        procs = list(psutil.process_iter(["pid", "name"]))
        matched = [p for p in procs if _normalize(p.info.get("name") or "") in candidates]
        if not matched:
            matched = [
                p for p in procs
                if any(c and c in _normalize(p.info.get("name") or "") for c in candidates)
            ]
        if not matched:
            return False, f"Couldn't find a running app matching '{name}'."

        closed = 0
        for proc in matched:
            try:
                proc.terminate()
                closed += 1
            except Exception:
                continue
        if closed:
            return True, f"Closed {name}"
        return False, f"Found '{name}' running but couldn't close it."
    except ImportError:
        pass

    for cand in candidates:
        try:
            if IS_WINDOWS:
                result = subprocess.run(
                    ["taskkill", "/IM", f"{cand}.exe", "/F"],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                result = subprocess.run(["pkill", "-i", cand], capture_output=True, timeout=5)
            if result.returncode == 0:
                return True, f"Closed {name}"
        except Exception:
            continue

    return False, f"Couldn't find a running app matching '{name}'."


def list_known_apps() -> list[str]:
    from backend.services.app_launcher.discovery import (
        _get_desktop_apps,
        _get_registry_apps,
        _get_start_menu_apps,
        _get_store_apps,
    )
    platform_key = _platform_key()
    names: list[str] = []

    for profile in APP_PROFILES.values():
        if profile.get(platform_key):
            names.extend(profile["aliases"])

    if IS_LINUX:
        names.extend(_get_desktop_apps().keys())
    elif IS_WINDOWS:
        names.extend(COMMON_APP_ALIASES.keys())
        names.extend(_get_registry_apps().keys())
        names.extend(_get_start_menu_apps().keys())
        names.extend(_get_store_apps().keys())
        if _sticky_notes_candidates():
            names += ["sticky notes", "microsoft sticky notes"]

    return sorted(set(names))


def list_app_profiles() -> dict:
    platform_key = _platform_key()
    profiles = [
        {
            "id":        app_id,
            "aliases":   profile["aliases"],
            "platform":  platform_key,
            "targets":   [t for t in profile.get(platform_key, []) if t],
            "supported": bool(profile.get(platform_key)),
        }
        for app_id, profile in APP_PROFILES.items()
    ]
    return {"platform": PLATFORM, "profiles": profiles}
