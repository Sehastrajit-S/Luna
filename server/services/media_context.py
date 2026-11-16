"""
Lightweight Windows media context.

This does not inspect video frames or bypass app privacy. It only reads visible
window titles, which is enough for many browsers and media players.
"""
import re
from dataclasses import dataclass

try:
    import win32gui
except ImportError:
    win32gui = None


MEDIA_TITLE_HINTS = {
    "netflix",
    "prime video",
    "hulu",
    "disney+",
    "youtube",
    "crunchyroll",
    "vlc",
    "media player",
    "movies & tv",
    "apple tv",
    "max",
    "plex",
    "jellyfin",
    "stremio",
}

BROWSER_SUFFIXES = [
    " - Google Chrome",
    " - Microsoft Edge",
    " - Mozilla Firefox",
    " - Brave",
    " - Opera",
]


@dataclass
class WatchingContext:
    title: str
    cleaned_title: str
    source: str
    confidence: float

    def as_prompt_text(self) -> str:
        if not self.title:
            return "No visible media window detected."
        return (
            f"Visible watching context: {self.cleaned_title}\n"
            f"Source/window: {self.source or self.title}\n"
            f"Confidence: {self.confidence:.2f}"
        )


def _clean_title(title: str) -> str:
    cleaned = " ".join(title.split())
    for suffix in BROWSER_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break

    noisy_suffixes = [
        " - Netflix",
        " - Prime Video",
        " - YouTube",
        " - Hulu",
        " - Disney+",
        " - Crunchyroll",
    ]
    for suffix in noisy_suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break

    return cleaned.strip()


def _score_title(title: str) -> float:
    lower = title.lower()
    score = 0.0
    if any(hint in lower for hint in MEDIA_TITLE_HINTS):
        score += 0.55
    if re.search(r"\b(?:s\d{1,2}\s*e\d{1,2}|season\s+\d+|episode\s+\d+|ep\.?\s*\d+)\b", lower):
        score += 0.35
    if " - " in title:
        score += 0.1
    return min(score, 1.0)


def get_foreground_window_title() -> str:
    if win32gui is None:
        return ""
    try:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd).strip()
    except Exception:
        return ""


def get_watching_context() -> WatchingContext:
    title = get_foreground_window_title()
    if not title:
        return WatchingContext("", "", "", 0.0)

    cleaned = _clean_title(title)
    confidence = _score_title(title)
    if confidence < 0.3:
        return WatchingContext("", "", title, confidence)

    return WatchingContext(
        title=title,
        cleaned_title=cleaned or title,
        source=title,
        confidence=confidence,
    )
