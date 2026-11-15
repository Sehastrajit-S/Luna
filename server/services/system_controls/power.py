"""Lock, sleep, shutdown, restart controls."""
import shutil

from backend.services.system_controls.helpers import IS_MAC, IS_WINDOWS, IS_LINUX, PLATFORM, _run, _osascript, _ps


def lock_screen() -> tuple[bool, str]:
    if IS_WINDOWS:
        rc, out = _run(["rundll32.exe", "user32.dll,LockWorkStation"])
        return (rc == 0), ("Screen locked" if rc == 0 else out)

    if IS_MAC:
        rc, out = _osascript(
            'tell application "System Events" to keystroke "q" '
            'using {command down, control down}'
        )
        if rc != 0:
            rc, out = _run(
                ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                 "-suspend"]
            )
        return (rc == 0), ("Screen locked" if rc == 0 else out)

    if IS_LINUX:
        for cmd in [
            ["loginctl", "lock-session"],
            ["xdg-screensaver", "lock"],
            ["gnome-screensaver-command", "--lock"],
            ["xscreensaver-command", "-lock"],
            ["qdbus", "org.kde.screensaver", "/ScreenSaver", "Lock"],
            ["slock"],
            ["i3lock"],
        ]:
            if shutil.which(cmd[0]):
                rc, out = _run(cmd)
                if rc == 0:
                    return True, "Screen locked"
        return False, "Could not lock screen — install loginctl or xdg-screensaver"

    return False, f"Lock screen not supported on {PLATFORM}"


def sleep_system() -> tuple[bool, str]:
    if IS_WINDOWS:
        rc, out = _ps("Add-Type -Assembly System.Windows.Forms; "
                      "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)")
        if rc != 0:
            rc, out = _run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
        return (rc == 0), ("System going to sleep" if rc == 0 else out)

    if IS_MAC:
        rc, out = _run(["pmset", "sleepnow"])
        return (rc == 0), ("System going to sleep" if rc == 0 else out)

    if IS_LINUX:
        for cmd in [["systemctl", "suspend"], ["pm-suspend"], ["loginctl", "suspend"]]:
            if shutil.which(cmd[0]):
                rc, out = _run(cmd)
                if rc == 0:
                    return True, "System going to sleep"
        return False, "Could not suspend — install systemd or pm-utils"

    return False, f"Sleep not supported on {PLATFORM}"


def shutdown_system(delay_seconds: int = 0) -> tuple[bool, str]:
    if IS_WINDOWS:
        rc, out = _run(["shutdown", "/s", "/t", str(delay_seconds)])
        return (rc == 0), (f"Shutting down in {delay_seconds}s" if rc == 0 else out)

    if IS_MAC:
        rc, out = _osascript('tell app "System Events" to shut down')
        return (rc == 0), ("Shutting down" if rc == 0 else out)

    if IS_LINUX:
        rc, out = _run(["systemctl", "poweroff"])
        return (rc == 0), ("Shutting down" if rc == 0 else out)

    return False, f"Shutdown not supported on {PLATFORM}"


def restart_system(delay_seconds: int = 0) -> tuple[bool, str]:
    if IS_WINDOWS:
        rc, out = _run(["shutdown", "/r", "/t", str(delay_seconds)])
        return (rc == 0), (f"Restarting in {delay_seconds}s" if rc == 0 else out)

    if IS_MAC:
        rc, out = _osascript('tell app "System Events" to restart')
        return (rc == 0), ("Restarting" if rc == 0 else out)

    if IS_LINUX:
        rc, out = _run(["systemctl", "reboot"])
        return (rc == 0), ("Restarting" if rc == 0 else out)

    return False, f"Restart not supported on {PLATFORM}"
