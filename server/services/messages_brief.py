""""Any new messages?" — who wrote, on which platform, without opening anything.

- WhatsApp: read the chat list (names, unread badges, first line of the last
  message) from a background capture of the WhatsApp window. No focus, no clicks,
  no chat opened, so nothing is marked as read. If WhatsApp is minimised it is
  shown without focus for the capture and minimised again.
- Gmail / Outlook: unread mail through their APIs (sender + subject), when connected.

Each source says plainly when it couldn't be checked and why.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from email.utils import parseaddr
from typing import Optional

logger = logging.getLogger("luna.messages_brief")

_TIME = re.compile(r"^(?:\d{1,2}:\d{2}\s*(?:am|pm)?|yesterday|today|monday|tuesday|wednesday|thursday|friday|saturday|"
                   r"sunday|\d{1,2}/\d{1,2}/\d{2,4})$", re.IGNORECASE)
_WHATSAPP_CHROME = {"chats", "all", "unread", "favorites", "groups", "archived", "search or start a new chat",
                    "whatsapp", "messages", "contacts"}


@dataclass
class Item:
    sender: str
    count: int = 1
    preview: str = ""
    when: str = ""


@dataclass
class SourceBrief:
    source: str
    ok: bool
    items: list[Item] = field(default_factory=list)
    note: str = ""


# ── WhatsApp ─────────────────────────────────────────────────────────────────

_TRAILING_TIME = re.compile(r"\s+(\d{1,2}:\d{2}\s*(?:AM|PM)?|Yesterday|Monday|Tuesday|Wednesday|Thursday|Friday|"
                            r"Saturday|Sunday|\d{1,2}/\d{1,2}/\d{2,4})$", re.IGNORECASE)


def _is_badge_green(pixel) -> bool:
    r, g, b = pixel[:3]
    return g > 150 and r < 110 and b < 160 and g - r > 70   # WhatsApp's unread green (#25D366 / #21C063)


def _unread_badge(image, top: float, bottom: float, x0: float, x1: float) -> Optional[int]:
    """The unread count in the green badge at the end of a preview row; 0 if there's no badge; None if unreadable."""
    if image is None:
        return None
    box = (int(x0), int(max(0, top - 6)), int(x1), int(bottom + 6))
    crop = image.crop(box).convert("RGB")
    pixels = [(x, y) for x in range(crop.size[0]) for y in range(crop.size[1]) if _is_badge_green(crop.getpixel((x, y)))]
    if len(pixels) < 25:
        return 0
    xs, ys = [p[0] for p in pixels], [p[1] for p in pixels]
    badge = crop.crop((min(xs), min(ys), max(xs) + 1, max(ys) + 1))
    try:
        from PIL import ImageOps

        from server.services.files.ocr import ocr_image
        big = ImageOps.invert(badge.convert("L")).resize((badge.size[0] * 5, badge.size[1] * 5))
        padded = ImageOps.expand(big, border=40, fill=255).convert("RGB")
        digits = re.sub(r"\D", "", ocr_image(padded).text)
        return int(digits) if digits else None
    except Exception:
        return None


def parse_whatsapp_chat_list(boxes, width: int, image=None) -> tuple[list[Item], str]:
    """Unread chats from the chat list (badges are found by colour, counts read from the badge).
    Returns (items, note)."""
    from server.services.site_reader import _rows

    split = width * 0.41
    left = [b for b in boxes if b.right <= split + 10 and b.top > 90]
    rows = [r for r in _rows(left)]
    note = ""
    texts = [" ".join(b.text for b in r).strip().lower() for r in rows]
    if any(t and "search or start" not in t and t.startswith("q ") for t in texts[:3]):
        note = "WhatsApp is showing a search, so this may not be every chat."
    items: list[Item] = []
    i = 0
    while i < len(rows) - 1:
        row, nxt = rows[i], rows[i + 1]
        # A chat entry: a name row ending in a time, then a preview row (maybe ending in an unread badge).
        times = [b for b in row if _TIME.match(b.text.strip())]
        names = [b for b in row if b not in times and b.left > split * 0.3]
        when = times[0].text.strip() if times else ""
        name = " ".join(b.text for b in names).strip()
        if not when:
            m = _TRAILING_TIME.search(name)
            if m:
                when, name = m.group(1), name[:m.start()].strip()
        if when and name and name.lower() not in _WHATSAPP_CHROME and not _TIME.match(name):
            preview_boxes = sorted([b for b in nxt if b.left > split * 0.3], key=lambda b: b.left)
            badge_digits = [b for b in preview_boxes if re.fullmatch(r"\d{1,3}", b.text.strip()) and b.left > split * 0.75]
            preview_boxes = [b for b in preview_boxes if b not in badge_digits]
            top = min(b.top for b in nxt)
            bottom = max(b.bottom for b in nxt)
            count = int(badge_digits[0].text) if badge_digits else _unread_badge(image, top, bottom, split * 0.72, split)
            if count != 0:
                preview = " ".join(b.text for b in preview_boxes).strip()
                # Read ticks OCR as "V/" or "V" — but only as a separate token ("Voice call" keeps its V).
                preview = re.sub(r"^(?:[vV√✓]{1,2}/?|/)(?:\s+|$)", "", preview)
                items.append(Item(sender=name, count=count or 1, preview=preview[:120], when=when))
            i += 2
            continue
        i += 1
    return items, note


