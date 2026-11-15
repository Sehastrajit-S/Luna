# Backward-compat shim — all logic lives in backend.services.app_launcher package
from backend.services.app_launcher import *  # noqa: F401, F403
from backend.services.app_launcher import (
    APP_PROFILES,
    COMMON_APP_ALIASES,
    STICKY_NOTES_TARGET,
    STICKY_NOTES_APP_IDS,
    STICKY_NOTES_PROTOCOLS,
    close_app,
    find_app,
    launch_app,
    launch_sticky_notes,
    list_known_apps,
    list_app_profiles,
)
