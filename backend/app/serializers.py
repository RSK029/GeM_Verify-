"""Model -> schema conversions used by more than one router."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Bid, DocumentStatus, Tender
from .schemas import BidSummaryOut, DocumentOut, TenderListOut, TenderOut

_FLAGGED = {
    DocumentStatus.REVIEW.value,
    DocumentStatus.FAILED.value,
    DocumentStatus.CLARIFICATION_REQUIRED.value,
}


def tender_list_out(tender: Tender) -> TenderListOut:
    return TenderListOut(
        id=tender.id,
        tender_number=tender.tender_number,
        title=tender.title,
        department=tender.department,
        estimated_value=tender.estimated_value,
        closing_date=tender.closing_date,
        status=tender.status,
        required_document_count=len(tender.required_documents),
        created_at=tender.created_at,
    )


def tender_out(tender: Tender) -> TenderOut:
    return TenderOut(
        **tender_list_out(tender).model_dump(),
        description=tender.description or "",
        required_documents=[
            {"document_type": r.document_type, "label": r.label, "mandatory": r.mandatory}
            for r in tender.required_documents
        ],
    )


def bid_summary_out(bid: Bid, *, include_scores: bool = True) -> BidSummaryOut:
    """Serialise a bid.

    ``include_scores`` is the single gate for the numeric verification score.
    Bidders never see it: a percentage invites the reading that a bid is "93%
    valid", when what actually decides the outcome is the individual findings
    and a human officer's judgement. The flags, not the score, carry the
    finding — so the number is withheld on the wire rather than merely hidden
    in the browser, where anyone could read it back out of the network tab.
    """
    active = bid.active_documents
    return BidSummaryOut(
        id=bid.id,
        tender_id=bid.tender_id,
        tender_number=bid.tender.tender_number,
        tender_title=bid.tender.title,
        bidder_id=bid.bidder_id,
        bidder_company=bid.bidder.company_name,
        status=bid.status,
        verification_score=bid.verification_score if include_scores else None,
        document_count=len(active),
        documents_verified=sum(
            1 for d in active if d.status == DocumentStatus.VERIFIED.value
        ),
        documents_flagged=sum(1 for d in active if d.status in _FLAGGED),
        submitted_at=bid.submitted_at,
        updated_at=bid.updated_at,
    )


def document_out(document) -> DocumentOut:
    return DocumentOut.model_validate(document)


def summaries(db: Session, bids, *, include_scores: bool = True) -> list[BidSummaryOut]:
    _ = db
    return [bid_summary_out(b, include_scores=include_scores) for b in bids]
