"""The verification pipeline.

Runs in a background task so the submit request returns immediately and the
frontend polls for the result.

  1. extraction   PDF -> structured fields                  (extraction.py)
  2. rules        fields + registry -> PASS / FAIL / REVIEW  (rules.py)
  3. consistency  cross-document decision record             (consistency.py)
  4. narration    Ollama prose over the finished record      (stage 3, pending)

Stages 1-3 are fully deterministic: the same bid always yields the same verdict
and the same score. Stage 4 only ever reads the record produced here; it cannot
change a verdict.
"""

from __future__ import annotations

import logging
import traceback

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models import (
    AiExplanation,
    AuditAction,
    Bid,
    BidStatus,
    ConsistencyVerdict,
    Document,
    DocumentStatus,
    DocumentType,
    ExplanationKind,
    NotificationType,
    utcnow,
)
from ..services import audit, notifications, storage
from . import consistency, extraction, llm, rules
from .registry import gateway_for

log = logging.getLogger("gemverify.verification")


def run_for_bid(bid_id: int) -> None:
    """Entry point for BackgroundTasks. Owns its own database session."""
    db = SessionLocal()
    try:
        _run(db, bid_id)
        db.commit()
    except Exception:  # noqa: BLE001 - a failed run must not kill the worker
        db.rollback()
        log.error("verification failed for bid %s\n%s", bid_id, traceback.format_exc())
        _mark_failed(bid_id)
        return
    finally:
        db.close()

    # The verdict is committed and visible before narration starts, so the
    # dashboards update immediately and a slow model never delays a result.
    narrate(bid_id)


def narrate(bid_id: int, kinds: list[ExplanationKind] | None = None) -> None:
    """Generate and cache the AI explanations for a finished bid."""
    kinds = kinds or [ExplanationKind.ADMIN_SUMMARY, ExplanationKind.DECISION_REASONING]
    db = SessionLocal()
    try:
        bid = db.get(Bid, bid_id)
        if bid is None:
            return
        documents = bid.active_documents
        report = _report_view(bid)
        context = llm.build_context(bid, report, documents)

        for kind in kinds:
            text, model, is_fallback = llm.explain(kind, context)
            existing = (
                db.query(AiExplanation)
                .filter(AiExplanation.bid_id == bid.id, AiExplanation.kind == kind.value)
                .first()
            )
            if existing:
                existing.text = text
                existing.model = model
                existing.is_fallback = is_fallback
                existing.generated_at = utcnow()
            else:
                db.add(
                    AiExplanation(
                        bid_id=bid.id,
                        kind=kind.value,
                        text=text,
                        model=model,
                        is_fallback=is_fallback,
                    )
                )
        audit.record(
            db,
            user_id=None,
            action=AuditAction.EXPLANATION_GENERATED,
            bid_id=bid.id,
            details=f"Generated {len(kinds)} explanation(s)",
        )
        db.commit()
    except Exception:  # noqa: BLE001 - narration is never load-bearing
        db.rollback()
        log.warning("narration failed for bid %s\n%s", bid_id, traceback.format_exc())
    finally:
        db.close()


class _ReportView:
    """Adapts a stored ConsistencyReport back to what llm.build_context expects."""

    def __init__(self, flags: list[dict]):
        self.flags = flags


def _report_view(bid: Bid) -> _ReportView | None:
    stored = bid.consistency_report
    if not stored:
        return None
    return _ReportView((stored.payload or {}).get("flags", []))


def _mark_failed(bid_id: int) -> None:
    db = SessionLocal()
    try:
        bid = db.get(Bid, bid_id)
        if bid:
            bid.status = BidStatus.MANUAL_REVIEW.value
            bid.decision_note = (
                "Automated verification could not complete. Manual review required."
            )
            db.commit()
    finally:
        db.close()


