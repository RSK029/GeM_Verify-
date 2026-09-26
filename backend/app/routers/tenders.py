from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Tender, User
from ..schemas import TenderListOut, TenderOut
from ..serializers import tender_list_out, tender_out

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("", response_model=list[TenderListOut])
def list_tenders(
    # Named `status` on the wire, per docs/API_CONTRACT.md. The argument cannot
    # be called `status` because that name is already FastAPI's status-code
    # module in this file — hence the alias. Without it FastAPI looked for
    # `?status_filter=`, so the filter the UI sent was silently ignored and
    # every request returned the unfiltered list.
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    query = db.query(Tender)
    if status_filter:
        query = query.filter(Tender.status == status_filter.upper())
    return [tender_list_out(t) for t in query.order_by(Tender.closing_date).all()]


@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(
    tender_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)
):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Tender not found", "code": "NOT_FOUND"},
        )
    return tender_out(tender)
