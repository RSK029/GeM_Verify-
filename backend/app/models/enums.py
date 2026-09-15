"""Enumerations shared by the ORM, the API schemas and the verification engine.

These are plain str subclasses so they serialise as their own value and compare
cleanly against strings coming off the wire. The exact spellings are part of the
frozen API contract — see docs/API_CONTRACT.md.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Role(StrEnum):
    BIDDER = "BIDDER"
    ADMIN = "ADMIN"


class TenderStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class BidStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    #: Pulled back by the bidder before a decision was reached. Terminal for
    #: this bid — the tender is re-entered by creating a fresh draft, so the
    #: withdrawn record and its audit trail stay intact.
    WITHDRAWN = "WITHDRAWN"


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REVIEW = "REVIEW"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    SUPERSEDED = "SUPERSEDED"


class DocumentType(StrEnum):
    CONTRACT = "CONTRACT"
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    UDYAM = "UDYAM"
    INCORPORATION = "INCORPORATION"
    EPFO_ESIC = "EPFO_ESIC"
    OEM_AUTHORISATION = "OEM_AUTHORISATION"
    LOCAL_CONTENT = "LOCAL_CONTENT"
    TURNOVER = "TURNOVER"
    EXPERIENCE = "EXPERIENCE"
    BANK_MANDATE = "BANK_MANDATE"

    @property
    def slug(self) -> str:
        """Specimen filename fragment: GST_CERTIFICATE -> gst-certificate."""
        return self.value.lower().replace("_", "-")

    @classmethod
    def from_slug(cls, slug: str) -> "DocumentType":
        return cls(slug.upper().replace("-", "_"))

    @property
    def pretty(self) -> str:
        """Display name. Acronyms stay upper-case: PAN, GST, CIN, EPFO."""
        return _PRETTY.get(self, self.value.replace("_", " ").title())


_PRETTY: dict["DocumentType", str] = {}


_PRETTY.update(
    {
        DocumentType.CONTRACT: "Signed Contract",
        DocumentType.AADHAAR: "Aadhaar",
        DocumentType.PAN: "PAN Card",
        DocumentType.GST_CERTIFICATE: "GST Certificate",
        DocumentType.UDYAM: "Udyam Certificate",
        DocumentType.INCORPORATION: "Certificate of Incorporation",
        DocumentType.EPFO_ESIC: "EPFO / ESIC Proof",
        DocumentType.OEM_AUTHORISATION: "OEM Authorisation",
        DocumentType.LOCAL_CONTENT: "Local Content Declaration",
        DocumentType.TURNOVER: "Turnover Certificate",
        DocumentType.EXPERIENCE: "Experience Certificate",
        DocumentType.BANK_MANDATE: "Bank Mandate",
    }
)

#: Human labels for the UI and for seeded tender requirements.
DOCUMENT_LABELS: dict[DocumentType, str] = {
    DocumentType.CONTRACT: "Signed Tender Document",
    DocumentType.AADHAAR: "Aadhaar of Authorised Signatory",
    DocumentType.PAN: "PAN Card (Company)",
    DocumentType.GST_CERTIFICATE: "GST Registration Certificate",
    DocumentType.UDYAM: "Udyam / MSME Registration Certificate",
    DocumentType.INCORPORATION: "Certificate of Incorporation",
    DocumentType.EPFO_ESIC: "EPFO / ESIC Establishment Proof",
    DocumentType.OEM_AUTHORISATION: "OEM Authorisation Letter",
    DocumentType.LOCAL_CONTENT: "Local Content Declaration",
    DocumentType.TURNOVER: "CA-Certified Turnover Statement",
    DocumentType.EXPERIENCE: "Work Experience Certificates",
    DocumentType.BANK_MANDATE: "Bank Mandate / Cancelled Cheque",
}


class CheckResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    SKIPPED = "SKIPPED"


class ConsistencyVerdict(StrEnum):
    CONSISTENT = "CONSISTENT"
    VARIATION = "VARIATION"
    POTENTIAL_INCONSISTENCY = "POTENTIAL_INCONSISTENCY"
    INCONSISTENT = "INCONSISTENT"


class ConsistencyDimension(StrEnum):
    IDENTITY = "IDENTITY"
    ADDRESS = "ADDRESS"
    REGISTRATION = "REGISTRATION"
    PAN = "PAN"
    SIGNATORY = "SIGNATORY"


class NotificationType(StrEnum):
    NEW_TENDER = "NEW_TENDER"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    BID_STATUS_CHANGED = "BID_STATUS_CHANGED"
    DOCUMENT_RESUBMITTED = "DOCUMENT_RESUBMITTED"


class ExplanationKind(StrEnum):
    ADMIN_SUMMARY = "ADMIN_SUMMARY"
    FLAG_EXPLANATION = "FLAG_EXPLANATION"
    CLARIFICATION_DRAFT = "CLARIFICATION_DRAFT"
    DECISION_REASONING = "DECISION_REASONING"


class AuditAction(StrEnum):
    USER_REGISTERED = "USER_REGISTERED"
    USER_LOGGED_IN = "USER_LOGGED_IN"
    USER_LOGGED_OUT = "USER_LOGGED_OUT"
    BID_CREATED = "BID_CREATED"
    BID_SUBMITTED = "BID_SUBMITTED"
    BID_DELETED = "BID_DELETED"
    BID_WITHDRAWN = "BID_WITHDRAWN"
    BID_REAPPLIED = "BID_REAPPLIED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_RESUBMITTED = "DOCUMENT_RESUBMITTED"
    DOCUMENT_VIEWED = "DOCUMENT_VIEWED"
    ADMIN_VIEWED_BID = "ADMIN_VIEWED_BID"
    ADMIN_VIEWED_DOCUMENT = "ADMIN_VIEWED_DOCUMENT"
    ADMIN_APPROVED_BID = "ADMIN_APPROVED_BID"
    ADMIN_REJECTED_BID = "ADMIN_REJECTED_BID"
    ADMIN_REQUESTED_CLARIFICATION = "ADMIN_REQUESTED_CLARIFICATION"
    VERIFICATION_STARTED = "VERIFICATION_STARTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    EXPLANATION_GENERATED = "EXPLANATION_GENERATED"
