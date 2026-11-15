"""Volume and mute controls."""
import shutil

from backend.services.system_controls.helpers import IS_MAC, IS_WINDOWS, IS_LINUX, _run, _osascript, _ps


def _win_endpoint():
    """The default speakers' master volume control (Windows Core Audio), or None.

    Replaces PowerShell: SAPI.SpVoice.Volume was the text-to-speech voice's
    volume, not the speakers', and PowerShell often missed its 5 s timeout.
    """
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities
        try:
            comtypes.CoInitialize()              # each thread needs COM; a repeat call is harmless
        except OSError:
            pass
        return AudioUtilities.GetSpeakers().EndpointVolume
    except Exception:
        return None


def get_volume() -> tuple[bool, int | str]:
    if IS_MAC:
        rc, out = _osascript("output volume of (get volume settings)")
        if rc == 0 and out.strip().isdigit():
            return True, int(out.strip())
        return False, f"osascript error: {out}"

    if IS_WINDOWS:
        endpoint = _win_endpoint()
        if endpoint is None:
            return False, "Could not read system volume on Windows (no audio output device found)"
        level = round(endpoint.GetMasterVolumeLevelScalar() * 100)
        return True, (f"{level}% (muted)" if endpoint.GetMute() else level)

    if shutil.which("pactl"):
        rc, out = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        if rc == 0:
            import re
            m = re.search(r"(\d+)%", out)
            if m:
                return True, int(m.group(1))
    if shutil.which("amixer"):
        rc, out = _run(["amixer", "get", "Master"])
        if rc == 0:
            import re
            m = re.search(r"\[(\d+)%\]", out)
            if m:
                return True, int(m.group(1))
    return False, "Could not read volume — install pulseaudio-utils or alsa-utils"


def set_volume(level: int) -> tuple[bool, str]:
    level = max(0, min(100, int(level)))

    if IS_MAC:
        rc, out = _osascript(f"set volume output volume {level}")
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)

    if IS_WINDOWS:
        endpoint = _win_endpoint()
        if endpoint is not None:
            endpoint.SetMasterVolumeLevelScalar(level / 100, None)
            return True, f"Volume set to {round(endpoint.GetMasterVolumeLevelScalar() * 100)}%"
        if shutil.which("nircmd"):
            nircmd_val = int(level * 655.35)
            rc, out = _run(["nircmd", "setsysvolume", str(nircmd_val)])
            return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
        script = (
            f"$wsh = New-Object -ComObject wscript.shell;"
            f"1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }};"
            f"$steps = [math]::Round({level} / 2);"
            f"1..$steps | ForEach-Object {{ $wsh.SendKeys([char]175) }}"
        )
        _ps(script)
        return True, f"Volume adjusted to approximately {level}%"

    if shutil.which("pactl"):
        rc, out = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
    if shutil.which("amixer"):
        rc, out = _run(["amixer", "-q", "set", "Master", f"{level}%"])
        return (rc == 0), (f"Volume set to {level}%" if rc == 0 else out)
    return False, "Could not set volume — install pulseaudio-utils or alsa-utils"


def mute_audio() -> tuple[bool, str]:
    if IS_MAC:
        rc, out = _osascript("set volume with output muted")
        return (rc == 0), ("Audio muted" if rc == 0 else out)

    if IS_WINDOWS:
        endpoint = _win_endpoint()                # the mute key below only toggles
        if endpoint is not None:
            endpoint.SetMute(1, None)
            return True, "Audio muted"
        if shutil.which("nircmd"):
            rc, out = _run(["nircmd", "mutesysvolume", "1"])
            return (rc == 0), ("Audio muted" if rc == 0 else out)
        _ps("$wsh = New-Object -ComObject wscript.shell; $wsh.SendKeys([char]173)")
        return True, "Audio muted"

    if IS_LINUX:
        if shutil.which("pactl"):
            rc, out = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
            return (rc == 0), ("Audio muted" if rc == 0 else out)
        if shutil.which("amixer"):
            rc, out = _run(["amixer", "-q", "set", "Master", "mute"])
            return (rc == 0), ("Audio muted" if rc == 0 else out)
    return False, "Could not mute audio on this platform"


def unmute_audio() -> tuple[bool, str]:
    if IS_MAC:
        rc, out = _osascript("set volume without output muted")
        return (rc == 0), ("Audio unmuted" if rc == 0 else out)

    if IS_WINDOWS:
        endpoint = _win_endpoint()
        if endpoint is not None:
            endpoint.SetMute(0, None)
            return True, "Audio unmuted"
        if shutil.which("nircmd"):
            rc, out = _run(["nircmd", "mutesysvolume", "0"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
        _ps("$wsh = New-Object -ComObject wscript.shell; $wsh.SendKeys([char]173)")
        return True, "Audio toggled"

    if IS_LINUX:
        if shutil.which("pactl"):
            rc, out = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
        if shutil.which("amixer"):
            rc, out = _run(["amixer", "-q", "set", "Master", "unmute"])
            return (rc == 0), ("Audio unmuted" if rc == 0 else out)
    return False, "Could not unmute audio on this platform"
