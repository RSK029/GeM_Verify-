from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import (
    AuditAction,
    AuditLog,
    Bid,
    BidStatus,
    Document,
    DocumentStatus,
    DocumentType,
    NotificationType,
    Tender,
    User,
    utcnow,
)
from ..schemas import (
    AdminOverviewOut,
    ApproveRequest,
    AuditLogListOut,
    AuditLogOut,
    BidSummaryOut,
    ClarificationRequest,
    RejectRequest,
)
from ..serializers import bid_summary_out
from ..services import audit, notifications

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_bid(bid_id: int, db: Session, *, decidable: bool = False) -> Bid:
    bid = db.get(Bid, bid_id)
    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Bid not found", "code": "NOT_FOUND"},
        )
    if decidable and bid.status == BidStatus.WITHDRAWN.value:
        # The bidder took this one back. Deciding it now would put a verdict on
        # a bid that is no longer in the competition.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": "This bid was withdrawn by the bidder and can no longer be decided",
                "code": "BID_WITHDRAWN",
            },
        )
    return bid


@router.get("/overview", response_model=AdminOverviewOut)
def overview(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    bids = db.query(Bid).filter(Bid.status != BidStatus.DRAFT.value).all()
    by_status: dict[str, int] = {}
    for bid in bids:
        by_status[bid.status] = by_status.get(bid.status, 0) + 1

    recent = sorted(bids, key=lambda b: b.submitted_at or b.updated_at, reverse=True)[:8]
    return AdminOverviewOut(
        total_bids=len(bids),
        by_status=by_status,
        recent_submissions=[bid_summary_out(b) for b in recent],
        attention_required=[
            bid_summary_out(b) for b in bids if b.status == BidStatus.MANUAL_REVIEW.value
        ],
        pending_clarifications=[
            bid_summary_out(b) for b in bids if b.status == BidStatus.CLARIFICATION_REQUIRED.value
        ],
    )


@router.get("/bids", response_model=list[BidSummaryOut])
def list_all_bids(
    status_filter: str | None = None,
    tender_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(Bid).join(User, Bid.bidder_id == User.id).join(Tender, Bid.tender_id == Tender.id)
    query = query.filter(Bid.status != BidStatus.DRAFT.value)
    if status_filter:
        query = query.filter(Bid.status == status_filter.upper())
    if tender_id:
        query = query.filter(Bid.tender_id == tender_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(User.company_name.ilike(like), Tender.tender_number.ilike(like), Tender.title.ilike(like))
        )
    return [bid_summary_out(b) for b in query.order_by(Bid.updated_at.desc()).all()]


@router.post("/bids/{bid_id}/approve", response_model=BidSummaryOut)
def approve(
    bid_id: int,
    payload: ApproveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    bid = _get_bid(bid_id, db, decidable=True)
    bid.status = BidStatus.APPROVED.value
    bid.decision_note = payload.note
    bid.updated_at = utcnow()
    audit.record(
        db,
        user_id=admin.id,
        action=AuditAction.ADMIN_APPROVED_BID,
        bid_id=bid.id,
        details=f"Bid approved. {payload.note}".strip(),
    )
    notifications.notify(
        db,
        user_id=bid.bidder_id,
        bid_id=bid.id,
        type=NotificationType.BID_STATUS_CHANGED,
        title="Your bid has been approved",
        message=payload.note
        or f"Your bid for {bid.tender.tender_number} has been approved after review.",
    )
    db.commit()
    db.refresh(bid)
    return bid_summary_out(bid)


@router.post("/bids/{bid_id}/reject", response_model=BidSummaryOut)
def reject(
    bid_id: int,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    bid = _get_bid(bid_id, db, decidable=True)
    bid.status = BidStatus.REJECTED.value
    bid.decision_note = payload.reason
    bid.updated_at = utcnow()
    audit.record(
        db,
        user_id=admin.id,
        action=AuditAction.ADMIN_REJECTED_BID,
        bid_id=bid.id,
        details=f"Bid rejected. Reason: {payload.reason}",
    )
    notifications.notify(
        db,
        user_id=bid.bidder_id,
        bid_id=bid.id,
        type=NotificationType.BID_STATUS_CHANGED,
        title="Your bid has been rejected",
        message=payload.reason,
    )
    db.commit()
    db.refresh(bid)
    return bid_summary_out(bid)


@router.post("/bids/{bid_id}/clarification", response_model=BidSummaryOut)
def request_clarification(
    bid_id: int,
    payload: ClarificationRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    bid = _get_bid(bid_id, db, decidable=True)
    named: list[str] = []
    for document_id in payload.document_ids:
        document = db.get(Document, document_id)
        if not document or document.bid_id != bid.id:
            continue
        document.status = DocumentStatus.CLARIFICATION_REQUIRED.value
        named.append(DocumentType(document.document_type).pretty)

    bid.status = BidStatus.CLARIFICATION_REQUIRED.value
    bid.decision_note = payload.message
    bid.updated_at = utcnow()
    audit.record(
        db,
        user_id=admin.id,
        action=AuditAction.ADMIN_REQUESTED_CLARIFICATION,
        bid_id=bid.id,
        details=f"Clarification requested on {', '.join(named) or 'the bid'}: {payload.message}",
    )
    notifications.notify(
        db,
        user_id=bid.bidder_id,
        bid_id=bid.id,
        type=NotificationType.CLARIFICATION_REQUIRED,
        title=(
            f"Clarification required on your {named[0]}" if named else "Clarification required"
        ),
        message=payload.message,
    )
    db.commit()
    db.refresh(bid)
    return bid_summary_out(bid)


@router.get("/audit-logs", response_model=AuditLogListOut)
def audit_logs(
    bid_id: int | None = None,
    user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(AuditLog)
    if bid_id:
        query = query.filter(AuditLog.bid_id == bid_id)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    names = {u.id: u.name for u in db.query(User).all()}
    return AuditLogListOut(
        items=[
            AuditLogOut(
                id=r.id,
                user_id=r.user_id,
                user_name=names.get(r.user_id) if r.user_id else "System",
                action=r.action,
                bid_id=r.bid_id,
                document_id=r.document_id,
                details=r.details,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total,
    )
