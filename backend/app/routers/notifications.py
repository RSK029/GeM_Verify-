from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user
from ..models import Notification, User
from ..schemas import NotificationListOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    unread = query.filter(Notification.read.is_(False)).count()
    if unread_only:
        query = query.filter(Notification.read.is_(False))
    items = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return NotificationListOut(
        items=[NotificationOut.model_validate(i) for i in items], unread_count=unread
    )


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    notification_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    item = db.get(Notification, notification_id)
    if not item or item.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"detail": "Notification not found", "code": "NOT_FOUND"},
        )
    item.read = True
    db.commit()


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.read.is_(False)
    ).update({Notification.read: True})
    db.commit()
