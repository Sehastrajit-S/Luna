""""Scan this and …": a photo plus what to do with it, mostly from voice-only mode.

The photo arrives as a chat attachment; the words say the task:
- "scan this (QR) and fill the form"   → open the QR's link, fill it with the user's own details
- "scan this and fill the form"        → read the details printed on the page, fill the form open in the browser
- "scan it and find prices at stores"  → barcode → product (or the vision model names it) → store price comparison
- "scan this" on a QR with no task     → open its link
- anything else ("what does this say") → the normal chat pipeline, with the photo

Forms are filled but never submitted here; "submit it" afterwards does that, and
only for a form filled in the same conversation in the last 15 minutes.
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("luna.scan_tasks")

SCAN_RE = re.compile(r"\bscan(?:ned|ning)?\b", re.IGNORECASE)
FORM_RE = re.compile(r"\b(?:fill|form|apply|application|register|sign\s*(?:me\s+)?up|enrol+)\b", re.IGNORECASE)
PRICE_RE = re.compile(r"\b(?:prices?|cost|cheap(?:er|est)?|compare|stores?|shops?|how\s+much|deals?|buy)\b", re.IGNORECASE)
SUBMIT_RE = re.compile(r"^(?:ok(?:ay)?[, ]+|yes[, ]+|yeah[, ]+|go\s+ahead[, ]+(?:and\s+)?|please\s+)*submit(?:\s+(?:it|the\s+form|"
                       r"that|now|the\s+application))?(?:\s+please)?[.!]*$", re.IGNORECASE)
_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)

# conversation id → (form window title, when filled)
_FILLED: dict[int, tuple[str, float]] = {}
SUBMIT_WINDOW_S = 15 * 60


@dataclass
class ScanOutcome:
    reply: Optional[str] = None      # answer the user directly
    rewrite: Optional[str] = None    # or: continue the normal pipeline with this message instead


def is_scan_request(text: str) -> bool:
    return bool(SCAN_RE.search(text or ""))


def reads_photo_itself(text: str) -> bool:
    """True when the scan handler, not the chat model, reads the photo for this request."""
    return is_scan_request(text) and (intent(text) != "other" or is_bare_scan(text))


def intent(text: str) -> str:
    if FORM_RE.search(text or ""):
        return "form"
    if PRICE_RE.search(text or ""):
        return "prices"
    return "other"


def image_bytes(db, attachment_ids: list[str]) -> Optional[bytes]:
    """The first image among the message's attachments."""
    from server.models.database import Attachment
    from server.services.files.service import original_path
    for attachment_id in attachment_ids or []:
        row = db.query(Attachment).filter_by(id=attachment_id).first()
        if row and row.kind == "image":
            try:
                return original_path(row).read_bytes()
            except OSError:
                continue
    return None


async def handle(db, conversation_id: Optional[int], text: str, data: bytes) -> ScanOutcome:
    from server.services.shopping.barcode import decode_qr

    task = intent(text)
    link = await asyncio.to_thread(decode_qr, data)
    if link and not _URL.match(link):
        link_text, link = link, None
    else:
        link_text = None

    if task == "form":
        return await _fill(db, conversation_id, data, link)
    if task == "prices":
        return await _prices(data)
    if link:
        return ScanOutcome(reply=await _open_link(link))
    if link_text:
        return ScanOutcome(reply=f"The QR code says: “{link_text[:300]}”.")
    if is_bare_scan(text):
        # Just "scan this": say what it is, from this photo only (the chat model also
        # sees earlier photos in the conversation and mixed them in).
        return ScanOutcome(reply=await _identify(data))
    return ScanOutcome()   # "what does this say?" etc.: the normal pipeline reads the photo


_BARE_SCAN = re.compile(
    r"^(?:(?:hey|hi|ok(?:ay)?)\s+)?(?:luna[,\s]+)?(?:(?:can|could|would|will)\s+you\s+)?(?:please\s+)?"
    r"(?:just\s+)?scan\s+(?:this|it|that|me\s+this)"
    r"(?:\s+(?:one|thing|item|product|label|code|barcode|qr(?:\s+code)?|for\s+me|please|now))*[\s.?!]*$",
    re.IGNORECASE)


def is_bare_scan(text: str) -> bool:
    return bool(_BARE_SCAN.match(" ".join((text or "").split())))


async def _identify(data: bytes) -> str:
    """What's in the photo: a product from its barcode, else a short description from the vision model."""
    from server.services.shopping.barcode import BarcodeError, decode_image_async, lookup

    code = ""
    try:
        code = await decode_image_async(data)
        product = await lookup(code)
        name = product.name or product.title or ""
        if name:
            return (f"That's **{name}** (barcode {code}). Want me to compare prices at stores?"
                    + _suggest([("Compare prices", f"Compare store prices for {name} (barcode {code})")]))
    except BarcodeError:
        pass
    except Exception as e:
        logger.info("Barcode lookup failed: %s", e)
    seen = await _ask_vision(data, (
        "Say in one or two short sentences what this photo shows. If there's a product, give its brand and name. "
        "Then read out any important text, prices or numbers exactly as printed. Don't guess at anything unreadable."),
        max_tokens=160)
    if seen:
        lead = f"Barcode {code} isn't in the product database. " if code else ""
        return lead + seen
    text = await asyncio.to_thread(_ocr_text, data)
    if text.strip():
        return "I can't recognise the item, but it says: " + " ".join(text.split())[:400]
    return "I couldn't make out anything in that photo. Hold it closer and steady, and try again."


