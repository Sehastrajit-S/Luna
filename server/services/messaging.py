"""Send a WhatsApp message to a contact by name, checking every step on screen.

Only runs after the user said yes (the message_contact tool is risky). Steps:

1. Bring WhatsApp to the front (start it if needed).
2. Search the contact (Ctrl+F, type the name). Check a chat with that name is in the results.
3. Open the first result. Check the chat header shows that name — otherwise stop.
4. Check the message box is empty (no half-written draft) — otherwise stop.
5. Type the message. Check it's in the message box — otherwise clear it and stop.
6. Press Enter. Check the message box emptied and the message shows as the last one.

Each check reads the WhatsApp window with OCR, so it works on the real screen and
not on assumptions. A screenshot of the final state is saved as evidence. Nothing
is sent if any check before step 6 fails.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Optional

logger = logging.getLogger("luna.messaging")

WHATSAPP_PROCESSES = {"WhatsApp.Root.exe", "WhatsApp.exe"}
PLACEHOLDER = "type a message"
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}\s*(?:am|pm)?\s*[✓√v/\\]*$", re.IGNORECASE)


class MessageError(Exception):
    """kind: unavailable | not_found | wrong_chat | draft | typing | not_sent | focus"""

    def __init__(self, kind: str, message: str, screenshot: str | None = None):
        super().__init__(message)
        self.kind, self.message, self.screenshot = kind, message, screenshot


@dataclass
class SendResult:
    app: str
    to: str
    chat: str
    text: str
    screenshot: Optional[str] = None
    steps: list[str] = field(default_factory=list)


# ── Reading the WhatsApp window ──────────────────────────────────────────────

def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def similar(a: str, b: str) -> float:
    a, b = _squash(a), _squash(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def names_match(wanted: str, shown: str) -> bool:
    """The chat shown is the contact asked for. Every word of the name must be there."""
    shown_s = _squash(shown)
    words = [w for w in re.findall(r"[a-z0-9]+", (wanted or "").lower()) if w]
    if not words or not shown_s:
        return False
    if all(w in shown_s for w in words):
        return True
    # A long name cut short in the chat list: "Alexandra Mo... (You)".
    cut = re.split(r"\.\.\.|…", shown or "", maxsplit=1)
    if len(cut) == 2 and len(_squash(cut[0])) >= 6 and _squash(wanted).startswith(_squash(cut[0])):
        return True
    return similar(wanted, shown) >= 0.85   # OCR slips ("Alexandra Mor..." truncation aside)


@dataclass
class Screen:
    """The OCR'd WhatsApp window, split into its regions."""
    width: int
    height: int
    boxes: list   # OcrBox

    @property
    def split(self) -> float:
        """Where the conversation pane starts: just left of the chat header (avatar + name)."""
        header = [b for b in self.boxes if 30 <= b.top and b.bottom <= 115 and b.left > self.width * 0.3]
        if header:
            return min(b.left for b in header) - 75
        return self.width * 0.42

    def _region(self, top: float, bottom: float, right_pane: bool) -> list:
        return [b for b in self.boxes if b.top >= top and b.bottom <= bottom
                and ((b.left >= self.split) if right_pane else (b.right <= self.split * 1.45))]

    def header(self) -> str:
        boxes = sorted(self._region(30, 115, True), key=lambda b: (b.top, b.left))
        return " ".join(b.text for b in boxes[:3])

    def composer(self) -> str:
        boxes = sorted(self._region(self.height - 80, self.height, True), key=lambda b: b.left)
        return " ".join(b.text for b in boxes)

    def composer_empty(self) -> bool:
        return _squash(PLACEHOLDER) in _squash(self.composer()) or not self.composer().strip()

    def messages(self) -> list[str]:
        """Text in the conversation, top to bottom, timestamps dropped."""
        boxes = sorted(self._region(115, self.height - 80, True), key=lambda b: (b.top, b.left))
        return [b.text for b in boxes if not _TIME_RE.match(b.text.strip())]

    def chat_results(self) -> list[str]:
        """Names in the search results' "Chats" section (left pane)."""
        left = sorted(self._region(115, self.height, False), key=lambda b: b.top)
        names, in_chats = [], False
        for b in left:
            label = b.text.strip().lower()
            if label == "chats":
                in_chats = True
                continue
            if label in ("messages", "contacts", "groups", "other contacts"):
                if in_chats:
                    break
                continue
            if in_chats and b.left < self.split * 0.6 + 60:
                names.append(b.text.strip())
        return names


