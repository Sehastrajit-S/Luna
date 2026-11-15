"""Attachment storage, extraction, and per-turn document context.

Layout: data/uploads/<id>/
    original<ext>     the uploaded bytes
    extracted.json    ExtractedFile (sections with page/sheet/slide labels)
    chunks.json       retrieval chunks          (large files, lazily)
    vectors.npy       chunk embeddings          (large files, lazily)
    summary.txt       map-reduce summary        (large files, on demand)

How a turn sees its files (the same shape hosted assistants use):
  * files that fit the document budget are sent in full;
  * larger files send their overview plus the chunks most relevant to the
    question, cited by page/sheet/slide;
  * "summarize this" on a large file uses a cached map-reduce summary.
Every file attached anywhere in the conversation stays available, so a
follow-up many turns later can still ask about it.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
import uuid
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from backend.config import DATA_DIR, settings
from backend.models.database import Attachment
from backend.services.files.extract import (
    IMAGE_EXT, MAX_UPLOAD_BYTES, ExtractedFile, Section, UnsupportedFile, check_supported, extract_file,
)
from backend.services.files import retrieval
from backend.services.llm.context_window import estimate_tokens

logger = logging.getLogger(__name__)

UPLOAD_ROOT = DATA_DIR / "uploads"
_ID_RE = re.compile(r"^[0-9a-f]{32}$")
IMAGE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
              ".gif": "image/gif", ".bmp": "image/bmp"}

_SUMMARY_INTENT_RE = re.compile(
    r"\b(summari[sz]e|summary|overview|tl;?dr|key (?:points|takeaways|findings)|main points|gist|"
    r"what(?:'s| is)\s+(?:this|the)\s+(?:file|doc(?:ument)?|pdf|paper|report|deck|sheet|spreadsheet)\s+about|"
    r"go through|walk me through|read (?:this|it|the whole))\b",
    re.IGNORECASE,
)
_summary_locks: dict[str, asyncio.Lock] = {}


def folder_for(attachment_id: str) -> Path:
    if not _ID_RE.match(attachment_id or ""):
        raise ValueError("invalid attachment id")
    return UPLOAD_ROOT / attachment_id


def original_path(attachment: Attachment) -> Path:
    folder = folder_for(attachment.id)
    return next(folder.glob("original*"), folder / "original")


def load_extracted(attachment_id: str) -> ExtractedFile | None:
    path = folder_for(attachment_id) / "extracted.json"
    if not path.exists():
        return None
    return ExtractedFile.from_json(json.loads(path.read_text(encoding="utf-8")))


# ── Images: described by the local vision model ──────────────────────────────

VISION_FALLBACKS = ("qwen2.5vl", "llama3.2-vision", "gemma3", "minicpm-v", "llava", "moondream")
VISION_MAX_SIDE = 1600       # larger images cost thousands of image tokens for little gain
VISION_PROMPT = (
    "Describe this image thoroughly for someone who can't see it. Say what kind of image it is "
    "(photo, screenshot, chart, diagram, document, UI, etc.) and what it shows. "
    "For charts and graphs, give the title, axes, series and the key values or trends. "
    "For tables, reproduce the rows and columns. For screenshots, describe the app, what's on screen and any "
    "errors or messages. For documents, summarize the content. Be specific and factual; don't guess at text "
    "you can't read."
)


async def _installed_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            r.raise_for_status()
            return [m.get("name", "") for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []


async def pick_vision_model() -> str | None:
    """Configured vision model if pulled, else the best installed fallback."""
    installed = await _installed_models()
    names = {n.split(":")[0]: n for n in installed}
    wanted = settings.vision_model.strip()
    if wanted in installed or f"{wanted}:latest" in installed:
        return wanted
    for family in (wanted.split(":")[0], *VISION_FALLBACKS):
        if family in names:
            return names[family]
    return None


def _prepare_image(data: bytes):
    """Decode, flatten transparency, and downscale. Returns (PIL image, PNG bytes) or (None, data)."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None, data
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if getattr(img, "is_animated", False):
        img.seek(0)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((VISION_MAX_SIDE, VISION_MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return img, buf.getvalue()


async def _vision_describe(model: str, png: bytes) -> str:
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0)) as client:
        r = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": model, "prompt": VISION_PROMPT, "images": [base64.b64encode(png).decode("ascii")],
                "stream": False, "keep_alive": "2m",   # free the GPU for the chat model soon after
                "options": {"num_predict": 700, "temperature": 0.1, "num_ctx": 8192},
            },
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()


