"""Shared FastAPI dependencies: current user, role gates, ownership checks.

The authorization rule the whole system rests on: a bidder may only ever reach
rows that trace back to their own user id. File paths are never the security
mechanism — every document read goes through ``authorize_document`` below.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import Bid, Document, Role, User
from .security import decode_session_token


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"detail": "Not authenticated", "code": "NOT_AUTHENTICATED"},
    )


def _forbidden(message: str = "Not permitted") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"detail": message, "code": "FORBIDDEN"},
    )


def _not_found(what: str = "Resource") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"detail": f"{what} not found", "code": "NOT_FOUND"},
    )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.SESSION_COOKIE)
    if not token:
        raise _unauthenticated()
    payload = decode_session_token(token)
    if not payload:
        raise _unauthenticated()
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise _unauthenticated()
    return user


def require_bidder(user: User = Depends(current_user)) -> User:
    if user.role != Role.BIDDER.value:
        raise _forbidden("Bidder access required")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.ADMIN.value:
        raise _forbidden("Administrator access required")
    return user


def authorize_bid(bid_id: int, user: User, db: Session, *, owner_only: bool = False) -> Bid:
    """Return the bid if this user may see it, else 403/404.

    Admins may read any bid. A bidder may only read their own. ``owner_only``
    additionally blocks admins, for actions only the bidder may take (submit,
    upload, resubmit).
    """
    bid = db.get(Bid, bid_id)
    if not bid:
        raise _not_found("Bid")
    if user.role == Role.ADMIN.value:
        if owner_only:
            raise _forbidden("Only the bidder may perform this action")
        return bid
    if bid.bidder_id != user.id:
        # Deliberately 403 rather than 404: the caller is authenticated and the
        # resource exists, so hiding it buys nothing and 403 is the honest code.
        raise _forbidden("This bid belongs to another bidder")
    return bid


def authorize_document(
    document_id: int, user: User, db: Session, *, owner_only: bool = False
) -> Document:
    doc = db.get(Document, document_id)
    if not doc:
        raise _not_found("Document")
    authorize_bid(doc.bid_id, user, db, owner_only=owner_only)
    return doc
