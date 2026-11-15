"""Chat file attachments: upload, extraction, retrieval, and per-turn context."""
from backend.services.files.extract import MAX_UPLOAD_BYTES, SUPPORTED_EXT, UnsupportedFile
from backend.services.files.service import (
    build_attachment_context,
    delete_attachment_files,
    link_to_message,
    load_extracted,
    original_path,
    prepare_large_file,
    save_upload,
)

__all__ = [
    "MAX_UPLOAD_BYTES",
    "SUPPORTED_EXT",
    "UnsupportedFile",
    "build_attachment_context",
    "delete_attachment_files",
    "link_to_message",
    "load_extracted",
    "original_path",
    "prepare_large_file",
    "save_upload",
]
