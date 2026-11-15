"""
Luna screen perception.
Tools: screenshot, OCR text search, active-window detection, click, type.
All imports are lazy so the module loads even without optional deps.
"""
import os
import tempfile
from typing import Any


def take_screenshot() -> dict[str, Any]:
    """Capture the screen. Returns {path, width, height} or {error}."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        fd, path = tempfile.mkstemp(suffix=".png", prefix="luna_ss_")
        os.close(fd)
        img.save(path)
        return {"path": path, "width": img.width, "height": img.height}
    except ImportError:
        return {"error": "Pillow not installed (pip install pillow)"}
    except Exception as e:
        return {"error": str(e)}


def get_active_window() -> dict[str, Any]:
    """Return the title and process name of the currently focused window."""
    try:
        import win32gui
        import win32process
        import psutil

        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc_name = ""
        try:
            proc_name = psutil.Process(pid).name()
        except Exception:
            pass
        return {"title": title, "process": proc_name, "hwnd": hwnd}
    except ImportError:
        return {"error": "win32gui / psutil not installed"}
    except Exception as e:
        return {"error": str(e)}


def find_text_on_screen(query: str) -> dict[str, Any]:
    """
    Take a screenshot and run OCR. Returns all matching text regions.
    Requires: pytesseract + Pillow + Tesseract-OCR installed on PATH.
    """
    ss = take_screenshot()
    if "error" in ss:
        return ss

    try:
        import pytesseract
        from PIL import Image

        with Image.open(ss["path"]) as img:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        matches = []
        for i, word in enumerate(data["text"]):
            if query.lower() in word.lower():
                x = data["left"][i]
                y = data["top"][i]
                w = data["width"][i]
                h = data["height"][i]
                matches.append({"text": word, "x": x, "y": y, "w": w, "h": h,
                                 "cx": x + w // 2, "cy": y + h // 2})
        try:
            os.unlink(ss["path"])
        except OSError:
            pass
        return {"query": query, "matches": matches, "count": len(matches)}
    except ImportError:
        return {"error": "pytesseract not installed (pip install pytesseract)"}
    except Exception as e:
        return {"error": str(e)}


def click_at(x: int, y: int) -> dict[str, Any]:
    """Move the mouse to (x, y) and click."""
    try:
        import pyautogui
        pyautogui.click(x, y)
        return {"clicked": True, "x": x, "y": y}
    except ImportError:
        return {"error": "pyautogui not installed (pip install pyautogui)"}
    except Exception as e:
        return {"error": str(e)}


def type_text(text: str) -> dict[str, Any]:
    """Type text into the currently focused window."""
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.03)
        return {"typed": True, "length": len(text)}
    except ImportError:
        return {"error": "pyautogui not installed (pip install pyautogui)"}
    except Exception as e:
        return {"error": str(e)}


def execute_screen_tool(tool_name: str, args: dict) -> dict[str, Any]:
    """Dispatch screen tool by name."""
    dispatch = {
        "take_screenshot": lambda: take_screenshot(),
        "get_active_window": lambda: get_active_window(),
        "find_text_on_screen": lambda: find_text_on_screen(args.get("query", "")),
        "click_at": lambda: click_at(int(args.get("x", 0)), int(args.get("y", 0))),
        "type_text": lambda: type_text(args.get("text", "")),
    }
    fn = dispatch.get(tool_name)
    if fn is None:
        return {"error": f"Unknown screen tool: {tool_name}"}
    return fn()
