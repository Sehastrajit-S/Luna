"""Clipboard read/write controls."""
import shutil
import subprocess

from backend.services.system_controls.helpers import IS_MAC, IS_WINDOWS, IS_LINUX, _run, _ps


def get_clipboard() -> tuple[bool, str]:
    if IS_WINDOWS:
        rc, out = _ps("Get-Clipboard")
        return (rc == 0), out

    if IS_MAC:
        rc, out = _run(["pbpaste"])
        return (rc == 0), out

    if IS_LINUX:
        for tool, args in [
            ("xclip", ["-selection", "clipboard", "-o"]),
            ("xsel",  ["--clipboard", "--output"]),
            ("wl-paste", []),
        ]:
            if shutil.which(tool):
                rc, out = _run([tool] + args)
                if rc == 0:
                    return True, out
    return False, "Could not read clipboard"


def set_clipboard(text: str) -> tuple[bool, str]:
    if IS_WINDOWS:
        rc, out = _ps(f"Set-Clipboard -Value '{text.replace(chr(39), chr(34))}'")
        return (rc == 0), ("Copied to clipboard" if rc == 0 else out)

    if IS_MAC:
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(text.encode())
        return True, "Copied to clipboard"

    if IS_LINUX:
        for tool, args in [
            ("xclip", ["-selection", "clipboard"]),
            ("xsel",  ["--clipboard", "--input"]),
            ("wl-copy", []),
        ]:
            if shutil.which(tool):
                proc = subprocess.Popen([tool] + args, stdin=subprocess.PIPE)
                proc.communicate(text.encode())
                return True, "Copied to clipboard"
    return False, "Could not write to clipboard — install xclip or xsel"
