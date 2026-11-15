"""Chunk + embed + search for attachments too large to send in full.

Mirrors hosted "file search": the document is split into overlapping chunks
that keep their page/sheet label, embedded once (cached on disk next to the
file), and each question pulls the most relevant chunks. If the embedding
model is unavailable, a keyword ranker keeps retrieval working.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

from backend.config import settings
from backend.services.files.extract import ExtractedFile

logger = logging.getLogger(__name__)

CHUNK_CHARS = 1400
CHUNK_OVERLAP = 200
EMBED_BATCH = 32
_WORD_RE = re.compile(r"[a-z0-9]{2,}")


@dataclass
class Chunk:
    index: int
    label: str
    text: str


def chunk_text(text: str, label: str = "", start_index: int = 0) -> list[Chunk]:
    """Overlapping ~CHUNK_CHARS chunks, cut at paragraph/sentence boundaries."""
    chunks: list[Chunk] = []
    text = text.strip()
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            # Prefer to break at a paragraph or sentence boundary.
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if cut > CHUNK_CHARS * 0.5:
                end = start + cut + 1
        chunks.append(Chunk(start_index + len(chunks), label, text[start:end].strip()))
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def chunk_document(doc: ExtractedFile) -> list[Chunk]:
    chunks: list[Chunk] = []
    if doc.overview:
        chunks.append(Chunk(0, "overview", doc.overview))
    for section in doc.sections:
        if section.text.strip():
            chunks.extend(chunk_text(section.text, section.label, start_index=len(chunks)))
    return chunks


async def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            r = await client.post(
                f"{settings.ollama_embed_base_url or settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embed_model, "input": texts},
            )
            r.raise_for_status()
            vectors = r.json().get("embeddings") or []
            return vectors if len(vectors) == len(texts) else None
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Attachment embedding failed (%s); using keyword search", e)
        return None


async def build_index(doc: ExtractedFile, folder: Path) -> list[Chunk]:
    """Chunk and embed the document once; cached in <folder>/chunks.json + vectors.npy."""
    chunks_path, vectors_path = folder / "chunks.json", folder / "vectors.npy"
    if chunks_path.exists():
        return [Chunk(**c) for c in json.loads(chunks_path.read_text(encoding="utf-8"))]

    chunks = chunk_document(doc)
    chunks_path.write_text(json.dumps([c.__dict__ for c in chunks], ensure_ascii=False), encoding="utf-8")
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = [f"search_document: {c.label} {c.text}" for c in chunks[start:start + EMBED_BATCH]]
        embedded = await _embed_batch(batch)
        if embedded is None:
            return chunks  # keyword fallback; retry embedding next time
        vectors.extend(embedded)
    if vectors:
        np.save(vectors_path, np.asarray(vectors, dtype=np.float32))
    return chunks


def _keyword_scores(query: str, chunks: list[Chunk]) -> list[float]:
    q_terms = Counter(_WORD_RE.findall(query.lower()))
    if not q_terms:
        return [0.0] * len(chunks)
    docs = [Counter(_WORD_RE.findall(f"{c.label} {c.text}".lower())) for c in chunks]
    n = len(docs)
    scores = []
    for d in docs:
        length = sum(d.values()) or 1
        score = 0.0
        for term in q_terms:
            if term in d:
                df = sum(1 for other in docs if term in other)
                score += (d[term] / length) * math.log(1 + n / df)
        scores.append(score)
    return scores


async def search(query: str, doc: ExtractedFile, folder: Path, top_k: int = 8) -> list[Chunk]:
    """Most relevant chunks for `query`, returned in document order."""
    chunks = await build_index(doc, folder)
    if not chunks:
        return []
    scores: list[float] | None = None
    vectors_path = folder / "vectors.npy"
    if vectors_path.exists():
        embedded = await _embed_batch([f"search_query: {query}"])
        if embedded:
            matrix = np.load(vectors_path)
            q = np.asarray(embedded[0], dtype=np.float32)
            denom = (np.linalg.norm(matrix, axis=1) * (np.linalg.norm(q) or 1.0)) + 1e-9
            semantic = (matrix @ q) / denom
            keyword = np.asarray(_keyword_scores(query, chunks), dtype=np.float32)
            if keyword.max() > 0:
                keyword = keyword / keyword.max()
            scores = list(0.8 * semantic + 0.2 * keyword)   # hybrid: exact terms still count
    if scores is None:
        scores = _keyword_scores(query, chunks)
    ranked = sorted(range(len(chunks)), key=lambda i: -scores[i])[:top_k]
    return [chunks[i] for i in sorted(ranked)]


async def rank_chunks(query: str, chunks: list[Chunk]) -> list[float]:
    """Hybrid relevance (embeddings + keywords) for chunks held in memory."""
    keyword = np.asarray(_keyword_scores(query, chunks), dtype=np.float32)
    if keyword.max() > 0:
        keyword = keyword / keyword.max()
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        embedded = await _embed_batch([f"search_document: {c.text}" for c in chunks[start:start + EMBED_BATCH]])
        if embedded is None:
            return list(keyword)
        vectors.extend(embedded)
    q = await _embed_batch([f"search_query: {query}"])
    if not q:
        return list(keyword)
    matrix, qv = np.asarray(vectors, dtype=np.float32), np.asarray(q[0], dtype=np.float32)
    semantic = (matrix @ qv) / ((np.linalg.norm(matrix, axis=1) * (np.linalg.norm(qv) or 1.0)) + 1e-9)
    return list(0.6 * semantic + 0.4 * keyword)          # exact terms (names, IDs) matter in pastes


async def condense_long_text(text: str, max_chars: int, keep_edge_chars: int = 1500) -> tuple[str, int, int]:
    """Fit a long pasted message into max_chars without losing its point.

    The start and end stay verbatim (instructions and the question usually sit
    there); the middle is chunked and only the chunks most relevant to the
    start+end are kept, in their original order, marked as excerpts. Returns
    (text, chunks_kept, chunks_total).
    """
    if len(text) <= max_chars:
        return text, 0, 0
    edge = min(keep_edge_chars, max_chars // 4)
    head, middle, tail = text[:edge], text[edge:len(text) - edge], text[len(text) - edge:]
    chunks = chunk_text(middle, "excerpt")
    scores = await rank_chunks(f"{head[-600:]} {tail}", chunks)
    room = max_chars - len(head) - len(tail) - 400
    picked: list[int] = []
    for i in sorted(range(len(chunks)), key=lambda i: -scores[i]):
        if sum(len(chunks[j].text) + 40 for j in picked) + len(chunks[i].text) + 40 > room:
            continue
        picked.append(i)
    parts = [head, f"\n\n[This message was too long to read in full: {len(picked)} of {len(chunks)} middle parts, "
                   "the ones most relevant to the question, are shown in order; the rest were left out.]"]
    last = -1
    for i in sorted(picked):
        parts.append(("\n[…]\n" if i != last + 1 else "\n") + chunks[i].text)
        last = i
    parts.append(("\n[…]\n" if last != len(chunks) - 1 else "\n") + tail)
    return "".join(parts), len(picked), len(chunks)
