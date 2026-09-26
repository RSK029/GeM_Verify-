from __future__ import annotations

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import authorize_bid, current_user, require_bidder
from ..models import (
    AuditAction,
    Bid,
    BidStatus,
    ConsistencyReport,
    Document,
    DocumentStatus,
    DocumentType,
    NotificationType,
    Role,
    Tender,
    TenderStatus,
    User,
    utcnow,
)
from ..schemas import (
    BidCreateRequest,
    BidDetailOut,
    BidSummaryOut,
    BidVerificationOut,
    ConsistencyReportOut,
    DocumentOut,
)
from ..serializers import bid_summary_out, tender_out
from ..services import audit, notifications, storage
from ..verification import orchestrator

router = APIRouter(prefix="/bids", tags=["bids"])

_EDITABLE = {BidStatus.DRAFT.value, BidStatus.CLARIFICATION_REQUIRED.value}

#: States a bidder may pull a bid back from. A draft was never submitted, so it
#: is deleted rather than withdrawn; an approved or rejected bid has already
#: been decided, and withdrawing it after the fact would let a bidder erase an
#: adverse decision from the officer's queue.
_WITHDRAWABLE = {
    BidStatus.SUBMITTED.value,
    BidStatus.PROCESSING.value,
    BidStatus.VERIFIED.value,
    BidStatus.MANUAL_REVIEW.value,
    BidStatus.CLARIFICATION_REQUIRED.value,
}

#: States a bidder may start again from. Reapplying never revives the old bid —
#: it opens a fresh draft, so the withdrawn or rejected record and everything
#: the engine found in it survive for audit.
_REAPPLICABLE = {BidStatus.WITHDRAWN.value, BidStatus.REJECTED.value}


def _sees_scores(user: User) -> bool:
    return user.role == "ADMIN"


def _bad_request(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail={"detail": message, "code": code}
    )


@router.post("", response_model=BidSummaryOut, status_code=status.HTTP_201_CREATED)
def create_bid(
    payload: BidCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_bidder),
):
    tender = db.get(Tender, payload.tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Tender not found", "code": "NOT_FOUND"},
        )
    existing = (
        db.query(Bid)
        .filter(Bid.bidder_id == user.id, Bid.tender_id == tender.id, Bid.status == BidStatus.DRAFT.value)
        .first()
    )
    if existing:
        return bid_summary_out(existing, include_scores=False)

    bid = Bid(bidder_id=user.id, tender_id=tender.id, status=BidStatus.DRAFT.value)
    db.add(bid)
    db.flush()
    audit.record(
        db,
        user_id=user.id,
        action=AuditAction.BID_CREATED,
        bid_id=bid.id,
        details=f"Draft bid created for {tender.tender_number}",
    )
    db.commit()
    db.refresh(bid)
    return bid_summary_out(bid, include_scores=False)


@router.get("", response_model=list[BidSummaryOut])
def list_bids(
    # Named `status` on the wire, per docs/API_CONTRACT.md. The argument cannot
    # be called `status` because that name is already FastAPI's status-code
    # module in this file — hence the alias. Without it FastAPI looked for
    # `?status_filter=`, so the filter the UI sent was silently ignored and
    # every request returned the unfiltered list.
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_bidder),
):
    query = db.query(Bid).filter(Bid.bidder_id == user.id)
    if status_filter:
        query = query.filter(Bid.status == status_filter.upper())
    return [
        bid_summary_out(b, include_scores=False)
        for b in query.order_by(Bid.updated_at.desc()).all()
    ]