def read_screen(capture: Callable[[], object]) -> tuple[Screen, object]:
    from server.services.files.ocr import ocr_boxes
    image = capture()
    if image is None:
        raise MessageError("unavailable", "Couldn't see the WhatsApp window (is it minimised?).")
    return Screen(image.size[0], image.size[1], ocr_boxes(image)), image


# ── Sending ──────────────────────────────────────────────────────────────────

def _whatsapp_window():
    from server.services import verification as V
    return V.window_titled("WhatsApp", WHATSAPP_PROCESSES)


def _start_whatsapp(sleep) -> Optional[dict]:
    from server.services.app_launcher import launch_app
    ok, _msg = launch_app("whatsapp")
    if not ok:
        return None
    for _ in range(20):
        sleep(0.5)
        win = _whatsapp_window()
        if win:
            sleep(2.0)   # let it finish loading chats
            return win
    return None


def send_whatsapp(to: str, text: str, *, keys=None, capture=None, window=None,
                  sleep: Callable[[float], None] = time.sleep, save=None) -> SendResult:
    """Send `text` to the WhatsApp chat named `to`. Raises MessageError (and sends nothing) if a check fails."""
    from server.services import desktop_input as K_default
    from server.services import verification as V

    K = keys or K_default
    to, text = " ".join((to or "").split()), (text or "").strip()
    if not to or not text:
        raise MessageError("not_found", "Say who to message and what to send.")
    result = SendResult(app="WhatsApp", to=to, chat="", text=text)

    win = window or _whatsapp_window() or _start_whatsapp(sleep)
    if not win:
        raise MessageError("unavailable", "WhatsApp isn't installed or didn't open.")
    hwnd = win["hwnd"]
    capture = capture or (lambda: V.capture_window(hwnd))
    save = save or (lambda image, label: V.save_screenshot(image, label))
    previous = K.foreground()

    def evidence(image, label):
        try:
            return save(image, label)
        except Exception:
            return None

    try:
        if not K.focus_window(hwnd):
            raise MessageError("focus", "Couldn't bring WhatsApp to the front, so I didn't type anything.")
        result.steps.append("WhatsApp is in front")

        # 2–3. Find the chat, open it, check the header.
        screen, image = _open_chat(K, hwnd, to, capture, sleep, evidence, result)

        # 4. No draft in the way.
        if not screen.composer_empty():
            raise MessageError("draft", f"There's an unsent draft in the chat with {to} ('{screen.composer()[:60]}'). "
                                        "I left it alone and sent nothing.", evidence(image, "whatsapp-draft"))

        # 5. Type and check.
        try:
            K.type_text(hwnd, text)
        except Exception as e:
            _clear_composer(K, hwnd)
            raise MessageError("focus", f"Typing was interrupted ({e}). I cleared the message box; nothing was sent.") from e
        sleep(0.8)
        screen, image = read_screen(capture)
        typed = screen.composer()
        first_line = text.split("\n")[0]
        if similar(first_line[:60], typed) < 0.75:
            K.press(hwnd, "ctrl", "A")
            K.press(hwnd, "delete")
            raise MessageError("typing", f"The message box shows '{typed[:60]}' instead of the message, so I cleared "
                                         "it and sent nothing.", evidence(image, "whatsapp-typing"))
        result.steps.append("message typed and checked in the message box")

        # 6. Send and check.
        K.press(hwnd, "enter")
        sleep(1.5)
        screen, image = read_screen(capture)
        recent = " ".join(screen.messages()[-6:])
        sent = screen.composer_empty() and similar(text.split("\n")[-1][:60], recent) >= 0.75
        result.screenshot = evidence(image, "whatsapp-sent")
        if not sent:
            raise MessageError("not_sent", "I pressed send, but I can't see the message in the chat. Please check "
                                           "WhatsApp.", result.screenshot)
        result.steps.append("message shows in the chat and the message box is empty")
        return result
    except MessageError:
        raise
    except Exception as e:   # key input refused, focus lost before typing, OCR missing…
        raise MessageError("focus", f"Stopped before sending: {e}. Nothing was sent.") from e
    finally:
        if previous and previous != hwnd:
            try:
                K.focus_window(previous, timeout=0.6)   # hand focus back to where the user was
            except Exception:
                pass