def _suggest(choices: list[tuple[str, str]]) -> str:
    import json
    return "\n<!--luna-suggest:" + json.dumps([{"label": l, "message": m} for l, m in choices]) + "-->"


# ── Forms ────────────────────────────────────────────────────────────────────

async def _fill(db, conversation_id, data: bytes, link: Optional[str]) -> ScanOutcome:
    from server.services import browser_open as B
    from server.services import form_filler as F

    title_hint = ""
    lines = []
    if link:
        request = B.request_for(link)
        opened = await asyncio.to_thread(B.open_website, request)
        if opened.get("error"):
            return ScanOutcome(reply=f"The QR code links to {link}, but I couldn't open it: {opened['error']}")
        evidence = opened.get("evidence")
        if evidence is not None and evidence.verified:
            title_hint = evidence.window["title"].replace(" - Google Chrome", "")[:60]
        lines.append(f"Opened the form from the QR code ({link}).")
        await asyncio.sleep(2.5)   # let the form render before reading its fields
        details = await F.my_details(db, browser_email=_profile_email(opened))
        source = "your details"
    else:
        text = await asyncio.to_thread(_ocr_text, data)
        if not text.strip():
            return ScanOutcome(reply="I couldn't read any text on that page, and there's no QR code. "
                                     "Hold it closer and steady, and try again.")
        details = await F.details_from_scan(text)
        if not details:
            return ScanOutcome(reply="I read the page but couldn't find details like a name, email or address to put in a form.")
        source = "the scanned page"
    if not details:
        return ScanOutcome(reply="\n".join(lines + [
            "I don't know enough about you to fill it — tell me your name, email and phone once and I'll remember them."]))
    try:
        result = await asyncio.to_thread(F.fill_form, details, title_hint=title_hint)
    except F.FormError as e:
        return ScanOutcome(reply="\n".join(lines + [e.message]))
    if result.filled and conversation_id:
        _FILLED[conversation_id] = (title_hint or result.title, time.monotonic())
    lines.append(f"Using {source}.")
    lines.append(F.describe(result))
    return ScanOutcome(reply="\n".join(lines))


def _profile_email(opened: dict) -> str:
    key = opened.get("profile_key") or ""
    return key if "@" in key else ""


def _ocr_text(data: bytes) -> str:
    try:
        from PIL import Image, ImageOps

        from server.services.files.ocr import ocr_image
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        return ocr_image(image).text
    except Exception as e:
        logger.info("OCR of scan failed: %s", e)
        return ""


def wants_submit(conversation_id: Optional[int], text: str) -> Optional[str]:
    """The form title to submit when the user says "submit it" soon after a fill in this conversation."""
    entry = _FILLED.get(conversation_id or 0)
    if not entry or time.monotonic() - entry[1] > SUBMIT_WINDOW_S:
        return None
    if not SUBMIT_RE.match(" ".join((text or "").split())):
        return None
    _FILLED.pop(conversation_id, None)
    return entry[0]


# ── Prices ───────────────────────────────────────────────────────────────────

async def _prices(data: bytes) -> ScanOutcome:
    from server.services.shopping.barcode import BarcodeError, decode_image_async, lookup

    try:
        code = await decode_image_async(data)
        product = await lookup(code)
        name = product.name or product.title or ""
        if name:
            return ScanOutcome(rewrite=f"Compare store prices for {name} (barcode {code})")
    except BarcodeError:
        pass
    except Exception as e:
        logger.info("Barcode lookup failed: %s", e)
    name = await _name_product(data)
    if not name:
        return ScanOutcome(reply="I couldn't find a barcode or tell what the product is. "
                                 "Point the camera at the barcode, close and steady, and try again.")
    return ScanOutcome(rewrite=f"Compare store prices for {name}")


async def _name_product(data: bytes) -> str:
    answer = (await _ask_vision(data, (
        "What product is this? Reply with only the brand, product name and size as printed on the "
        "pack, e.g. 'Coca-Cola Zero Sugar 12 fl oz can'. If it isn't a product, reply 'none'."), max_tokens=40)).strip('".')
    return "" if not answer or answer.lower().startswith("none") else answer[:120]


async def _ask_vision(data: bytes, prompt: str, max_tokens: int) -> str:
    """One question about the photo to the local vision model; "" when there isn't one or it fails."""
    import httpx

    from server.config import settings
    from server.services.files.service import _prepare_image, pick_vision_model

    model = await pick_vision_model()
    if not model:
        return ""
    _img, png = _prepare_image(data)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            r = await client.post(f"{settings.ollama_base_url}/api/generate", json={
                "model": model, "images": [base64.b64encode(png).decode("ascii")], "stream": False, "keep_alive": "2m",
                "prompt": prompt, "options": {"num_predict": max_tokens, "temperature": 0.0}})
            r.raise_for_status()
            return r.json().get("response", "").strip()
    except Exception as e:
        logger.info("Vision request failed: %s", e)
        return ""


# ── Links ────────────────────────────────────────────────────────────────────

async def _open_link(link: str) -> str:
    from server.services import browser_open as B
    request = B.request_for(link)
    result = await asyncio.to_thread(B.open_website, request)
    if result.get("error"):
        return f"The QR code links to {link}. I couldn't open it: {result['error']}"
    return f"The QR code links to {link}. " + B.describe(result)
