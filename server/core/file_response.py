"""Serve a stored file for in-app preview (inline) or as a download.

Inline responses never let the browser run the file: HTML, SVG and XML come
back as plain text, sniffing is off and the page is sandboxed, so a file Luna
wrote (or a user uploaded) can't execute scripts on the API's origin.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi.responses import FileResponse

_ACTIVE_TYPES = ("text/html", "application/xhtml+xml", "image/svg+xml", "text/xml", "application/xml",
                 "text/javascript", "application/javascript")


# Windows' registry maps these to Office types; browsers show them better as text.
_TEXT_TYPES = {".csv": "text/csv", ".tsv": "text/tab-separated-values", ".md": "text/markdown",
               ".log": "text/plain", ".py": "text/x-python"}


def file_response(path: Path, filename: str, media_type: str | None = None, download: bool = False) -> FileResponse:
    media_type = (_TEXT_TYPES.get(Path(filename).suffix.lower()) or media_type
                  or mimetypes.guess_type(filename)[0] or "application/octet-stream")
    if download:
        return FileResponse(path, media_type=media_type, filename=filename)
    headers = {"X-Content-Type-Options": "nosniff"}
    if media_type.split(";")[0].strip().lower() in _ACTIVE_TYPES:
        media_type = "text/plain; charset=utf-8"
    if media_type != "application/pdf":          # Chrome refuses to render PDFs in a sandboxed page
        headers["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'"
    return FileResponse(path, media_type=media_type, filename=filename,
                        content_disposition_type="inline", headers=headers)
