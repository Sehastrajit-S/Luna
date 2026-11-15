# Backward-compat shim — all logic lives in backend.services.system_controls package
from backend.services.system_controls import *  # noqa: F401, F403
from backend.services.system_controls import (
    get_volume, set_volume, mute_audio, unmute_audio,
    get_brightness, set_brightness, turn_off_display,
    lock_screen, sleep_system, shutdown_system, restart_system,
    get_clipboard, set_clipboard,
    get_system_info,
)