def _run(db: Session, bid_id: int) -> None:
    bid = db.get(Bid, bid_id)
    if bid is None:
        return

    audit.record(
        db,
        user_id=None,
        action=AuditAction.VERIFICATION_STARTED,
        bid_id=bid.id,
        details=f"Verification started for bid #{bid.id}",
    )

    gateway = gateway_for(db)
    tender_number = bid.tender.tender_number
    documents = bid.active_documents

    # --- stage 1: extraction ---------------------------------------------
    for document in documents:
        _extract_document(db, document)

    # --- stage 2: deterministic rules -------------------------------------
    all_checks: list[rules.Check] = []
    for document in documents:
        all_checks.extend(rules.apply(db, document, gateway, tender_number))

    # --- stage 3: cross-document consistency ------------------------------
    report = consistency.analyse(bid, gateway)

    document_score = rules.score(all_checks)
    overall = round(
        settings.WEIGHT_DOCUMENT * document_score
        + settings.WEIGHT_CONSISTENCY * report.consistency_score,
        1,
    )
    consistency.persist(db, bid, report, document_score, overall)

    bid.document_score = document_score
    bid.consistency_score = report.consistency_score
    bid.verification_score = overall
    bid.status = _bid_status(documents, report)
    bid.decision_note = _summary_line(documents, report)
    bid.updated_at = utcnow()

    audit.record(
        db,
        user_id=None,
        action=AuditAction.VERIFICATION_COMPLETED,
        bid_id=bid.id,
        details=(
            f"Verification completed: status {bid.status}, score {overall} "
            f"(documents {document_score}, consistency {report.consistency_score}), "
            f"{len(report.flags)} cross-document flag(s)"
        ),
    )
    notifications.notify(
        db,
        user_id=bid.bidder_id,
        bid_id=bid.id,
        type=NotificationType.VERIFICATION_COMPLETED,
        title="Verification completed",
        message=(
            f"Your bid for {tender_number} has been verified. "
            f"Current status: {bid.status.replace('_', ' ').title()}."
        ),
    )


def _extract_document(db: Session, document: Document) -> None:
    document.status = DocumentStatus.PROCESSING.value
    db.flush()

    path = storage.absolute_path(document.file_path)
    try:
        fields = extraction.extract(path, document.document_type)
    except Exception as exc:  # noqa: BLE001
        document.extracted_fields = None
        document.extraction_error = str(exc)
        document.status = DocumentStatus.REVIEW.value
        return

    document.extracted_fields = fields
    missing = extraction.missing_fields(document.document_type, fields)
    # A parser gap is our problem, not the bidder's: it routes to REVIEW so a
    # human looks, never to FAILED.
    document.extraction_error = ("Could not read: " + ", ".join(missing)) if missing else None
    db.flush()


def _bid_status(documents: list[Document], report: consistency.Report) -> str:
    """A single flagged document never auto-rejects a bid — it escalates it.

    Rejection is a human decision. The pipeline's job is to decide whether a
    human needs to look, and to say why.
    """
    statuses = {d.status for d in documents}
    if statuses & {DocumentStatus.FAILED.value, DocumentStatus.REVIEW.value}:
        return BidStatus.MANUAL_REVIEW.value
    if consistency.worst_verdict(report) != ConsistencyVerdict.CONSISTENT.value:
        # Every document passed on its own, but they do not agree with each
        # other. This is the case GeMVerify exists to catch.
        return BidStatus.MANUAL_REVIEW.value
    return BidStatus.VERIFIED.value


def _summary_line(documents: list[Document], report: consistency.Report) -> str:
    total = len(documents)
    clean = sum(1 for d in documents if d.status == DocumentStatus.VERIFIED.value)
    parts = [f"{clean}/{total} documents passed their individual checks"]
    if report.flags:
        parts.append(f"{len(report.flags)} cross-document flag(s)")
    else:
        parts.append("no cross-document inconsistencies")
    return "; ".join(parts) + "."


def document_types_present(bid: Bid) -> set[DocumentType]:
    return {DocumentType(d.document_type) for d in bid.active_documents}
