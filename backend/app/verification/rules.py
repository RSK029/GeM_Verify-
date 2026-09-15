"""Deterministic per-document checks.

Every verdict produced here comes from arithmetic or an exact comparison: a
Verhoeff digit, a mod-36 check character, a regex, a threshold, a registry
lookup. No language model participates. ``ABCDE1234F != XYZAB9999Q`` is a string
comparison and asking a model to make it would be a liability, not a feature.

Each check writes one ``VerificationResult`` row carrying the submitted value,
the registry value and a human-readable reason, so the admin UI can show the
evidence beside the document rather than a bare verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    CheckResult,
    ConsistencyVerdict,
    Document,
    DocumentStatus,
    DocumentType,
    VerificationResult,
)
from . import normalize
from .registry import RegistryGateway
from .validators import (
    validate_aadhaar,
    validate_cin,
    validate_gstin,
    validate_pan,
    validate_udyam,
)


@dataclass
class Check:
    check_type: str
    result: str
    reason: str
    submitted_value: str | None = None
    registry_value: str | None = None
    confidence: float = 1.0


def _ok(check_type: str, reason: str, submitted=None, registry=None) -> Check:
    return Check(check_type, CheckResult.PASS.value, reason, submitted, registry)


def _fail(check_type: str, reason: str, submitted=None, registry=None) -> Check:
    return Check(check_type, CheckResult.FAIL.value, reason, submitted, registry)


def _review(check_type: str, reason: str, submitted=None, registry=None, confidence=0.5) -> Check:
    return Check(check_type, CheckResult.REVIEW.value, reason, submitted, registry, confidence)


def _skip(check_type: str, reason: str) -> Check:
    return Check(check_type, CheckResult.SKIPPED.value, reason, confidence=0.0)


def _name_result(comparison) -> str:
    """How a name comparison scores as a *per-document* check.

    A VARIATION is a benign difference — an omitted corporate suffix, an
    initial. The document itself is fine, so it passes here; the difference is
    still reported by the consistency layer, which is where a reader can see it
    against the other eleven documents. Only a comparison that is genuinely
    ambiguous or wrong escalates this document to REVIEW.
    """
    clean = (
        ConsistencyVerdict.CONSISTENT.value,
        ConsistencyVerdict.VARIATION.value,
    )
    return CheckResult.PASS.value if comparison.verdict in clean else CheckResult.REVIEW.value


def _number(value: str | None) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# individual checks
# --------------------------------------------------------------------------


def _check_pan(fields: dict, gw: RegistryGateway) -> list[Check]:
    pan = fields.get("pan")
    if not pan:
        return [_skip("PAN_FORMAT", "no PAN found in this document")]

    checks: list[Check] = []
    # Deliberately no expected holder type. A company, an LLP, a partnership
    # firm and a trust can all bid, and each carries a different fourth
    # character. Failing a valid LLP's PAN for not being a company's would be
    # rejecting the entity type, not verifying the document.
    valid, detail = validate_pan(pan)
    checks.append((_ok if valid else _fail)("PAN_FORMAT", detail, pan))

    record = gw.pan(pan)
    if not record.found:
        checks.append(
            _fail("PAN_REGISTRY_MATCH", "PAN is not present in the Income Tax registry", pan)
        )
        return checks
    checks.append(
        _ok("PAN_REGISTRY_MATCH", "PAN found in registry", pan, record.get("pan"))
    )

    submitted_name = fields.get("company_name")
    if submitted_name:
        comparison = normalize.compare_names(submitted_name, record.get("name"))
        # A name difference escalates to a human; it is never an auto-rejection.
        checks.append(
            Check(
                "PAN_NAME_MATCH",
                _name_result(comparison),
                comparison.reason,
                submitted_name,
                record.get("name"),
                comparison.similarity,
            )
        )
    return checks


def _check_gst(fields: dict, gw: RegistryGateway) -> list[Check]:
    gstin = fields.get("gstin")
    if not gstin:
        return [_skip("GSTIN_CHECKSUM", "no GSTIN found in this document")]

    checks: list[Check] = []
    valid, detail = validate_gstin(gstin)
    checks.append((_ok if valid else _fail)("GSTIN_CHECKSUM", detail, gstin))

    record = gw.gstin(gstin)
    if not record.found:
        checks.append(
            _fail("GSTIN_REGISTRY_MATCH", "GSTIN is not present in the GST registry", gstin)
        )
    else:
        checks.append(
            _ok("GSTIN_REGISTRY_MATCH", "GSTIN found in registry", gstin, record.get("gstin"))
        )
        name = fields.get("company_name")
        if name:
            comparison = normalize.compare_names(name, record.get("legal_name"))
            checks.append(
                Check(
                    "GST_NAME_MATCH",
                    _name_result(comparison),
                    comparison.reason,
                    name,
                    record.get("legal_name"),
                    comparison.similarity,
                )
            )

    # Note: whether the GSTIN embeds the PAN shown on the PAN card is a
    # *relational* fact spanning two documents, not a property of this one. It
    # is checked in app.verification.consistency via linkage.pan_matches_gstin.
    # Asserting it here would let a single-document pass fail for a reason the
    # document cannot be responsible for.
    return checks


def _check_aadhaar(fields: dict, gw: RegistryGateway) -> list[Check]:
    _ = gw  # UIDAI is deliberately not queried; Verhoeff is a local check.
    number = fields.get("aadhaar_number")
    if not number:
        return [_skip("AADHAAR_VERHOEFF", "no Aadhaar number found in this document")]
    valid, detail = validate_aadhaar(number)
    masked = f"XXXX XXXX {normalize.normalize_identifier(number)[-4:]}"
    return [(_ok if valid else _fail)("AADHAAR_VERHOEFF", detail, masked)]


def _check_udyam(fields: dict, gw: RegistryGateway) -> list[Check]:
    number = fields.get("udyam_number")
    if not number:
        return [_skip("UDYAM_FORMAT", "no Udyam number found in this document")]

    checks: list[Check] = []
    valid, detail = validate_udyam(number)
    checks.append((_ok if valid else _fail)("UDYAM_FORMAT", detail, number))

    record = gw.udyam(number)
    if not record.found:
        checks.append(
            _fail("UDYAM_REGISTRY_MATCH", "Udyam number is not present in the registry", number)
        )
        return checks
    checks.append(
        _ok("UDYAM_REGISTRY_MATCH", "Udyam registration found", number, record.get("udyam_number"))
    )

    name = fields.get("company_name")
    if name:
        comparison = normalize.compare_names(name, record.get("business_name"))
        checks.append(
            Check(
                "UDYAM_NAME_MATCH",
                _name_result(comparison),
                comparison.reason,
                name,
                record.get("business_name"),
                comparison.similarity,
            )
        )
    return checks


def _check_incorporation(fields: dict, gw: RegistryGateway) -> list[Check]:
    cin = fields.get("cin")
    if not cin:
        return [_skip("CIN_FORMAT", "no CIN found in this document")]

    checks: list[Check] = []
    valid, detail = validate_cin(cin)
    checks.append((_ok if valid else _fail)("CIN_FORMAT", detail, cin))

    record = gw.company(cin)
    if not record.found:
        checks.append(_fail("CIN_REGISTRY_MATCH", "CIN is not present in the MCA registry", cin))
        return checks
    checks.append(_ok("CIN_REGISTRY_MATCH", "Company found in registry", cin, record.get("cin")))

    name = fields.get("company_name")
    if name:
        comparison = normalize.compare_names(name, record.get("company_name"))
        checks.append(
            Check(
                "COMPANY_NAME_MATCH",
                _name_result(comparison),
                comparison.reason,
                name,
                record.get("company_name"),
                comparison.similarity,
            )
        )
    return checks


def _check_oem(fields: dict, gw: RegistryGateway, tender_number: str) -> list[Check]:
    checks: list[Check] = []
    pan = fields.get("pan")
    record = gw.oem_for_dealer(pan or "", tender_number)

    if not record.found:
        checks.append(
            _fail(
                "OEM_REGISTRY_MATCH",
                "No OEM authorisation is recorded for this bidder against this tender",
                pan,
            )
        )
    else:
        checks.append(
            _ok(
                "OEM_REGISTRY_MATCH",
                f"Authorisation {record.get('authorization_id')} on record",
                fields.get("oem_name"),
                record.get("oem_name"),
            )
        )
        valid_until = record.get("valid_until")
        if isinstance(valid_until, datetime):
            expired = valid_until < datetime.now(timezone.utc).replace(tzinfo=None)
            checks.append(
                (_fail if expired else _ok)(
                    "OEM_VALIDITY",
                    ("authorisation expired on " if expired else "authorisation valid until ")
                    + valid_until.strftime("%d/%m/%Y"),
                    registry=valid_until.strftime("%d/%m/%Y"),
                )
            )

    covers = fields.get("covers_all_items")
    excluded = fields.get("items_excluded")
    if not covers:
        checks.append(
            _skip("OEM_COVERAGE", "the letter does not enumerate the items it covers")
        )
    elif covers == "YES":
        checks.append(
            _ok("OEM_COVERAGE", "authorisation covers all tender line items without exclusion")
        )
    elif covers == "NO":
        checks.append(
            _fail(
                "OEM_COVERAGE",
                f"authorisation excludes {excluded or 'one or more'} tender line item(s)",
                covers,
            )
        )
    return checks


def _check_threshold(
    fields: dict,
    *,
    check_type: str,
    field: str,
    minimum: float,
    unit: str,
) -> list[Check]:
    value = _number(fields.get(field))
    if value is None:
        return [_skip(check_type, f"{field.replace('_', ' ')} could not be read")]
    submitted = f"{value:g} {unit}".strip()
    required = f"{minimum:g} {unit}".strip()
    if value >= minimum:
        return [_ok(check_type, f"{submitted} meets the minimum of {required}", submitted, required)]
    return [
        _fail(check_type, f"{submitted} is below the minimum of {required}", submitted, required)
    ]


def _check_epfo(fields: dict, gw: RegistryGateway) -> list[Check]:
    code = fields.get("establishment_code")
    status = (fields.get("epfo_status") or "").upper()
    if not code:
        return [_skip("EPFO_STATUS", "no establishment code found in this document")]

    record = gw.epfo(code)
    registry_status = (record.get("status") or "").upper() if record.found else None
    if not record.found:
        return [_fail("EPFO_STATUS", "establishment is not present in the EPFO registry", code)]
    if registry_status != "ACTIVE":
        return [
            _fail(
                "EPFO_STATUS",
                f"establishment coverage is {registry_status.title()}",
                status,
                registry_status,
            )
        ]
    if status and status != "ACTIVE":
        return [
            _review(
                "EPFO_STATUS",
                f"document states {status.title()} but the registry shows Active",
                status,
                registry_status,
            )
        ]
    return [_ok("EPFO_STATUS", "establishment coverage is Active", status or "ACTIVE", registry_status)]


def _check_tender_reference(fields: dict, tender_number: str) -> list[Check]:
    quoted = fields.get("tender_number")
    if not quoted:
        return [_skip("TENDER_REFERENCE_MATCH", "document does not quote a tender reference")]
    if normalize.normalize_identifier(quoted) == normalize.normalize_identifier(tender_number):
        return [
            _ok("TENDER_REFERENCE_MATCH", "document quotes this tender", quoted, tender_number)
        ]
    return [
        _fail(
            "TENDER_REFERENCE_MATCH",
            "document quotes a different tender reference",
            quoted,
            tender_number,
        )
    ]


# --------------------------------------------------------------------------
# orchestration per document
# --------------------------------------------------------------------------

_REGISTRY_CHECKS = {
    DocumentType.PAN: _check_pan,
    DocumentType.GST_CERTIFICATE: _check_gst,
    DocumentType.AADHAAR: _check_aadhaar,
    DocumentType.UDYAM: _check_udyam,
    DocumentType.INCORPORATION: _check_incorporation,
}


def checks_for(document: Document, gw: RegistryGateway, tender_number: str) -> list[Check]:
    doc_type = DocumentType(document.document_type)
    fields = document.extracted_fields or {}

    # A field we could not read is a gap in *our* parser, not a fault in the
    # document — and it must never stop us checking everything we did read.
    # Returning early here meant one unreadable tender reference silently
    # cancelled the PAN format check, the GSTIN checksum and every registry
    # lookup, so a document with one small gap reported nothing at all.
    if document.extraction_error:
        checks: list[Check] = [
            _review("EXTRACTION_COMPLETENESS", document.extraction_error, confidence=0.0)
        ]
    else:
        checks = [
            _ok("EXTRACTION_COMPLETENESS", "all expected fields were read from this document")
        ]

    handler = _REGISTRY_CHECKS.get(doc_type)
    if handler:
        checks.extend(handler(fields, gw))

    if doc_type is DocumentType.OEM_AUTHORISATION:
        checks.extend(_check_oem(fields, gw, tender_number))
    elif doc_type is DocumentType.TURNOVER:
        checks.extend(
            _check_threshold(
                fields,
                check_type="TURNOVER_THRESHOLD",
                field="turnover_cr",
                minimum=settings.MIN_TURNOVER_CR,
                unit="crore",
            )
        )
    elif doc_type is DocumentType.EXPERIENCE:
        checks.extend(
            _check_threshold(
                fields,
                check_type="EXPERIENCE_THRESHOLD",
                field="experience_years",
                minimum=settings.MIN_EXPERIENCE_YEARS,
                unit="years",
            )
        )
    elif doc_type is DocumentType.LOCAL_CONTENT:
        checks.extend(
            _check_threshold(
                fields,
                check_type="LOCAL_CONTENT_THRESHOLD",
                field="local_content_pct",
                minimum=settings.MIN_LOCAL_CONTENT_PCT,
                unit="%",
            )
        )
    elif doc_type is DocumentType.EPFO_ESIC:
        checks.extend(_check_epfo(fields, gw))

    if fields.get("tender_number"):
        checks.extend(_check_tender_reference(fields, tender_number))

    return checks


def status_for(checks: list[Check]) -> str:
    results = {c.result for c in checks}
    if CheckResult.FAIL.value in results:
        return DocumentStatus.FAILED.value
    if CheckResult.REVIEW.value in results:
        return DocumentStatus.REVIEW.value
    return DocumentStatus.VERIFIED.value


def apply(db: Session, document: Document, gw: RegistryGateway, tender_number: str) -> list[Check]:
    """Run every check for a document and persist the results."""
    for stale in list(document.results):
        db.delete(stale)
    db.flush()

    checks = checks_for(document, gw, tender_number)
    for check in checks:
        db.add(
            VerificationResult(
                document_id=document.id,
                check_type=check.check_type,
                result=check.result,
                submitted_value=check.submitted_value,
                registry_value=check.registry_value,
                confidence=check.confidence,
                reason=check.reason,
            )
        )
    document.status = status_for(checks)
    db.flush()
    return checks


def score(checks: list[Check]) -> float:
    """PASS = 1, REVIEW = 0.5, FAIL = 0. Skipped checks do not count."""
    scored = [c for c in checks if c.result != CheckResult.SKIPPED.value]
    if not scored:
        return 100.0
    weights = {CheckResult.PASS.value: 1.0, CheckResult.REVIEW.value: 0.5, CheckResult.FAIL.value: 0.0}
    return round(100.0 * sum(weights[c.result] for c in scored) / len(scored), 1)
