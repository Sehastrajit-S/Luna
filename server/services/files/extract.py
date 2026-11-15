"""Turn an uploaded file into labelled text sections the model can read.

Each extractor returns sections labelled the way people cite them — "p. 3"
for PDFs, "Sheet1" for workbooks, "slide 4" for decks — so answers can point
back to where something came from. Images are handled asynchronously in
services/files/service.py (they need the vision model).
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from charset_normalizer import from_bytes

MAX_UPLOAD_BYTES = 30 * 1024 * 1024       # same per-file ceiling Claude uses
MAX_EXTRACTED_CHARS = 2_000_000           # ~500K tokens; beyond this we truncate
MAX_TABLE_ROWS = 200_000

PDF_EXT = {".pdf"}
DOCX_EXT = {".docx"}
PPTX_EXT = {".pptx"}
XLSX_EXT = {".xlsx", ".xlsm"}
CSV_EXT = {".csv", ".tsv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
HTML_EXT = {".html", ".htm"}
TEXT_EXT = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".env.example", ".sql", ".tex", ".bib", ".srt", ".vtt", ".rtf",
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".kt", ".kts", ".c", ".h", ".cpp",
    ".hpp", ".cc", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".m", ".scala", ".r", ".lua", ".pl",
    ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".css", ".scss", ".less", ".vue", ".svelte",
    ".dart", ".ipynb", ".graphql", ".proto", ".dockerfile", ".gradle", ".makefile",
}
LEGACY_OFFICE = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}

SUPPORTED_EXT = PDF_EXT | DOCX_EXT | PPTX_EXT | XLSX_EXT | CSV_EXT | IMAGE_EXT | HTML_EXT | TEXT_EXT


class UnsupportedFile(ValueError):
    """The file type can't be read; the message is shown to the user."""


@dataclass
class Section:
    label: str       # "p. 3", "slide 2", "Sheet1", "" for plain text
    text: str


@dataclass
class ExtractedFile:
    kind: str                       # pdf | docx | pptx | spreadsheet | csv | text | image
    mime_type: str
    sections: list[Section] = field(default_factory=list)
    page_count: int | None = None
    overview: str = ""              # data profile / outline shown before content
    summary_line: str = ""          # short chip text: "PDF · 12 pages"
    warnings: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        parts = [self.overview] if self.overview else []
        for s in self.sections:
            if s.text.strip():
                parts.append(f"[{s.label}]\n{s.text.strip()}" if s.label else s.text.strip())
        return "\n\n".join(parts)

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "ExtractedFile":
        data = dict(data)
        data["sections"] = [Section(**s) for s in data.get("sections", [])]
        return cls(**data)


def extension_of(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".env.example"):
        return ".env.example"
    if name in {"dockerfile", "makefile"}:
        return f".{name}"
    return Path(name).suffix


def check_supported(filename: str) -> str:
    ext = extension_of(filename)
    if ext in LEGACY_OFFICE:
        raise UnsupportedFile(f"Old {ext} files aren't supported — save it as {LEGACY_OFFICE[ext]} and attach that.")
    if ext not in SUPPORTED_EXT:
        raise UnsupportedFile(f"Luna can't read {ext or 'files without an extension'} files yet.")
    return ext


def _decode(data: bytes) -> str:
    if not data:
        return ""
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if data.startswith(bom):
            return data.decode(enc, errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        best = from_bytes(data).best()
        return str(best) if best else data.decode("latin-1", errors="replace")


def _cap(text: str, warnings: list[str]) -> str:
    if len(text) > MAX_EXTRACTED_CHARS:
        warnings.append("The file is very long; only the first part was read.")
        return text[:MAX_EXTRACTED_CHARS]
    return text


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


# ── PDF ──────────────────────────────────────────────────────────────────────

def _extract_pdf(data: bytes) -> ExtractedFile:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, ValueError, OSError) as e:
        raise UnsupportedFile(f"This PDF looks damaged and couldn't be opened ({e}).") from e
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise UnsupportedFile("This PDF is password-protected. Remove the password and attach it again.")
        except Exception as e:
            raise UnsupportedFile("This PDF is password-protected. Remove the password and attach it again.") from e

    out = ExtractedFile(kind="pdf", mime_type="application/pdf", page_count=len(reader.pages))
    total = 0
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
            out.warnings.append(f"Page {i} couldn't be read.")
        text = re.sub(r"[ \t]+\n", "\n", text).strip()
        total += len(text)
        if total > MAX_EXTRACTED_CHARS:
            out.warnings.append(f"Only the first {i - 1} pages were read (document too long).")
            break
        out.sections.append(Section(f"p. {i}", text))

    _ocr_scanned_pages(data, out)
    out.summary_line = f"PDF · {_plural(out.page_count or 0, 'page')}"
    return out