async def _describe_image(data: bytes, ext: str) -> ExtractedFile:
    """Image → exact text via OCR + a description from the vision model."""
    from backend.services.files.ocr import OcrUnavailable, ocr_image

    out = ExtractedFile(kind="image", mime_type=IMAGE_MIME.get(ext, "image/png"), page_count=1)
    try:
        img, png = await asyncio.to_thread(_prepare_image, data)
    except Exception as e:
        raise UnsupportedFile(f"This image couldn't be opened ({e}).") from e
    if img is not None:
        out.overview = f"Image, {img.width}×{img.height}px"

    # OCR gives exact characters (numbers, code, error messages) that vision
    # models tend to paraphrase; the vision model explains everything else.
    try:
        ocr = await asyncio.to_thread(ocr_image, img if img is not None else data)
        if ocr.text:
            out.sections.append(Section("Text in the image (OCR)", ocr.text))
    except OcrUnavailable as e:
        out.warnings.append(f"Text in the image couldn't be read exactly: {e}.")
    except Exception as e:
        logger.warning("Image OCR failed: %s", e)

    model = await pick_vision_model()
    if model is None:
        out.warnings.append("No vision model is installed, so only the text in the image could be read. "
                            f"Run `ollama pull {settings.vision_model}` for full image understanding.")
    else:
        try:
            description = await _vision_describe(model, png)
            if description:
                out.sections.insert(0, Section("Description", description))
            if model.split(":")[0] == "moondream":
                out.warnings.append(f"Described with moondream (basic). Run `ollama pull {settings.vision_model}` "
                                    "for much better image understanding.")
        except httpx.HTTPError as e:
            logger.warning("Vision model %s failed: %s", model, e)
            out.warnings.append(f"The vision model ({model}) failed, so only the text in the image was read.")
    out.summary_line = "Image" + (f" · {img.width}×{img.height}" if img is not None else "")
    return out


# ── Upload ───────────────────────────────────────────────────────────────────