def _open_chat(K, hwnd, to: str, capture, sleep, evidence, result: SendResult):
    """Search WhatsApp for `to`, open the chat and check its header. Returns the screen it shows."""
    K.press(hwnd, "esc")
    K.press(hwnd, "ctrl", "F")
    K.press(hwnd, "ctrl", "A")
    K.type_text(hwnd, to)
    sleep(1.5)
    screen, image = read_screen(capture)
    results = screen.chat_results()
    if not any(names_match(to, r) for r in results):
        K.press(hwnd, "esc")
        seen = ", ".join(results[:5]) or "none"
        raise MessageError("not_found", f"No WhatsApp chat called '{to}'. Chats found: {seen}.",
                           evidence(image, "whatsapp-not-found"))
    result.steps.append(f"found '{to}' in the chat search")

    K.press(hwnd, "down")
    K.press(hwnd, "enter")
    sleep(1.5)
    screen, image = read_screen(capture)
    header = screen.header()
    if not names_match(to, header):
        raise MessageError("wrong_chat", f"The chat that opened is '{header or 'unknown'}', not '{to}', "
                                         "so I didn't type anything.", evidence(image, "whatsapp-wrong-chat"))
    result.chat = header
    result.steps.append(f"chat header shows '{header}'")
    return screen, image


def open_whatsapp_chat(to: str, *, keys=None, capture=None, window=None,
                       sleep: Callable[[float], None] = time.sleep, save=None) -> SendResult:
    """Open the WhatsApp chat named `to` and leave it on screen. Types nothing into the chat."""
    from server.services import desktop_input as K_default
    from server.services import verification as V

    K = keys or K_default
    to = " ".join((to or "").split())
    if not to:
        raise MessageError("not_found", "Say whose chat to open.")
    result = SendResult(app="WhatsApp", to=to, chat="", text="")
    win = window or _whatsapp_window() or _start_whatsapp(sleep)
    if not win:
        raise MessageError("unavailable", "WhatsApp isn't installed or didn't open.")
    hwnd = win["hwnd"]
    capture = capture or (lambda: V.capture_window(hwnd))
    save = save or (lambda image, label: V.save_screenshot(image, label))

    def evidence(image, label):
        try:
            return save(image, label)
        except Exception:
            return None

    try:
        if not K.focus_window(hwnd):
            raise MessageError("focus", "Couldn't bring WhatsApp to the front.")
        result.steps.append("WhatsApp is in front")
        _screen, image = _open_chat(K, hwnd, to, capture, sleep, evidence, result)
        result.screenshot = evidence(image, "whatsapp-chat")
        return result
    except MessageError:
        raise
    except Exception as e:
        raise MessageError("focus", f"Stopped before opening the chat: {e}.") from e


def describe_open(result: SendResult) -> str:
    shot = f" Screenshot: {result.screenshot}" if result.screenshot else ""
    return f"Opened your WhatsApp chat with {result.to}. Checks: {'; '.join(result.steps)}.{shot}"


# "open Meera's chat", "open my chat with Meera on WhatsApp", "open Meera's chat and WhatsApp" (sic, speech)
_OPEN_CHAT = re.compile(
    r"^(?:no[,.]?\s+|ok(?:ay)?[,.]?\s+|please\s+|(?:can|could|would)\s+you\s+)*(?:open|show|go\s+to|pull\s+up)\s+"
    r"(?:up\s+)?(?:(?:my|the)\s+)?"
    r"(?:(?P<a>[\w .'-]{2,40}?)(?:'s|’s|s')\s+(?:whatsapp\s+)?chat"
    r"|(?:whatsapp\s+)?chat\s+with\s+(?P<b>[\w .'-]{2,40}?))"
    r"(?:\s+(?:in|on|and|from)\s+(?:the\s+)?whatsapp(?:\s+app)?)?(?:\s+please)?[\s.?!]*$",
    re.IGNORECASE)


def parse_open_chat(message: str) -> Optional[str]:
    """The contact name in "open Meera's chat", or None."""
    match = _OPEN_CHAT.match(" ".join((message or "").split()))
    if not match:
        return None
    name = (match.group("a") or match.group("b") or "").strip(" .'")
    return name if name and name.lower() not in {"the", "my", "a", "this", "that", "whatsapp", "group"} else None


_LEAD = r"^(?:(?:no|ok(?:ay)?|hey\s+luna|luna)[,.]?\s+)?(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?" \
        r"(?:(?:open|go\s+to)\s+whats\s*app\s+and\s+)?"