OCR_MAX_PAGES = 100   # ~2-3 s/page on CPU; beyond this the upload would take minutes
_MIN_TEXT_LAYER_CHARS = 20


def _page_ranges(numbers: list[int]) -> str:
    ranges, start, prev = [], None, None
    for n in numbers + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            ranges.append(f"{start}" if start == prev else f"{start}–{prev}")
            start = prev = n
    return ", ".join(ranges)


def _ocr_scanned_pages(data: bytes, out: ExtractedFile) -> None:
    """Read pages that have no text layer (scans, photos of pages) with OCR."""
    from backend.services.files.ocr import OcrUnavailable, ocr_pdf_pages

    scanned = [i for i, s in enumerate(out.sections) if len(s.text) < _MIN_TEXT_LAYER_CHARS]
    if not scanned:
        return
    todo, skipped = scanned[:OCR_MAX_PAGES], scanned[OCR_MAX_PAGES:]
    try:
        results = ocr_pdf_pages(data, todo)
    except OcrUnavailable as e:
        out.warnings.append(f"{len(scanned)} page(s) look scanned and couldn't be read: {e}.")
        return

    read, unreadable, confidences = [], [], []
    for index in todo:
        result = results.get(index)
        if result and len(result.text) >= _MIN_TEXT_LAYER_CHARS:
            out.sections[index].text = result.text
            read.append(index + 1)
            confidences.append(result.confidence)
        elif result is None or not out.sections[index].text:
            unreadable.append(index + 1)

    if read:
        note = f"Page{'s' if len(read) > 1 else ''} {_page_ranges(read)} {'were' if len(read) > 1 else 'was'} scanned and read with OCR"
        avg = sum(confidences) / len(confidences)
        if avg < 0.8:
            note += " (low confidence — the scan may be blurry; double-check exact figures)"
        out.warnings.append(note + ".")
    if unreadable and len(unreadable) == len(out.sections):
        out.warnings.append("No text could be found on any page, even with OCR (blank or image-only pages).")
    elif unreadable:
        out.warnings.append(f"No text found on page(s) {_page_ranges(unreadable)} (blank or images only).")
    if skipped:
        out.warnings.append(f"Only the first {OCR_MAX_PAGES} scanned pages were read with OCR; "
                            f"page(s) {_page_ranges([i + 1 for i in skipped])} were skipped.")


# ── Word ─────────────────────────────────────────────────────────────────────

def _docx_table(table) -> str:
    rows = []
    for row in table.rows:
        cells = [" ".join(c.text.split()) for c in row.cells]
        rows.append("| " + " | ".join(cells) + " |")
    if len(rows) > 1:
        rows.insert(1, "|" + "---|" * len(table.rows[0].cells))
    return "\n".join(rows)


def _extract_docx(data: bytes) -> ExtractedFile:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as e:
        raise UnsupportedFile(f"This Word document couldn't be opened ({e}).") from e

    out = ExtractedFile(kind="docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    label, lines, headings = "", [], []
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, document)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name or "").lower() if para.style is not None else ""
            level = re.match(r"heading (\d)", style)
            if style == "title" or (level and int(level.group(1)) <= 2):
                if lines:
                    out.sections.append(Section(label, "\n".join(lines)))
                label, lines = text[:80], []
                headings.append(text)
                lines.append(f"{'#' * (int(level.group(1)) if level else 1)} {text}")
            elif level:
                lines.append(f"{'#' * int(level.group(1))} {text}")
            elif "list" in style:
                lines.append(f"- {text}")
            else:
                lines.append(text)
        elif tag == "tbl":
            lines.append(_docx_table(Table(child, document)))
    if lines:
        out.sections.append(Section(label, "\n".join(lines)))

    words = sum(len(s.text.split()) for s in out.sections)
    out.page_count = max(1, round(words / 500)) if words else 0
    if headings:
        out.overview = "Outline: " + " · ".join(h[:60] for h in headings[:25])
    if not words:
        out.warnings.append("This document has no readable text.")
    out.summary_line = f"Word · {_plural(words, 'word')}"
    return out


