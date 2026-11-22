"""Keyboard input to a specific window (Windows): focus it, press keys, type text.

Uses SendInput with KEYEVENTF_UNICODE, so any text (emoji, accents, Tamil…)
types correctly regardless of keyboard layout. Every function first checks the
target window is in front, so keys never land in whatever happens to be focused.
"""
from __future__ import annotations

import ctypes
import platform
import time
from ctypes import wintypes

IS_WINDOWS = platform.system() == "Windows"

VK = {"enter": 0x0D, "esc": 0x1B, "tab": 0x09, "back": 0x08, "delete": 0x2E, "ctrl": 0x11, "shift": 0x10,
      "alt": 0x12, "down": 0x28, "up": 0x26, "home": 0x24, "end": 0x23, "pagedown": 0x22, "pageup": 0x21,
      **{chr(c): c for c in range(ord("A"), ord("Z") + 1)}, **{str(d): 0x30 + d for d in range(10)}}

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    INPUT_KEYBOARD, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 1, 0x2, 0x4


class InputError(RuntimeError):
    pass


def _send(inputs: list) -> None:
    array = (INPUT * len(inputs))(*inputs)
    if user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT)) != len(inputs):
        raise InputError("Windows blocked the key presses (another app may have focus lock).")


def _key(vk: int, up: bool = False):
    return INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)))


def foreground() -> int:
    return int(user32.GetForegroundWindow() or 0) if IS_WINDOWS else 0


def focus_window(hwnd: int, timeout: float = 2.0) -> bool:
    """Bring the window to the front. True once it really is the foreground window."""
    if not IS_WINDOWS:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if foreground() == hwnd:
            return True
        # Windows only lets the process that last had input change the foreground window;
        # a tap of Alt counts as input, which lifts that lock.
        _send([_key(VK["alt"]), _key(VK["alt"], up=True)])
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
    return foreground() == hwnd


def _require(hwnd: int, refocus: bool = True) -> None:
    """The window must be in front before any key goes out. Another app taking focus in between
    (a notification, the editor) gets one attempt to bring the window back; otherwise stop."""
    if foreground() == hwnd:
        return
    if refocus and focus_window(hwnd, timeout=1.0):
        time.sleep(0.2)
        return
    raise InputError("The window lost focus, so I stopped instead of typing into something else.")


def press(hwnd: int, *keys: str) -> None:
    """Press a key combination in the window, e.g. press(h, "ctrl", "F")."""
    _require(hwnd)
    codes = [VK[k] if k in VK else VK[k.upper()] for k in keys]
    _send([_key(c) for c in codes] + [_key(c, up=True) for c in reversed(codes)])
    time.sleep(0.12)


def scroll(hwnd: int, notches: int = 7) -> None:
    """Scroll the page under the window's centre with the mouse wheel (works wherever keyboard focus is).
    The pointer is put back where it was."""
    _require(hwnd)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    user32.SetCursorPos((rect.left + rect.right) // 2, rect.top + (rect.bottom - rect.top) * 2 // 3)
    try:
        wheel = INPUT(0, _INPUTUNION(mi=MOUSEINPUT(0, 0, ctypes.c_uint32(-120 * notches & 0xFFFFFFFF).value,
                                                   0x0800, 0, 0)))   # MOUSEEVENTF_WHEEL, negative = down
        _send([wheel])
        time.sleep(0.1)
    finally:
        user32.SetCursorPos(old.x, old.y)


def click(hwnd: int, x: int, y: int) -> None:
    """Left-click at (x, y) inside the window (window coordinates, as in its screenshot). Pointer is put back."""
    _require(hwnd)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if not (0 <= x < rect.right - rect.left and 0 <= y < rect.bottom - rect.top):
        raise InputError("That spot is outside the window.")
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    user32.SetCursorPos(rect.left + x, rect.top + y)
    try:
        time.sleep(0.05)
        _send([INPUT(0, _INPUTUNION(mi=MOUSEINPUT(0, 0, 0, 0x0002, 0, 0))),    # left down
               INPUT(0, _INPUTUNION(mi=MOUSEINPUT(0, 0, 0, 0x0004, 0, 0)))])   # left up
        time.sleep(0.1)
    finally:
        user32.SetCursorPos(old.x, old.y)


def type_text(hwnd: int, text: str) -> None:
    """Type text into the window's focused field. Newlines become Shift+Enter (a line break, not "send")."""
    _require(hwnd)
    for line_index, line in enumerate(text.split("\n")):
        if line_index:
            press(hwnd, "shift", "enter")
        units = line.encode("utf-16-le")
        inputs = []
        for i in range(0, len(units), 2):
            code = int.from_bytes(units[i:i + 2], "little")
            inputs.append(INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0))))
            inputs.append(INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))))
        for start in range(0, len(inputs), 64):
            # Mid-text, losing focus means part of the text went elsewhere: stop rather than refocus.
            _require(hwnd, refocus=start == 0 and line_index == 0)
            _send(inputs[start:start + 64])
            time.sleep(0.02)
