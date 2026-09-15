"""Authentication.

There is no role selector at login. The caller sends an email and a password;
the backend looks up the row, verifies the Argon2id hash and returns the role
stored in the database. The frontend routes on that role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import current_user
from ..models import AuditAction, Role, User
from ..schemas import LoginRequest, RegisterRequest, UserOut
from ..security import create_session_token, hash_password, needs_rehash, verify_password
from ..services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE,
        value=create_session_token(user.id, user.role),
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
        max_age=settings.SESSION_TTL_HOURS * 3600,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "An account with this email already exists", "code": "DUPLICATE_EMAIL"},
        )
    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=Role.BIDDER.value,  # admins are seed-only; never self-registered
        company_name=payload.company_name.strip(),
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        user_id=user.id,
        action=AuditAction.USER_REGISTERED,
        details=f"Bidder registered: {user.company_name}",
    )
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        # Same message either way: do not reveal whether the email exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "Incorrect email or password", "code": "INVALID_CREDENTIALS"},
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    audit.record(
        db, user_id=user.id, action=AuditAction.USER_LOGGED_IN, details=f"Signed in as {user.role}"
    )
    db.commit()
    _set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)):
    audit.record(db, user_id=user.id, action=AuditAction.USER_LOGGED_OUT, details="Signed out")
    db.commit()
    response.delete_cookie(settings.SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
