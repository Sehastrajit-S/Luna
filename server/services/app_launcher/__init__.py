"""Cross-platform app launcher — Windows, macOS, Linux."""
from backend.services.app_launcher.profiles import (
    APP_PROFILES,
    COMMON_APP_ALIASES,
    STICKY_NOTES_APP_IDS,
    STICKY_NOTES_PROTOCOLS,
    STICKY_NOTES_TARGET,
)
from backend.services.app_launcher.launcher import (
    close_app,
    find_app,
    launch_app,
    launch_sticky_notes,
    list_known_apps,
    list_app_profiles,
)

__all__ = [
    "APP_PROFILES",
    "COMMON_APP_ALIASES",
    "STICKY_NOTES_TARGET",
    "STICKY_NOTES_APP_IDS",
    "STICKY_NOTES_PROTOCOLS",
    "close_app",
    "find_app",
    "launch_app",
    "launch_sticky_notes",
    "list_known_apps",
    "list_app_profiles",
]
