"""AI explanation endpoints.

These serve cached prose generated after verification finished. They never
produce a verdict, a score or a status — the decision record is the authority,
and the UI must present these beside the evidence, never in place of it.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import authorize_bid, current_user, require_admin
from ..models import AiExplanation, ExplanationKind, Role, User
from ..schemas import AiExplanationOut, RegenerateRequest
from ..verification import llm, orchestrator

router = APIRouter(tags=["explanations"])

#: A bidder may read the explanations addressed to them, not the officer's
#: internal review notes.
_BIDDER_KINDS = {
    ExplanationKind.CLARIFICATION_DRAFT.value,
    ExplanationKind.DECISION_REASONING.value,
}


@router.get("/bids/{bid_id}/explanation", response_model=AiExplanationOut)
def get_explanation(
    bid_id: int,
    kind: str = ExplanationKind.ADMIN_SUMMARY.value,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    bid = authorize_bid(bid_id, user, db)
    try:
        wanted = ExplanationKind(kind.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Unknown explanation kind '{kind}'", "code": "VALIDATION_ERROR"},
        )
    if user.role != Role.ADMIN.value and wanted.value not in _BIDDER_KINDS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"detail": "This explanation is for procurement officers", "code": "FORBIDDEN"},
        )

    row = (
        db.query(AiExplanation)
        .filter(AiExplanation.bid_id == bid.id, AiExplanation.kind == wanted.value)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": "This explanation has not been generated yet",
                "code": "NOT_FOUND",
            },
        )
    return AiExplanationOut.model_validate(row)


@router.post("/bids/{bid_id}/explanation/regenerate", status_code=status.HTTP_202_ACCEPTED)
def regenerate(
    bid_id: int,
    payload: RegenerateRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    bid = authorize_bid(bid_id, admin, db)
    try:
        wanted = ExplanationKind(payload.kind.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": f"Unknown explanation kind '{payload.kind}'", "code": "VALIDATION_ERROR"},
        )
    background.add_task(orchestrator.narrate, bid.id, [wanted])
    return {"detail": "Generation started", "code": "ACCEPTED"}


@router.get("/ai/status", tags=["meta"])
def ai_status(_: User = Depends(current_user)):
    """Whether narration will use the model or the templated fallback.

    Useful before a demo: it says in one call whether Ollama is reachable and
    whether the configured model is actually pulled.
    """
    ready, reason = llm.available()
    return {"ready": ready, "detail": reason}
