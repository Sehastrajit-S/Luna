"""Local OCR for scanned PDFs and text in images.

RapidOCR (PaddleOCR models on ONNX Runtime) runs on the CPU with no system
install; pypdfium2 renders PDF pages to images. Both are optional imports:
when missing, callers get OcrUnavailable and fall back to a clear warning.
"""
from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

RENDER_DPI = 200
MIN_CONFIDENCE = 0.5

_engine = None
_engine_lock = threading.Lock()


class OcrUnavailable(RuntimeError):
    pass


@dataclass
class OcrResult:
    text: str
    confidence: float   # mean confidence of kept lines, 0..1
    lines: int


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError as e:
                raise OcrUnavailable("OCR isn't installed (pip install rapidocr-onnxruntime)") from e
            _engine = RapidOCR()
        return _engine


def _to_text(result) -> OcrResult:
    """Order detected boxes into lines: top-to-bottom, then left-to-right."""
    items = []
    for box, text, score in result or []:
        if not text or float(score) < MIN_CONFIDENCE:
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((sum(ys) / 4, min(xs), max(ys) - min(ys), text.strip(), float(score)))
    if not items:
        return OcrResult("", 0.0, 0)
    items.sort(key=lambda it: (it[0], it[1]))
    lines: list[list[tuple]] = []
    for item in items:
        if lines:
            last = lines[-1]
            center = sum(i[0] for i in last) / len(last)
            height = max(i[2] for i in last) or 1
            if abs(item[0] - center) < height * 0.6:
                last.append(item)
                continue
        lines.append([item])
    text = "\n".join(" ".join(i[3] for i in sorted(line, key=lambda i: i[1])) for line in lines)
    confidence = sum(i[4] for i in items) / len(items)
    return OcrResult(text, confidence, len(lines))


def ocr_image(image) -> OcrResult:
    """OCR a PIL image, numpy array, or encoded image bytes."""
    engine = _get_engine()
    if hasattr(image, "convert"):   # PIL
        import numpy as np
        image = np.asarray(image.convert("RGB"))
    result, _ = engine(image)
    return _to_text(result)


@dataclass
class OcrBox:
    text: str
    left: float
    top: float
    right: float
    bottom: float
    score: float


def ocr_boxes(image) -> list[OcrBox]:
    """Each piece of text found, with where it is (pixels). For checking a region of a window."""
    engine = _get_engine()
    if hasattr(image, "convert"):
        import numpy as np
        image = np.asarray(image.convert("RGB"))
    result, _ = engine(image)
    boxes = []
    for box, text, score in result or []:
        if text and float(score) >= MIN_CONFIDENCE:
            xs, ys = [p[0] for p in box], [p[1] for p in box]
            boxes.append(OcrBox(text.strip(), min(xs), min(ys), max(xs), max(ys), float(score)))
    return boxes


def render_pdf_page(data: bytes, page_index: int, dpi: int = RENDER_DPI):
    """Render one PDF page to a PIL image."""
    try:
        import pypdfium2 as pdfium
    except ImportError as e:
        raise OcrUnavailable("PDF rendering isn't installed (pip install pypdfium2)") from e
    pdf = pdfium.PdfDocument(io.BytesIO(data))
    try:
        page = pdf[page_index]
        try:
            return page.render(scale=dpi / 72).to_pil()
        finally:
            page.close()
    finally:
        pdf.close()


def ocr_pdf_pages(data: bytes, page_indexes: list[int]) -> dict[int, OcrResult]:
    """OCR the given 0-based pages of a PDF. Pages that fail are skipped."""
    results: dict[int, OcrResult] = {}
    for index in page_indexes:
        try:
            results[index] = ocr_image(render_pdf_page(data, index))
        except OcrUnavailable:
            raise
        except Exception as e:  # one bad page must not sink the document
            logger.warning("OCR of PDF page %d failed: %s", index + 1, e)
    return results
