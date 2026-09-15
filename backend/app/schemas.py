"""Pydantic request/response models. Shapes follow docs/API_CONTRACT.md."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer


def _as_utc_z(value: datetime) -> str:
    """Serialise a timestamp as ISO-8601 UTC with an explicit `Z`.

    The DateTime columns are timezone-naive, so SQLite hands back
    `2026-09-15T12:25:23.842600` with no designator. JavaScript parses a naive
    string as *local* time, which silently shifts every timestamp in the UI by
    the viewer's offset — five and a half hours in IST.

    Everything stored is UTC, so a naive value is treated as UTC here and the
    designator is re-attached. This is the server's job: a client cannot know
    what an undesignated timestamp means, and should not have to guess.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


#: Use instead of `datetime` on every response field. Matches the contract's
#: stated format: "2026-09-15T10:32:04Z".
UtcDatetime = Annotated[
    datetime, PlainSerializer(_as_utc_z, return_type=str, when_used="json")
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth -----------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    company_name: str = Field(min_length=2, max_length=200)


class LoginRequest(BaseModel):
    """Login deliberately takes a plain string, not EmailStr.

    Registration validates the address properly — that is the right place for
    it. But at login, a malformed address is simply a failed login: it must
    return 401, not a 422 explaining *why* the address was rejected. Anything
    else is a worse experience and tells an attacker something about the input
    that was refused.

    (This is not hypothetical: EmailStr rejects reserved TLDs such as `.local`,
    which locked the seeded administrator out of its own system.)
    """

    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    role: str
    company_name: str | None
    created_at: UtcDatetime


# --- tenders --------------------------------------------------------------


class RequiredDocumentOut(ORMModel):
    document_type: str
    label: str
    mandatory: bool


class TenderListOut(ORMModel):
    id: int
    tender_number: str
    title: str
    department: str
    estimated_value: int
    closing_date: UtcDatetime
    status: str
    required_document_count: int = 0
    created_at: UtcDatetime


class TenderOut(TenderListOut):
    description: str
    required_documents: list[RequiredDocumentOut] = []


# --- documents ------------------------------------------------------------


class DocumentOut(ORMModel):
    id: int
    bid_id: int
    document_type: str
    original_filename: str
    size_bytes: int
    status: str
    version: int
    supersedes_id: int | None
    uploaded_at: UtcDatetime
    extracted_fields: dict | None = None
    extraction_error: str | None = None


class VerificationResultOut(ORMModel):
    id: int
    document_id: int
    check_type: str
    result: str
    submitted_value: str | None
    registry_value: str | None
    confidence: float
    reason: str
    created_at: UtcDatetime


class DocumentVerificationOut(BaseModel):
    document_id: int
    document_type: str
    status: str
    results: list[VerificationResultOut]


class BidVerificationOut(BaseModel):
    documents: list[DocumentVerificationOut]


# --- bids -----------------------------------------------------------------


class BidCreateRequest(BaseModel):
    tender_id: int


class BidSummaryOut(BaseModel):
    id: int
    tender_id: int
    tender_number: str
    tender_title: str
    bidder_id: int
    bidder_company: str | None
    status: str
    verification_score: float | None
    document_count: int
    documents_verified: int
    documents_flagged: int
    submitted_at: UtcDatetime | None
    updated_at: UtcDatetime


class BidDetailOut(BidSummaryOut):
    tender: TenderOut
    documents: list[DocumentOut]
    decision_note: str | None = None


# --- consistency ----------------------------------------------------------


class ConsistencyObservation(BaseModel):
    document_type: str
    document_id: int | None = None
    value: str | None = None
    similarity: float | None = None
    verdict: str
    reason: str = ""


class ConsistencyDimensionOut(BaseModel):
    dimension: str
    score: float | None
    verdict: str
    canonical_value: str | None = None
    canonical_source: str | None = None
    observations: list[ConsistencyObservation] = []


class ConsistencyFlagOut(BaseModel):
    id: str
    dimension: str
    verdict: str
    title: str
    documents_involved: list[str] = []
    values: dict[str, str | None] = {}


class ConsistencyReportOut(BaseModel):
    """The cross-document decision record as the API returns it.

    The three scores are nullable because they are withheld from bidders — see
    `serializers.bid_summary_out`. Administrators always receive them. The
    verdicts and flags are returned to both: a bidder is entitled to know
    *what* was found in their own documents, just not to a number that reads
    like a grade.
    """

    bid_id: int
    overall_score: float | None = None
    document_score: float | None = None
    consistency_score: float | None = None
    dimensions: list[ConsistencyDimensionOut]
    flags: list[ConsistencyFlagOut]
    computed_at: UtcDatetime


# --- explanations ---------------------------------------------------------


class AiExplanationOut(ORMModel):
    bid_id: int
    kind: str
    text: str
    model: str | None
    is_fallback: bool
    generated_at: UtcDatetime


class RegenerateRequest(BaseModel):
    kind: str = "ADMIN_SUMMARY"


# --- notifications --------------------------------------------------------


class NotificationOut(ORMModel):
    id: int
    user_id: int
    bid_id: int | None
    type: str
    title: str
    message: str
    read: bool
    created_at: UtcDatetime


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int


# --- audit ----------------------------------------------------------------


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None
    action: str
    bid_id: int | None
    document_id: int | None
    details: str
    created_at: UtcDatetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    total: int


# --- admin actions --------------------------------------------------------


class ApproveRequest(BaseModel):
    note: str = ""


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3)


class ClarificationRequest(BaseModel):
    document_ids: list[int] = []
    message: str = Field(min_length=3)


class AdminOverviewOut(BaseModel):
    total_bids: int
    by_status: dict[str, int]
    recent_submissions: list[BidSummaryOut]
    attention_required: list[BidSummaryOut]
    pending_clarifications: list[BidSummaryOut]


class BidderDashboardOut(BaseModel):
    active_bids: int
    pending_verification: int
    clarification_required: int
    verified_bids: int
    recent_bids: list[BidSummaryOut]
    recent_notifications: list[NotificationOut]
    action_required: list[BidSummaryOut]
    open_tenders: list[TenderListOut]
