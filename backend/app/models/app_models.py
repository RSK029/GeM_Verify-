"""Application tables — the system's own data."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .enums import (
    BidStatus,
    CheckResult,
    DocumentStatus,
    DocumentType,
    ExplanationKind,
    NotificationType,
    Role,
    TenderStatus,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default=Role.BIDDER.value, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    bids: Mapped[list["Bid"]] = relationship(back_populates="bidder")


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tender_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    department: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_value: Mapped[int] = mapped_column(Integer, default=0)
    closing_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=TenderStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    required_documents: Mapped[list["TenderRequiredDocument"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan", order_by="TenderRequiredDocument.sort_order"
    )
    bids: Mapped[list["Bid"]] = relationship(back_populates="tender")


class TenderRequiredDocument(Base):
    """Which document types a given tender demands. Drives the upload UI."""

    __tablename__ = "tender_required_documents"
    __table_args__ = (UniqueConstraint("tender_id", "document_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"))
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    tender: Mapped[Tender] = relationship(back_populates="required_documents")


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(primary_key=True)
    bidder_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=BidStatus.DRAFT.value, index=True)
    verification_score: Mapped[float | None] = mapped_column(Float)
    document_score: Mapped[float | None] = mapped_column(Float)
    consistency_score: Mapped[float | None] = mapped_column(Float)
    decision_note: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    bidder: Mapped[User] = relationship(back_populates="bids")
    tender: Mapped[Tender] = relationship(back_populates="bids")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="bid", cascade="all, delete-orphan"
    )
    consistency_report: Mapped["ConsistencyReport | None"] = relationship(
        back_populates="bid", cascade="all, delete-orphan", uselist=False
    )

    @property
    def active_documents(self) -> list["Document"]:
        return [d for d in self.documents if d.status != DocumentStatus.SUPERSEDED.value]


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default=DocumentStatus.PENDING.value)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    extracted_fields: Mapped[dict | None] = mapped_column(JSON)
    extraction_error: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    bid: Mapped[Bid] = relationship(back_populates="documents")
    results: Mapped[list["VerificationResult"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class VerificationResult(Base):
    """One deterministic check against one document. Never written by the LLM."""

    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    check_type: Mapped[str] = mapped_column(String(48), nullable=False)
    result: Mapped[str] = mapped_column(String(16), default=CheckResult.SKIPPED.value)
    submitted_value: Mapped[str | None] = mapped_column(Text)
    registry_value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    document: Mapped[Document] = relationship(back_populates="results")


class ConsistencyReport(Base):
    """The cross-document decision record. One row per bid, replaced on re-run."""

    __tablename__ = "consistency_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    bid_id: Mapped[int] = mapped_column(
        ForeignKey("bids.id", ondelete="CASCADE"), unique=True, index=True
    )
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    document_score: Mapped[float] = mapped_column(Float, default=0.0)
    consistency_score: Mapped[float] = mapped_column(Float, default=0.0)
    #: full decision record: dimensions + flags, exactly as the API returns it
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    bid: Mapped[Bid] = relationship(back_populates="consistency_report")


class AiExplanation(Base):
    """Generated prose. Cached per (bid, kind). Never authoritative."""

    __tablename__ = "ai_explanations"
    __table_args__ = (UniqueConstraint("bid_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default=ExplanationKind.ADMIN_SUMMARY.value)
    text: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str | None] = mapped_column(String(80))
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bid_id: Mapped[int | None] = mapped_column(ForeignKey("bids.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32), default=NotificationType.BID_STATUS_CHANGED.value)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    bid_id: Mapped[int | None] = mapped_column(Integer, index=True)
    document_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