def _hidden_window(process_names: set[str], title: str) -> Optional[dict]:
    """A top-level window of the process even when it's hidden (WhatsApp closed to the background)."""
    import ctypes
    from ctypes import wintypes

    import psutil

    pids = {p.pid for p in psutil.process_iter(["name"]) if (p.info.get("name") or "") in process_names}
    if not pids:
        return None
    user32 = ctypes.WinDLL("user32")
    found: list[dict] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and not user32.GetWindow(hwnd, 4):   # top-level, not owned
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.strip().lower() == title.lower():
                found.append({"hwnd": int(hwnd), "title": buf.value, "pid": pid.value})
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else None


def brief_whatsapp(capture=None, find_window=None, ocr=None, sleep=None) -> SourceBrief:
    import time

    from server.services import verification as V
    from server.services.messaging import WHATSAPP_PROCESSES

    sleep = sleep or time.sleep
    win = (find_window or (lambda: V.window_titled("WhatsApp", WHATSAPP_PROCESSES)))()
    hidden = False
    if not win and find_window is None and V.IS_WINDOWS:
        win = _hidden_window(WHATSAPP_PROCESSES, "WhatsApp")
        hidden = bool(win)
    if not win:
        return SourceBrief("WhatsApp", False, note="WhatsApp isn't running on this computer.")
    image = None
    shown_from = None   # "hidden" or "minimised": how to put it back
    try:
        if capture is None and V.IS_WINDOWS:
            import ctypes
            user32 = ctypes.WinDLL("user32")
            if hidden or not user32.IsWindowVisible(win["hwnd"]):
                shown_from = "hidden"
            elif user32.IsIconic(win["hwnd"]):
                shown_from = "minimised"
            if shown_from:
                user32.ShowWindow(win["hwnd"], 4)   # SW_SHOWNOACTIVATE: shown for the capture, focus untouched
                sleep(1.5)                          # let it draw its chat list
        image = (capture or (lambda: V.capture_window(win["hwnd"])))()
    finally:
        if shown_from:
            import ctypes
            # Back the way it was: hidden (SW_HIDE) or minimised without focus (SW_SHOWMINNOACTIVE).
            ctypes.WinDLL("user32").ShowWindow(win["hwnd"], 0 if shown_from == "hidden" else 7)
    if image is None:
        return SourceBrief("WhatsApp", False, note="Couldn't capture the WhatsApp window.")
    if ocr is None:
        from server.services.files.ocr import ocr_boxes as ocr
    items, note = parse_whatsapp_chat_list(ocr(image), image.size[0], image)
    return SourceBrief("WhatsApp", True, items, note or "From the chats at the top of the list.")


# ── Mail ─────────────────────────────────────────────────────────────────────

def _sender_name(raw: str) -> str:
    name, address = parseaddr(raw or "")
    return (name or address or raw or "unknown").strip().strip('"')


async def brief_gmail(limit: int = 25) -> SourceBrief:
    from server.config import settings
    from server.services.workspace_integrations.base import WorkspaceIntegrationError
    from server.services.workspace_integrations.google import google_workspace

    if not (settings.google_workspace_refresh_token or settings.google_workspace_access_token):
        return SourceBrief("Gmail", False, note="Gmail isn't connected to Luna.")
    try:
        listing = (await google_workspace("gmail", "search_messages",
                                          {"q": "is:unread in:inbox newer_than:2d", "maxResults": limit})).data
        ids = [m["id"] for m in listing.get("messages", []) if m.get("id")]
        metas = await asyncio.gather(*(google_workspace("gmail", "get_message", {"message_id": i, "format": "metadata"})
                                       for i in ids[:limit]), return_exceptions=True)
    except WorkspaceIntegrationError as e:
        return SourceBrief("Gmail", False, note=str(e))
    grouped: dict[str, Item] = {}
    for meta in metas:
        if isinstance(meta, Exception):
            continue
        data = meta.data
        headers = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}
        sender = _sender_name(headers.get("from", ""))
        subject = headers.get("subject", "(no subject)")
        item = grouped.get(sender.lower())
        if item:
            item.count += 1
        else:
            grouped[sender.lower()] = Item(sender=sender, preview=subject[:120])
    estimate = listing.get("resultSizeEstimate") or len(ids)
    note = f"Unread in the last 2 days ({estimate})." if ids else "No unread mail in the last 2 days."
    items = sorted(grouped.values(), key=lambda it: -it.count)
    return SourceBrief("Gmail", True, items, note)