async def save_upload(db: Session, filename: str, data: bytes, conversation_id: int | None = None) -> Attachment:
    """Store and extract an upload. Raises UnsupportedFile with a user-facing reason."""
    filename = Path(filename or "file").name[:200] or "file"
    ext = check_supported(filename)
    if not data:
        raise UnsupportedFile("This file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnsupportedFile(f"Files can be up to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    if ext in IMAGE_EXT:
        doc = await _describe_image(data, ext)
    else:
        doc = await asyncio.to_thread(extract_file, data, filename)

    attachment_id = uuid.uuid4().hex
    folder = folder_for(attachment_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"original{ext}").write_bytes(data)
    (folder / "extracted.json").write_text(json.dumps(doc.to_json(), ensure_ascii=False), encoding="utf-8")

    has_text = any(s.text.strip() for s in doc.sections) or bool(doc.overview)
    attachment = Attachment(
        id=attachment_id,
        conversation_id=conversation_id,
        filename=filename,
        mime_type=doc.mime_type,
        kind=doc.kind,
        size_bytes=len(data),
        status="ready" if has_text else "error",
        error=" ".join(doc.warnings) or None,
        page_count=doc.page_count,
        token_estimate=estimate_tokens(doc.full_text),
        summary_line=doc.summary_line,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    logger.info("Attachment %s saved: %s (%s, ~%d tokens)", attachment_id, filename, doc.summary_line,
                attachment.token_estimate or 0)
    return attachment


async def prepare_large_file(attachment_id: str) -> None:
    """Background: build the retrieval index right after upload so the first question is fast."""
    try:
        doc = load_extracted(attachment_id)
        if doc and estimate_tokens(doc.full_text) > per_file_budget():
            await retrieval.build_index(doc, folder_for(attachment_id))
    except Exception as e:  # never let background prep surface as an error
        logger.warning("Preparing attachment %s failed: %s", attachment_id, e)


def link_to_message(db: Session, attachment_ids: list[str], conversation_id: int, message_id: int) -> list[Attachment]:
    ids = [a for a in dict.fromkeys(attachment_ids or []) if _ID_RE.match(a or "")]
    if not ids:
        return []
    rows = db.query(Attachment).filter(Attachment.id.in_(ids)).all()
    linked = []
    for row in rows:
        # Only unclaimed uploads or ones already in this conversation can be attached.
        if row.message_id is None and row.conversation_id in (None, conversation_id):
            row.conversation_id = conversation_id
            row.message_id = message_id
            linked.append(row)
    db.commit()
    return linked


def sweep_unsent_uploads(db: Session, max_age_hours: int = 24) -> int:
    """Remove uploads never attached to a message (e.g. the app closed with a
    file still in the composer). Files in sent messages go when their chat is deleted."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    stale = [
        a for a in db.query(Attachment).filter(Attachment.message_id.is_(None)).all()
        if a.created_at and (a.created_at if a.created_at.tzinfo else a.created_at.replace(tzinfo=timezone.utc)) < cutoff
    ]
    for a in stale:
        db.delete(a)
    db.commit()
    for a in stale:
        try:
            delete_attachment_files(a.id)
        except OSError as e:
            logger.warning("Could not remove files for unsent attachment %s: %s", a.id, e)
    if stale:
        logger.info("Removed %d unsent upload(s) older than %dh", len(stale), max_age_hours)
    return len(stale)


def delete_attachment_files(attachment_id: str) -> None:
    folder = folder_for(attachment_id)
    if folder.exists():
        for path in folder.iterdir():
            path.unlink(missing_ok=True)
        folder.rmdir()


# ── Per-turn document context ────────────────────────────────────────────────

def document_budget() -> int:
    """Tokens of attachment content per turn (the rest of the window is prompt + history)."""
    return max(2000, int(settings.llm_context_window * 0.4))


def per_file_budget() -> int:
    return int(document_budget() * 0.85)


def wants_summary(question: str) -> bool:
    return bool(_SUMMARY_INTENT_RE.search(question or ""))


async def summarize_document(attachment: Attachment, doc: ExtractedFile) -> str:
    """Map-reduce summary for files too large to read in one pass; cached."""
    folder = folder_for(attachment.id)
    cache = folder / "summary.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    lock = _summary_locks.setdefault(attachment.id, asyncio.Lock())
    async with lock:
        if cache.exists():
            return cache.read_text(encoding="utf-8")
        from backend.services.llm import ollama

        group_chars = int((settings.llm_context_window - settings.llm_max_output_tokens - 1500) * 3.5)
        groups, current = [], ""
        for section in doc.sections:
            piece = f"[{section.label}]\n{section.text}\n\n" if section.label else f"{section.text}\n\n"
            if current and len(current) + len(piece) > group_chars:
                groups.append(current)
                current = ""
            current += piece[:group_chars]
        if current:
            groups.append(current)

        partials = []
        for i, group in enumerate(groups, start=1):
            partials.append(await ollama.complete(
                prompt=f"Part {i} of {len(groups)} of “{attachment.filename}”:\n\n{group}",
                system=("Summarize this part of a document in 5-10 bullet points. Keep names, numbers, dates and "
                        "conclusions, and cite page/slide/sheet labels in brackets like [p. 4]. No preamble."),
                temperature=0.2,
            ))
        if len(partials) == 1:
            summary = partials[0].strip()
        else:
            summary = (await ollama.complete(
                prompt="\n\n".join(f"Part {i}:\n{p}" for i, p in enumerate(partials, start=1)),
                system=("Combine these partial summaries of one document into a single structured summary: "
                        "a 2-3 sentence overview, then the key points as bullets. Keep the [p. N] citations. "
                        "No preamble."),
                temperature=0.2,
            )).strip()
        cache.write_text(summary, encoding="utf-8")
        return summary


def _render_chunks(chunks: list[retrieval.Chunk], budget: int) -> str:
    out, used = [], 0
    for c in chunks:
        block = f"[{c.label}]\n{c.text}" if c.label else c.text
        cost = estimate_tokens(block)
        if used + cost > budget:
            break
        out.append(block)
        used += cost
    return "\n\n".join(out)


async def build_attachment_context(db: Session, conversation_id: int, question: str,
                                   current_ids: list[str] | None = None) -> str:
    """The <documents> block for this turn, or "" when the conversation has no files."""
    rows = (
        db.query(Attachment)
        .filter(Attachment.conversation_id == conversation_id, Attachment.status == "ready")
        .order_by(Attachment.created_at.asc())
        .all()
    )
    if not rows:
        return ""
    current = set(current_ids or [])
    # Files attached to this message come first; then the most recent earlier ones.
    rows.sort(key=lambda a: (a.id not in current, -(a.created_at.timestamp() if a.created_at else 0)))
    rows = rows[:8]

    budget = document_budget()
    share = max(800, budget // len(rows))
    blocks = []
    for index, att in enumerate(rows, start=1):
        doc = load_extracted(att.id)
        if doc is None:
            continue
        full = doc.full_text
        file_budget = share if len(rows) > 1 else per_file_budget()
        coverage = "full"
        if estimate_tokens(full) <= file_budget:
            content = full
        elif wants_summary(question) and doc.kind not in {"csv", "spreadsheet"}:
            coverage = "summary of the whole file"
            content = await summarize_document(att, doc)
        else:
            coverage = "excerpts relevant to the question"
            chunks = await retrieval.search(question, doc, folder_for(att.id), top_k=12)
            head = doc.overview if doc.overview else ""
            remaining = file_budget - estimate_tokens(head)
            content = "\n\n".join(p for p in (head, _render_chunks(chunks, remaining)) if p)
        notes = f"\nNote: {' '.join(doc.warnings)}" if doc.warnings else ""
        blocks.append(
            f'<document index="{index}" name="{att.filename}" type="{att.summary_line or att.kind}" '
            f'coverage="{coverage}">\n{content}{notes}\n</document>'
        )
    if not blocks:
        return ""
    return (
        "<documents>\n" + "\n".join(blocks) + "\n</documents>\n"
        "The attached documents above are already read — answer directly and completely; never reply that you "
        "will read or review them first. Cite where facts come from with the file name and the "
        "label in brackets, e.g. (report.pdf, p. 4) or (sales.xlsx, Sheet1). If coverage is only excerpts and "
        "the answer isn't in them, say what you'd need rather than guessing.\n\n"
    )
