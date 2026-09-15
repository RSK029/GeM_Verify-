"""Private server-side document storage.

Uploaded documents are sensitive. They are written under ``backend/uploads/``,
which is never mounted as a static route — the only way to read one back is
``GET /api/documents/{id}``, which authorizes first and logs the access.

Stored filenames are random. The original filename is kept in the database as a
display label only; it never influences the path on disk, so a crafted filename
cannot escape the upload root.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from ..config import settings


@dataclass(frozen=True)
class StoredFile:
    stored_filename: str
    file_path: str
    size_bytes: int
    sha256: str


def _reject(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": message, "code": code}
    )


def validate_pdf(content: bytes, declared_content_type: str | None) -> None:
    """Validate by magic bytes, not by the client's claims."""
    if len(content) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "detail": f"File exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
                "code": "FILE_TOO_LARGE",
            },
        )
    if not content:
        raise _reject("UNSUPPORTED_FILE_TYPE", "File is empty")
    if not content.startswith(settings.PDF_MAGIC):
        raise _reject(
            "UNSUPPORTED_FILE_TYPE",
            "Only PDF documents are accepted (file does not start with %PDF-)",
        )
    if declared_content_type and declared_content_type not in settings.ALLOWED_MIME:
        # Advisory only — the magic-byte check above is the real gate.
        pass


def bid_directory(bidder_id: int, bid_id: int) -> Path:
    path = settings.UPLOAD_DIR / f"bidder_{bidder_id:03d}" / f"bid_{bid_id:04d}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(content: bytes, *, bidder_id: int, bid_id: int) -> StoredFile:
    directory = bid_directory(bidder_id, bid_id)
    stored_filename = f"{uuid.uuid4().hex}.pdf"
    destination = directory / stored_filename
    destination.write_bytes(content)
    return StoredFile(
        stored_filename=stored_filename,
        file_path=str(destination.relative_to(settings.UPLOAD_DIR)),
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def absolute_path(file_path: str) -> Path:
    """Resolve a stored relative path, refusing anything outside the upload root."""
    root = settings.UPLOAD_DIR.resolve()
    candidate = (root / file_path).resolve()
    if not str(candidate).startswith(str(root)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "Invalid document path", "code": "FORBIDDEN"},
        )
    return candidate
