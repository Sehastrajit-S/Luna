"""PC activity helpers: idle seconds and foreground application name."""


def get_pc_idle_seconds() -> int:
    """Seconds since last keyboard/mouse input (Windows). Returns 0 on failure."""
    try:
        import win32api
        info = win32api.GetLastInputInfo()
        tick = win32api.GetTickCount()
        return int((tick - info) / 1000)
    except Exception:
        return 0


def get_active_app() -> str:
    """Process name of the foreground window (lowercase). Empty string on failure."""
    try:
        import win32gui, win32process, psutil
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""