_ON_WA = r"\s+(?:on|in|via|through|over|using)\s+whats\s*app(?:\s+please)?[\s.!?]*$"
_SEND_PATTERNS = [
    # send hi to Arjun on WhatsApp / send "I'm late" to Priya Raman on WhatsApp
    re.compile(_LEAD + r"(?:send|say|write)\s+(?P<text>.+?)\s+to\s+(?P<to>[\w .'-]{2,40}?)" + _ON_WA, re.I),
    # send Arjun a message saying hi on WhatsApp / text Priya that I'm late on WhatsApp
    re.compile(_LEAD + r"(?:send|text|message|msg|tell|ping|whats\s*app)\s+(?P<to>[\w .'-]{2,40}?)\s+"
               r"(?:an?\s+(?:message|text|msg)\s+)?(?:saying|that|:)\s*(?P<text>.+?)" + _ON_WA, re.I),
    # send Arjun hi on WhatsApp / text Priya I'm late on WhatsApp  (name = one word; the approval shows the split)
    re.compile(_LEAD + r"(?:send|text|message|msg|tell|ping)\s+(?P<to>[A-Za-z][\w'-]{1,30})\s+"
               r"(?:an?\s+(?:message|text|msg)\s+)?(?P<text>.+?)" + _ON_WA, re.I),
    # open WhatsApp and text Mom I reached
    re.compile(r"^(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:open|go\s+to)\s+whats\s*app\s+and\s+"
               r"(?:send|text|message|msg|tell)\s+(?P<to>[A-Za-z][\w'-]{1,30})\s+(?:an?\s+(?:message|text|msg)\s+)?"
               r"(?:saying\s+|that\s+|:\s*)?(?P<text>.+?)[\s.!?]*$", re.I),
    # WhatsApp Arjun saying hi
    re.compile(_LEAD + r"whats\s*app\s+(?P<to>[\w .'-]{2,40}?)\s+(?:saying|that|:)\s*(?P<text>.+?)[\s.!?]*$", re.I),
]


def parse_send_request(message: str) -> Optional[tuple[str, str]]:
    """(contact, text) for "send Arjun hi on WhatsApp"-style requests, else None.

    Only requests that name WhatsApp: everything else is left to the agent. The user
    approves the exact contact and text before anything is typed."""
    text = " ".join((message or "").split())
    for pattern in _SEND_PATTERNS:
        match = pattern.match(text)
        if match:
            to = match.group("to").strip(" .'")
            body = match.group("text").strip().strip("\"“”'‘’").strip()
            if to and body and to.lower() not in {"a", "the", "my", "him", "her", "them", "it", "message", "text"}:
                return to, body
    return None


# conversation id → (contact, when): who "send him …" means right after a send.
_LAST_CONTACT: dict[int, tuple[str, float]] = {}
FOLLOW_UP_S = 15 * 60
_FOLLOW_UP = re.compile(
    r"^(?:(?:ok(?:ay)?|now|also|and|then)[,\s]+)*(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?(?:also\s+)?"
    r"(?:send|text|message|tell)\s+(?:(?:him|her|them)\s+)?(?:(?:another\s+(?:one|message)|again)\s+)?"
    r"(?:(?:saying|that)\s+|:\s*)?(?P<text>.+?)[\s]*$", re.IGNORECASE)
_NOT_A_MESSAGE = re.compile(r"^(?:me|it|this\s+file|the\s+\w+\s+to|an?\s+(?:email|mail)\b)|\bto\s+[A-Z]\w+\s*[.!?]?$|"
                            r"\b(?:e-?mail|gmail|outlook|slack)\b", re.IGNORECASE)


def remember_contact(conversation_id: Optional[int], to: str) -> None:
    if conversation_id:
        _LAST_CONTACT[conversation_id] = (to, time.monotonic())


def parse_follow_up_send(conversation_id: Optional[int], message: str) -> Optional[tuple[str, str]]:
    """(contact, text) for "send him this is from Luna" soon after a WhatsApp send in this conversation."""
    entry = _LAST_CONTACT.get(conversation_id or 0)
    if not entry or time.monotonic() - entry[1] > FOLLOW_UP_S:
        return None
    match = _FOLLOW_UP.match(" ".join((message or "").split()))
    if not match:
        return None
    body = match.group("text").strip().strip("\"“”'‘’").strip()
    if not body or _NOT_A_MESSAGE.search(body):
        return None
    return entry[0], body


def _clear_composer(K, hwnd) -> None:
    try:
        if K.focus_window(hwnd, timeout=1.0):
            K.press(hwnd, "ctrl", "A")
            K.press(hwnd, "delete")
    except Exception:
        pass


def describe(result: SendResult) -> str:
    checks = "; ".join(result.steps)
    shot = f" Screenshot: {result.screenshot}" if result.screenshot else ""
    return f"Sent to {result.to} on WhatsApp: “{result.text}”. Checks: {checks}.{shot}"
