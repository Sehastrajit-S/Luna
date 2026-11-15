"""
Luna system controls package.

Public API — import from here:
  get_volume, set_volume, mute_audio, unmute_audio
  get_brightness, set_brightness
  lock_screen, sleep_system, shutdown_system, restart_system
  turn_off_display
  get_clipboard, set_clipboard
  get_system_info
"""
from backend.services.system_controls.audio import (
    get_volume,
    set_volume,
    mute_audio,
    unmute_audio,
)
from backend.services.system_controls.display import (
    get_brightness,
    set_brightness,
    turn_off_display,
)
from backend.services.system_controls.power import (
    lock_screen,
    sleep_system,
    shutdown_system,
    restart_system,
)
from backend.services.system_controls.clipboard import get_clipboard, set_clipboard
from backend.services.system_controls.info import get_system_info

__all__ = [
    "get_volume", "set_volume", "mute_audio", "unmute_audio",
    "get_brightness", "set_brightness", "turn_off_display",
    "lock_screen", "sleep_system", "shutdown_system", "restart_system",
    "get_clipboard", "set_clipboard",
    "get_system_info",
]
