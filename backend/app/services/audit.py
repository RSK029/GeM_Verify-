"""Single choke point for the audit trail.

Every accountability-relevant action goes through ``record()``. Nothing else in
the codebase inserts into ``audit_logs``, so the trail cannot quietly develop
holes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import AuditAction, AuditLog


def record(
    db: Session,
    *,
    user_id: int | None,
    action: AuditAction | str,
    details: str = "",
    bid_id: int | None = None,
    document_id: int | None = None,
    commit: bool = False,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=str(action),
        bid_id=bid_id,
        document_id=document_id,
        details=details,
    )
    db.add(entry)
    if commit:
        db.commit()
    else:
        db.flush()
    return entry