# ── PowerPoint ───────────────────────────────────────────────────────────────

def _extract_pptx(data: bytes) -> ExtractedFile:
    from pptx import Presentation

    try:
        deck = Presentation(io.BytesIO(data))
    except Exception as e:
        raise UnsupportedFile(f"This PowerPoint file couldn't be opened ({e}).") from e

    out = ExtractedFile(kind="pptx", mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    for i, slide in enumerate(deck.slides, start=1):
        lines = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
                text = "\n".join(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
                if text:
                    is_title = shape == getattr(slide.shapes, "title", None)
                    lines.append(f"# {text}" if is_title else text)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    lines.append("| " + " | ".join(" ".join(c.text.split()) for c in row.cells) + " |")
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            if notes:
                lines.append(f"Speaker notes: {notes}")
        out.sections.append(Section(f"slide {i}", "\n".join(lines)))
    out.page_count = len(deck.slides)
    out.summary_line = f"PowerPoint · {_plural(out.page_count, 'slide')}"
    return out


# ── Tables (CSV / Excel) ─────────────────────────────────────────────────────

def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "").replace("%", "")
        if re.fullmatch(r"-?\d+(\.\d+)?([eE]-?\d+)?", cleaned):
            return float(cleaned)
    return None


def _fmt(n: float) -> str:
    return f"{n:,.0f}" if abs(n) >= 1000 or n == int(n) else f"{n:,.4g}"


def profile_table(header: list[str], rows: list[list], name: str = "") -> str:
    """ChatGPT-style data profile: shape, column types, stats, sample rows."""
    cols = len(header)
    lines = [f"{name + ': ' if name else ''}{_plural(len(rows), 'row')} × {_plural(cols, 'column')}"]
    for c, col in enumerate(header):
        values = [r[c] for r in rows if c < len(r) and r[c] not in (None, "")]
        nums = [n for n in (_number(v) for v in values) if n is not None]
        missing = len(rows) - len(values)
        desc = f"- {col or f'column {c + 1}'}: "
        if values and len(nums) >= 0.8 * len(values):
            desc += f"numeric, min {_fmt(min(nums))}, max {_fmt(max(nums))}, mean {_fmt(sum(nums) / len(nums))}"
        else:
            distinct: dict[str, int] = {}
            for v in values:
                key = str(v)[:60]
                distinct[key] = distinct.get(key, 0) + 1
            top = sorted(distinct.items(), key=lambda kv: -kv[1])[:4]
            desc += f"text, {_plural(len(distinct), 'distinct value')}"
            if top and len(distinct) < len(values):
                desc += " (most common: " + ", ".join(f"{k} ×{n}" for k, n in top) + ")"
        if missing:
            desc += f", {missing:,} empty"
        lines.append(desc)
    return "\n".join(lines)


def table_text(header: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(["" if v is None else v for v in r] for r in rows)
    return buf.getvalue().strip()


def _chunk_rows(header: list[str], rows: list[list], label: str, per_section: int = 60) -> list[Section]:
    sections = []
    for start in range(0, len(rows), per_section):
        part = rows[start:start + per_section]
        sections.append(Section(f"{label}rows {start + 2}–{start + 1 + len(part)}", table_text(header, part)))
    return sections or [Section(label.strip(" ,") or "table", table_text(header, []))]


def _extract_csv(data: bytes, ext: str) -> ExtractedFile:
    text = _decode(data)
    out = ExtractedFile(kind="csv", mime_type="text/tab-separated-values" if ext == ".tsv" else "text/csv")
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|") if ext != ".tsv" else csv.excel_tab
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    all_rows = []
    for i, row in enumerate(reader):
        if i > MAX_TABLE_ROWS:
            out.warnings.append(f"Only the first {MAX_TABLE_ROWS:,} rows were read.")
            break
        all_rows.append(row)
    if not all_rows:
        out.warnings.append("This file is empty.")
        out.summary_line = "CSV · empty"
        return out
    header, rows = all_rows[0], all_rows[1:]
    out.overview = "Data profile\n" + profile_table(header, rows)
    out.sections = _chunk_rows(header, rows, "")
    out.page_count = len(rows)
    out.summary_line = f"{'TSV' if ext == '.tsv' else 'CSV'} · {_plural(len(rows), 'row')} × {len(header)} cols"
    return out


def _extract_xlsx(data: bytes) -> ExtractedFile:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as e:
        raise UnsupportedFile(f"This Excel file couldn't be opened ({e}).") from e

    out = ExtractedFile(kind="spreadsheet", mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    profiles, total_rows = [], 0
    for ws in wb.worksheets:
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i > MAX_TABLE_ROWS:
                out.warnings.append(f"Sheet {ws.title}: only the first {MAX_TABLE_ROWS:,} rows were read.")
                break
            if any(v not in (None, "") for v in row):
                rows.append(["" if v is None else v for v in row])
        if not rows:
            continue
        width = max(len(r) for r in rows)
        while width and all((len(r) < width or r[width - 1] in (None, "")) for r in rows):
            width -= 1
        rows = [list(r[:width]) + [""] * (width - len(r[:width])) for r in rows]
        header = [str(h) if h not in (None, "") else f"column {i + 1}" for i, h in enumerate(rows[0])]
        body = rows[1:]
        total_rows += len(body)
        profiles.append(profile_table(header, body, name=f"Sheet “{ws.title}”"))
        out.sections.extend(_chunk_rows(header, body, f"{ws.title}, "))
    wb.close()
    out.overview = "Data profile\n" + "\n\n".join(profiles) if profiles else ""
    if not profiles:
        out.warnings.append("This workbook has no data.")
    out.page_count = total_rows
    sheets = len(profiles)
    out.summary_line = f"Excel · {_plural(sheets, 'sheet')}, {_plural(total_rows, 'row')}"
    return out


# ── Text, code, HTML ─────────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr|section|article)>", "\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    import html as _html
    text = _html.unescape(text)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _strip_rtf(rtf: str) -> str:
    text = re.sub(r"\\par[d]?", "\n", rtf)
    text = re.sub(r"\{\\\*[^{}]*\}|\\[a-z]+-?\d* ?|[{}]", "", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _ipynb_text(raw: str) -> str:
    nb = json.loads(raw)
    parts = []
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        if cell.get("cell_type") == "code":
            parts.append(f"```python\n{src}\n```")
        else:
            parts.append(src)
    return "\n\n".join(parts)


def _extract_text(data: bytes, ext: str, filename: str) -> ExtractedFile:
    text = _decode(data)
    kind, mime = "text", "text/plain"
    if ext in HTML_EXT:
        text, mime = _strip_html(text), "text/html"
    elif ext == ".rtf":
        text, mime = _strip_rtf(text), "application/rtf"
    elif ext == ".ipynb":
        try:
            text, mime = _ipynb_text(text), "application/x-ipynb+json"
        except (ValueError, TypeError):
            pass
    elif ext in {".json", ".jsonl"}:
        mime = "application/json"
    out = ExtractedFile(kind=kind, mime_type=mime)
    text = _cap(text, out.warnings)
    lines = text.splitlines()
    # Label long files by line range so answers can cite "lines 120–180".
    if len(lines) > 150:
        for start in range(0, len(lines), 150):
            chunk = "\n".join(lines[start:start + 150])
            out.sections.append(Section(f"lines {start + 1}–{start + len(lines[start:start + 150])}", chunk))
    else:
        out.sections.append(Section("", text))
    out.page_count = len(lines)
    if not text.strip():
        out.warnings.append("This file is empty.")
    label = ext.lstrip(".").upper() if ext else "Text"
    out.summary_line = f"{label} · {_plural(len(lines), 'line')}"
    return out


def extract_file(data: bytes, filename: str) -> ExtractedFile:
    """Extract text from a non-image file. Raises UnsupportedFile with a user-facing message."""
    ext = check_supported(filename)
    if len(data) > MAX_UPLOAD_BYTES:
        raise UnsupportedFile(f"Files can be up to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if ext in PDF_EXT:
        return _extract_pdf(data)
    if ext in DOCX_EXT:
        return _extract_docx(data)
    if ext in PPTX_EXT:
        return _extract_pptx(data)
    if ext in XLSX_EXT:
        return _extract_xlsx(data)
    if ext in CSV_EXT:
        return _extract_csv(data, ext)
    if ext in IMAGE_EXT:
        raise ValueError("images are extracted asynchronously")
    return _extract_text(data, ext, filename)