async def brief_outlook(limit: int = 25) -> SourceBrief:
    from server.config import settings
    from server.services.workspace_integrations.base import WorkspaceIntegrationError
    from server.services.workspace_integrations.microsoft import microsoft_workspace

    if not (settings.microsoft_workspace_refresh_token or settings.microsoft_workspace_access_token):
        return SourceBrief("Outlook", False, note="")   # not connected: leave it out quietly
    try:
        data = (await microsoft_workspace("mail", "search_messages", {"limit": limit})).data
    except WorkspaceIntegrationError as e:
        return SourceBrief("Outlook", False, note=str(e))
    grouped: dict[str, Item] = {}
    for m in data.get("value", []):
        if m.get("isRead"):
            continue
        sender = (m.get("from", {}).get("emailAddress", {}) or {})
        name = sender.get("name") or sender.get("address") or "unknown"
        item = grouped.get(name.lower())
        if item:
            item.count += 1
        else:
            grouped[name.lower()] = Item(sender=name, preview=(m.get("subject") or "")[:120])
    return SourceBrief("Outlook", True, sorted(grouped.values(), key=lambda it: -it.count))


# ── Request and reply ────────────────────────────────────────────────────────

_ASKS = re.compile(
    r"\b(?:brief|briefing|summar(?:y|ize|ise)|catch\s+me\s+up|anything\s+new|"
    r"check\s+(?:my\s+|the\s+)?(?:new\s+|unread\s+)?(?:messages?|mails?|e-?mails?|inbox|whats\s*app|gmail|outlook|texts?|chats?)|"
    r"any\s+(?:new\s+|unread\s+)?(?:whats\s*app\s+|gmail\s+|e-?mail\s+|outlook\s+)?"
    r"(?:messages?|texts?|mails?|e-?mails?|dms?|chats?)|who\s+(?:has\s+|have\s+)?(?:messaged|texted|emailed|mailed|wrote|"
    r"written|sent|pinged|contacted)|do\s+i\s+have\s+(?:any\s+)?(?:new\s+|unread\s+)?(?:messages?|texts?|mails?|e-?mails?)|"
    r"unread\s+(?:messages?|texts?|mails?|e-?mails?|chats?)|new\s+(?:messages?|texts?|mails?|e-?mails?))\b",
    re.IGNORECASE)
_ABOUT_MESSAGES = re.compile(r"\b(?:messages?|texts?|mails?|e-?mails?|inbox|whats\s*app|dms?|chats?|gmail|outlook)\b"
                             r"|\bcatch\s+me\s+up\b|\bwho\s+(?:has\s+)?(?:messaged|texted|emailed|wrote|pinged)\b",
                             re.IGNORECASE)


def parse_brief_request(message: str) -> Optional[list[str]]:
    """Which sources to brief on, or None if the message isn't asking for a briefing."""
    text = " ".join((message or "").split())
    if re.match(r"^(?:please\s+)?(?:open|go\s+to|launch|send|text|reply|email|mail)\b", text, re.IGNORECASE):
        return None   # opening or writing, not a briefing
    if not (_ASKS.search(text) and _ABOUT_MESSAGES.search(text)):
        return None
    wants_whatsapp = bool(re.search(r"\bwhats\s*app\b|\btext(?:s|ed)?\b|\bchats?\b|\bdms?\b", text, re.IGNORECASE))
    wants_mail = bool(re.search(r"\b(?:mails?|e-?mail(?:s|ed)?|inbox|gmail|outlook|mailed)\b", text, re.IGNORECASE))
    if wants_whatsapp and not wants_mail:
        return ["whatsapp"]
    if wants_mail and not wants_whatsapp:
        return ["gmail", "outlook"]
    return ["whatsapp", "gmail", "outlook"]


async def brief(sources: list[str]) -> list[SourceBrief]:
    tasks = []
    if "whatsapp" in sources:
        tasks.append(asyncio.to_thread(brief_whatsapp))
    if "gmail" in sources:
        tasks.append(brief_gmail())
    if "outlook" in sources:
        tasks.append(brief_outlook())
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Briefing source failed: %s", r)
            out.append(SourceBrief("messages", False, note=f"Couldn't check: {r}"))
        else:
            out.append(r)
    return out


def describe(briefs: list[SourceBrief], max_items: int = 8) -> str:
    parts = []
    for b in briefs:
        if not b.ok:
            if b.note:
                parts.append(f"**{b.source}** — couldn't check: {b.note}")
            continue
        if not b.items:
            parts.append(f"**{b.source}** — nothing unread." + (f" {b.note}" if b.note and "No unread" not in b.note else ""))
            continue
        total = sum(i.count for i in b.items)
        noun = "chats" if b.source == "WhatsApp" else "senders"
        lines = [f"**{b.source}** — {total} unread from {len(b.items)} {noun if len(b.items) != 1 else noun[:-1]}:"]
        for it in b.items[:max_items]:
            count = f" ({it.count})" if it.count > 1 else ""
            preview = f" — {it.preview}" if it.preview else ""
            lines.append(f"- {it.sender}{count}{preview}")
        if len(b.items) > max_items:
            lines.append(f"- …and {len(b.items) - max_items} more")
        parts.append("\n".join(lines))
    if not parts:
        return "No messaging apps or mail accounts are connected that I can check."
    return "\n\n".join(parts) + "\n\n(I only looked at the lists — nothing was opened or marked as read.)"