@router.get("/{bid_id}", response_model=BidDetailOut)
def get_bid(bid_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    bid = authorize_bid(bid_id, user, db)
    if user.role == "ADMIN":
        audit.record(
            db,
            user_id=user.id,
            action=AuditAction.ADMIN_VIEWED_BID,
            bid_id=bid.id,
            details=f"Administrator opened bid #{bid.id} ({bid.bidder.company_name})",
        )
        db.commit()
    summary = bid_summary_out(bid, include_scores=_sees_scores(user))
    return BidDetailOut(
        **summary.model_dump(),
        tender=tender_out(bid.tender),
        documents=[DocumentOut.model_validate(d) for d in bid.documents],
        decision_note=bid.decision_note,
    )


@router.delete("/{bid_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bid(bid_id: int, db: Session = Depends(get_db), user: User = Depends(require_bidder)):
    bid = authorize_bid(bid_id, user, db, owner_only=True)
    if bid.status != BidStatus.DRAFT.value:
        raise _bad_request("BID_NOT_EDITABLE", "Only a draft bid can be deleted")
    audit.record(
        db, user_id=user.id, action=AuditAction.BID_DELETED, bid_id=bid.id, details="Draft bid deleted"
    )
    db.delete(bid)
    db.commit()


@router.post("/{bid_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    bid_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_bidder),
):
    bid = authorize_bid(bid_id, user, db, owner_only=True)
    if bid.status not in _EDITABLE:
        raise _bad_request(
            "BID_NOT_EDITABLE", f"Documents cannot be changed while the bid is {bid.status}"
        )
    try:
        doc_type = DocumentType(document_type.upper())
    except ValueError:
        raise _bad_request("VALIDATION_ERROR", f"Unknown document type '{document_type}'")

    content = await file.read()
    storage.validate_pdf(content, file.content_type)
    stored = storage.save(content, bidder_id=user.id, bid_id=bid.id)

    # Replacing a slot on a draft supersedes the previous upload rather than
    # overwriting it, so the audit trail keeps every version.
    previous = (
        db.query(Document)
        .filter(
            Document.bid_id == bid.id,
            Document.document_type == doc_type.value,
            Document.status != DocumentStatus.SUPERSEDED.value,
        )
        .order_by(Document.version.desc())
        .first()
    )
    version = 1
    if previous:
        previous.status = DocumentStatus.SUPERSEDED.value
        version = previous.version + 1

    document = Document(
        bid_id=bid.id,
        document_type=doc_type.value,
        original_filename=file.filename or f"{doc_type.slug}.pdf",
        stored_filename=stored.stored_filename,
        file_path=stored.file_path,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        status=DocumentStatus.PENDING.value,
        version=version,
        supersedes_id=previous.id if previous else None,
    )
    db.add(document)
    db.flush()
    audit.record(
        db,
        user_id=user.id,
        action=AuditAction.DOCUMENT_UPLOADED,
        bid_id=bid.id,
        document_id=document.id,
        details=f"Uploaded {doc_type.value} ({document.original_filename}), version {version}",
    )
    bid.updated_at = utcnow()
    db.commit()
    db.refresh(document)
    return DocumentOut.model_validate(document)


@router.post("/{bid_id}/submit", response_model=BidSummaryOut, status_code=status.HTTP_202_ACCEPTED)
def submit_bid(
    bid_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_bidder),
):
    bid = authorize_bid(bid_id, user, db, owner_only=True)
    if bid.status not in _EDITABLE:
        raise _bad_request("BID_NOT_EDITABLE", f"A bid in state {bid.status} cannot be submitted")

    present = {d.document_type for d in bid.active_documents}
    missing = [
        r.label
        for r in bid.tender.required_documents
        if r.mandatory and r.document_type not in present
    ]
    if missing:
        raise _bad_request(
            "MISSING_REQUIRED_DOCUMENTS",
            "Missing mandatory documents: " + ", ".join(missing),
        )

    bid.status = BidStatus.PROCESSING.value
    bid.submitted_at = bid.submitted_at or utcnow()
    bid.updated_at = utcnow()
    audit.record(
        db,
        user_id=user.id,
        action=AuditAction.BID_SUBMITTED,
        bid_id=bid.id,
        details=f"Bid submitted with {len(present)} documents",
    )
    db.commit()
    db.refresh(bid)

    # Verification takes tens of seconds; it must not block this request.
    background.add_task(orchestrator.run_for_bid, bid.id)
    return bid_summary_out(bid, include_scores=False)


@router.post("/{bid_id}/withdraw", response_model=BidSummaryOut)
def withdraw_bid(bid_id: int, db: Session = Depends(get_db), user: User = Depends(require_bidder)):
    """Pull a submitted bid back out of the officer's queue.

    The bid is not deleted and its documents are not touched. Withdrawal is a
    state change with an audit entry, because a record that vanishes is worse
    than one that says plainly it was taken back, and by whom.
    """
    bid = authorize_bid(bid_id, user, db, owner_only=True)
    if bid.status == BidStatus.DRAFT.value:
        raise _bad_request(
            "BID_NOT_WITHDRAWABLE",
            "This bid has not been submitted yet — delete the draft instead",
        )
    if bid.status not in _WITHDRAWABLE:
        raise _bad_request(
            "BID_NOT_WITHDRAWABLE", f"A bid in state {bid.status} can no longer be withdrawn"
        )

    bid.status = BidStatus.WITHDRAWN.value
    bid.updated_at = utcnow()
    audit.record(
        db,
        user_id=user.id,
        action=AuditAction.BID_WITHDRAWN,
        bid_id=bid.id,
        details=f"Bid withdrawn by the bidder for {bid.tender.tender_number}",
    )
    for admin in db.query(User).filter(User.role == Role.ADMIN.value).all():
        notifications.notify(
            db,
            user_id=admin.id,
            bid_id=bid.id,
            type=NotificationType.BID_STATUS_CHANGED,
            title="A bid has been withdrawn",
            message=(
                f"{bid.bidder.company_name or user.name} withdrew their bid for "
                f"{bid.tender.tender_number}."
            ),
        )
    db.commit()
    db.refresh(bid)
    return bid_summary_out(bid, include_scores=False)


@router.post("/{bid_id}/reapply", response_model=BidSummaryOut, status_code=status.HTTP_201_CREATED)
def reapply(bid_id: int, db: Session = Depends(get_db), user: User = Depends(require_bidder)):
    """Start a fresh draft for the same tender after withdrawing or being rejected.

    A new bid rather than a reopened one: the earlier attempt, its verification
    results and the officer's decision note remain exactly as they were. The
    previously uploaded documents are carried across as fresh, unverified
    copies so the bidder only has to replace what actually needs changing —
    every one of them is re-run from scratch on the next submit.
    """
    previous = authorize_bid(bid_id, user, db, owner_only=True)
    if previous.status not in _REAPPLICABLE:
        raise _bad_request(
            "BID_NOT_REAPPLICABLE",
            f"A bid in state {previous.status} cannot be reapplied for",
        )
    if previous.tender.status != TenderStatus.OPEN.value:
        raise _bad_request("TENDER_CLOSED", "This tender is no longer accepting bids")

    existing_draft = (
        db.query(Bid)
        .filter(
            Bid.bidder_id == user.id,
            Bid.tender_id == previous.tender_id,
            Bid.status == BidStatus.DRAFT.value,
        )
        .first()
    )
    if existing_draft:
        return bid_summary_out(existing_draft, include_scores=False)

    bid = Bid(bidder_id=user.id, tender_id=previous.tender_id, status=BidStatus.DRAFT.value)
    db.add(bid)
    db.flush()

    carried = 0
    for document in previous.active_documents:
        db.add(
            Document(
                bid_id=bid.id,
                document_type=document.document_type,
                original_filename=document.original_filename,
                stored_filename=document.stored_filename,
                file_path=document.file_path,
                size_bytes=document.size_bytes,
                sha256=document.sha256,
                # Deliberately reset: nothing the engine concluded about the
                # old bid may be inherited by the new one.
                status=DocumentStatus.PENDING.value,
                version=1,
                supersedes_id=None,
            )
        )
        carried += 1

    audit.record(
        db,
        user_id=user.id,
        action=AuditAction.BID_REAPPLIED,
        bid_id=bid.id,
        details=(
            f"Reapplied for {previous.tender.tender_number} after bid #{previous.id} "
            f"({previous.status}); {carried} documents carried over"
        ),
    )
    db.commit()
    db.refresh(bid)
    return bid_summary_out(bid, include_scores=False)


@router.get("/{bid_id}/verification", response_model=BidVerificationOut)
def bid_verification(bid_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    bid = authorize_bid(bid_id, user, db)
    return BidVerificationOut(
        documents=[
            {
                "document_id": d.id,
                "document_type": d.document_type,
                "status": d.status,
                "results": d.results,
            }
            for d in bid.active_documents
        ]
    )


@router.get("/{bid_id}/consistency", response_model=ConsistencyReportOut)
def bid_consistency(bid_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    bid = authorize_bid(bid_id, user, db)
    report: ConsistencyReport | None = bid.consistency_report
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": "Consistency analysis has not run for this bid yet",
                "code": "NOT_FOUND",
            },
        )
    payload = dict(report.payload or {})
    dimensions = payload.get("dimensions", [])
    scored = _sees_scores(user)
    if not scored:
        # Strip every number before it leaves the server. The verdict words and
        # the flags stay: a bidder should be able to see that their Udyam
        # certificate names the company differently, without being handed a
        # percentage to argue about.
        dimensions = [_unscored_dimension(d) for d in dimensions]
    return ConsistencyReportOut(
        bid_id=bid.id,
        overall_score=report.overall_score if scored else None,
        document_score=report.document_score if scored else None,
        consistency_score=report.consistency_score if scored else None,
        dimensions=dimensions,
        flags=payload.get("flags", []),
        computed_at=report.computed_at,
    )


def _unscored_dimension(dimension: dict) -> dict:
    stripped = dict(dimension)
    stripped["score"] = None
    stripped["observations"] = [
        {**dict(observation), "similarity": None}
        for observation in dimension.get("observations", [])
    ]
    return stripped
