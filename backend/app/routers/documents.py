"""Document metadata and authenticated file streaming.

``/uploads`` is never mounted as a static directory. The only route to a stored
document is this one, which authorizes the caller against the owning bid and
writes an audit entry before any bytes are returned.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import authorize_document, current_user, require_bidder
from ..models import (
    AuditAction,
    BidStatus,
    Document,
    DocumentStatus,
    NotificationType,
    Role,
    User,
    utcnow,
)
from ..schemas import DocumentOut, VerificationResultOut
from ..services import audit, notifications, storage
from ..verification import orchestrator

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/meta", response_model=DocumentOut)
def document_meta(
    document_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return DocumentOut.model_validate(authorize_document(document_id, user, db))


@router.get("/{document_id}/verification", response_model=list[VerificationResultOut])
def document_verification(
    document_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return authorize_document(document_id, user, db).results


@router.get("/{document_id}")
def download_document(
    document_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    document = authorize_document(document_id, user, db)
    path = storage.absolute_path(document.file_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Stored file is missing", "code": "NOT_FOUND"},
        )
    action = (
        AuditAction.ADMIN_VIEWED_DOCUMENT
        if user.role == Role.ADMIN.value
        else AuditAction.DOCUMENT_VIEWED
    )
    audit.record(
        db,
        user_id=user.id,
        action=action,
        bid_id=document.bid_id,
        document_id=document.id,
        details=f"Viewed {document.document_type} ({document.original_filename})",
    )
    db.commit()
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.original_filename,
        headers={"Content-Disposition": f'inline; filename="{document.original_filename}"'},
    )


@router.post("/{document_id}/resubmit", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def resubmit_document(
    document_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_bidder),
):
    previous = authorize_document(document_id, user, db, owner_only=True)
    bid = previous.bid

    content = await file.read()
    storage.validate_pdf(content, file.content_type)
    stored = storage.save(content, bidder_id=user.id, bid_id=bid.id)

    # Never overwrite the evidence: the old row is kept and marked superseded.
    previous.status = DocumentStatus.SUPERSEDED.value
    document = Document(
        bid_id=bid.id,
        document_type=previous.document_type,
        original_filename=file.filename or previous.original_filename,
        stored_filename=stored.stored_filename,
        file_path=stored.file_path,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        status=DocumentStatus.PENDING.value,
        version=previous.version + 1,
        supersedes_id=previous.id,
    )
    db.add(document)
    db.flush()

    audit.record(
        db,
        user_id=user.id,
        action=AuditAction.DOCUMENT_RESUBMITTED,
        bid_id=bid.id,
        document_id=document.id,
        details=(
            f"Revised {document.document_type} uploaded "
            f"(version {document.version}, replaces #{previous.id})"
        ),
    )

    admins = db.query(User).filter(User.role == Role.ADMIN.value).all()
    for admin in admins:
        notifications.notify(
            db,
            user_id=admin.id,
            bid_id=bid.id,
            type=NotificationType.DOCUMENT_RESUBMITTED,
            title="Document resubmitted",
            message=(
                f"{bid.bidder.company_name} re-uploaded "
                f"{document.document_type.replace('_', ' ').title()} on bid #{bid.id}."
            ),
        )

    bid.status = BidStatus.PROCESSING.value
    bid.updated_at = utcnow()
    db.commit()
    db.refresh(document)

    background.add_task(orchestrator.run_for_bid, bid.id)
    return DocumentOut.model_validate(document)
