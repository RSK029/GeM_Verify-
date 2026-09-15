"""Persistent notifications.

Notifications live in the database rather than in memory so a bidder who is
offline when an admin acts still sees the message on their next login.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Notification, NotificationType


def notify(
    db: Session,
    *,
    user_id: int,
    type: NotificationType | str,
    title: str,
    message: str = "",
    bid_id: int | None = None,
    commit: bool = False,
) -> Notification:
    item = Notification(
        user_id=user_id,
        bid_id=bid_id,
        type=str(type),
        title=title,
        message=message,
    )
    db.add(item)
    if commit:
        db.commit()
    else:
        db.flush()
    return item
