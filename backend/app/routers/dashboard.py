from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_bidder
from ..models import Bid, BidStatus, Notification, Tender, TenderStatus, User
from ..schemas import BidderDashboardOut, NotificationOut
from ..serializers import bid_summary_out, tender_list_out

router = APIRouter(tags=["dashboard"])

_ACTIVE = {
    BidStatus.SUBMITTED.value,
    BidStatus.PROCESSING.value,
    BidStatus.VERIFIED.value,
    BidStatus.MANUAL_REVIEW.value,
    BidStatus.CLARIFICATION_REQUIRED.value,
}


@router.get("/dashboard", response_model=BidderDashboardOut)
def bidder_dashboard(db: Session = Depends(get_db), user: User = Depends(require_bidder)):
    bids = (
        db.query(Bid)
        .filter(Bid.bidder_id == user.id)
        .order_by(Bid.updated_at.desc())
        .all()
    )
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    tenders = (
        db.query(Tender)
        .filter(Tender.status == TenderStatus.OPEN.value)
        .order_by(Tender.closing_date)
        .limit(5)
        .all()
    )
    action_required = [b for b in bids if b.status == BidStatus.CLARIFICATION_REQUIRED.value]
    return BidderDashboardOut(
        active_bids=sum(1 for b in bids if b.status in _ACTIVE),
        pending_verification=sum(
            1 for b in bids if b.status in {BidStatus.PROCESSING.value, BidStatus.SUBMITTED.value}
        ),
        clarification_required=len(action_required),
        verified_bids=sum(
            1 for b in bids if b.status in {BidStatus.VERIFIED.value, BidStatus.APPROVED.value}
        ),
        recent_bids=[bid_summary_out(b, include_scores=False) for b in bids[:5]],
        recent_notifications=[NotificationOut.model_validate(n) for n in notifications],
        action_required=[
            bid_summary_out(b, include_scores=False) for b in action_required
        ],
        open_tenders=[tender_list_out(t) for t in tenders],
    )
