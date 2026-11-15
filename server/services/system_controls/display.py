"""Brightness and display controls."""
import shutil

from backend.services.system_controls.helpers import IS_MAC, IS_WINDOWS, IS_LINUX, _run, _osascript, _ps


def get_brightness() -> tuple[bool, int | str]:
    if IS_MAC:
        if shutil.which("brightness"):
            rc, out = _run(["brightness", "-l"])
            if rc == 0:
                import re
                m = re.search(r"brightness\s+([0-9.]+)", out)
                if m:
                    return True, int(float(m.group(1)) * 100)
        return False, "Install 'brightness' CLI: brew install brightness"

    if IS_WINDOWS:
        rc, out = _ps(
            "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"
        )
        if rc == 0 and out.strip().isdigit():
            return True, int(out.strip())
        return False, "Could not read brightness (laptop display required)"

    if IS_LINUX:
        for tool in ["brightnessctl", "xbacklight", "light"]:
            if not shutil.which(tool):
                continue
            if tool == "brightnessctl":
                rc, out = _run(["brightnessctl", "get"])
                if rc == 0:
                    rc2, out2 = _run(["brightnessctl", "max"])
                    if rc2 == 0 and out.strip().isdigit() and out2.strip().isdigit():
                        return True, int(int(out.strip()) / int(out2.strip()) * 100)
            elif tool == "xbacklight":
                rc, out = _run(["xbacklight", "-get"])
                if rc == 0:
                    return True, int(float(out.strip()))
            elif tool == "light":
                rc, out = _run(["light", "-G"])
                if rc == 0:
                    return True, int(float(out.strip()))
    return False, "Could not read brightness — install brightnessctl or xbacklight"


def set_brightness(level: int) -> tuple[bool, str]:
    level = max(0, min(100, int(level)))

    if IS_MAC:
        if shutil.which("brightness"):
            rc, out = _run(["brightness", str(level / 100)])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
        return False, "Install 'brightness' CLI: brew install brightness"

    if IS_WINDOWS:
        rc, out = _ps(
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
            f".WmiSetBrightness(1, {level})"
        )
        return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else f"Could not set brightness — {out}")

    if IS_LINUX:
        if shutil.which("brightnessctl"):
            rc, out = _run(["brightnessctl", "set", f"{level}%"])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
        if shutil.which("xbacklight"):
            rc, out = _run(["xbacklight", "-set", str(level)])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
        if shutil.which("light"):
            rc, out = _run(["light", "-S", str(level)])
            return (rc == 0), (f"Brightness set to {level}%" if rc == 0 else out)
    return False, "Could not set brightness — install brightnessctl or xbacklight"


def turn_off_display() -> tuple[bool, str]:
    if IS_WINDOWS:
        import ctypes
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        return True, "Display turned off"

    if IS_MAC:
        rc, out = _run(["pmset", "displaysleepnow"])
        return (rc == 0), ("Display turned off" if rc == 0 else out)

    if IS_LINUX:
        for cmd in [["xset", "dpms", "force", "off"], ["xrandr", "--display", ":0", "--off"]]:
            if shutil.which(cmd[0]):
                rc, out = _run(cmd)
                if rc == 0:
                    return True, "Display turned off"
    return False, "Could not turn off display"
