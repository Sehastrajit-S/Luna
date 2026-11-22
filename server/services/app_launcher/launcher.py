"""App launching logic, target resolution, and public API."""
import os
import platform
import re
import shutil
import subprocess
from difflib import get_close_matches
from pathlib import Path

from server.services.app_launcher.profiles import (
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
        if query in aliases or any(_names_match(query, a) for a in aliases):
            targets = list(profile.get(_platform_key(), []))
            return [t for t in targets if t]
    return []


def _first_available_target(targets: list[str]) -> str | None:
    if not targets:
        return None
    if IS_MAC:
        return targets[0]
    if IS_WINDOWS:
        # A bare program name only counts when Windows can actually find it;
        # otherwise find_app goes on to the installed-apps lists.
        for t in targets:
            resolved = _resolve_windows_target(t)
            if resolved:
                return resolved
        return None
    for t in targets:
        if t.startswith("xdg-open:"):
            return t
        if shutil.which(t.split()[0]):
            return t
    return targets[0]


def _is_windows_uri(target: str) -> bool:
    return (target == STICKY_NOTES_TARGET or target.endswith(":")
            or target.startswith("ms-") or target.startswith("shell:"))


def _resolve_windows_target(target: str) -> str | None:
    """The target as something launchable on Windows, or None when it isn't installed."""
    if not target:
        return None
    if _is_windows_uri(target):
        return target
    if Path(target).exists():
        return target
    exe = target.split()[0]
    if shutil.which(exe):
        return target
    from server.services.app_launcher.discovery import _get_registry_apps
    registered = _get_registry_apps().get(_normalize(Path(exe).stem))
    if registered and Path(registered.strip('"')).exists():
        return registered.strip('"')
    return None


def _contains_words(haystack: str, needle: str) -> bool:
    """needle appears in haystack as whole words ("run" is not in "running")."""
    return bool(needle) and re.search(rf"(?<![\w]){re.escape(needle)}(?![\w])", haystack) is not None


def _names_match(query: str, name: str) -> bool:
    """A request and an app name refer to the same app: equal, or one inside the other as whole
    words, where an app name inside a longer request must be at least 4 characters."""
    if not query or not name:
        return False
    if query == name or _contains_words(name, query):
        return True
    return len(name) >= 4 and _contains_words(query, name)


def _best_match(query: str, apps: dict[str, str]) -> str | None:
    if query in apps:
        return apps[query]
    # "chrome" → "google chrome": the query inside a longer app name, as whole words.
    for k, v in apps.items():
        if _contains_words(k, query):
            return v
    # "spotify music" → "spotify": an app name inside the query, as whole words, and not a tiny one
    # ("run" in "…running late" opened the Run dialog; "ea" in "reached" opened the EA app).
    for k, v in sorted(apps.items(), key=lambda kv: -len(kv[0])):
        if len(k) >= 4 and _contains_words(query, k) and len(k) >= len(query) / 3:
            return v
    close = get_close_matches(query, apps.keys(), n=1, cutoff=0.72)
    if close:
        return apps[close[0]]
    return None


def _sticky_notes_candidates() -> list[str]:
    from server.services.app_launcher.discovery import (
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
    from server.services.app_launcher.discovery import (
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

    aliased = COMMON_APP_ALIASES.get(query) or next(
        (t for a, t in COMMON_APP_ALIASES.items() if _names_match(query, a)), None)
    resolved = _resolve_windows_target(aliased) if aliased else None
    if resolved:
        return True, resolved

    # Installed apps, by the name asked for and every name its profile knows
    # ("whatsapp" is a Store app, "chrome" is listed as "google chrome").
    names = [query, *(_normalize(a) for a in _profile_aliases(query))]
    if aliased:
        names.append(_normalize(aliased))
    names = list(dict.fromkeys(n for n in names if n))
    for apps in (_get_luna_apps(), _get_registry_apps(), _get_start_menu_apps(), _get_store_apps()):
        for n in names:
            target = _best_match(n, apps)
            if target:
                return True, target

    suggestions = suggest_apps(name)
    hint = f" Did you mean {', '.join(suggestions)}?" if suggestions else ""
    return False, f"Couldn't find an app called '{name}' on this computer.{hint}"


def _profile_aliases(query: str) -> list[str]:
    for profile in APP_PROFILES.values():
        aliases = [_normalize(a) for a in profile["aliases"]]
        if query in aliases or any(_names_match(query, a) for a in aliases):
            return aliases
    return []


def suggest_apps(name: str, limit: int = 3) -> list[str]:
    """Installed app names that look like `name`, for "did you mean"."""
    query = _normalize(name)
    known = list_known_apps()
    picks = [k for k in known if query and (query in k or k in query) and len(k) > 2]
    picks += get_close_matches(query, known, n=limit, cutoff=0.6)
    return list(dict.fromkeys(picks))[:limit]


def launch_app(name: str) -> tuple[bool, str]:
    found, target = find_app(name)
    if not found:
        return False, target

    if target == STICKY_NOTES_TARGET:
        return launch_sticky_notes()

    try:
        _launch_target(target)
        return True, f"Launched {name}"
    except OSError as e:
        if IS_WINDOWS and not _is_windows_uri(target):
            # Last try: let Windows resolve the name itself (App Paths, file associations).
            try:
                os.startfile(target)
                return True, f"Launched {name}"
            except OSError:
                pass
        suggestions = suggest_apps(name)
        hint = f" Did you mean {', '.join(suggestions)}?" if suggestions else ""
        return False, f"Couldn't open {name}: {getattr(e, 'strerror', None) or e}.{hint}"
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
    from server.services.app_launcher.discovery import (
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
