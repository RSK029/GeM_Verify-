# GeMVerify — API Contract v1

**Status: FROZEN.** Both the backend and the frontend build against this document.
Changes require a version bump and a note in the changelog at the bottom.

Base URL: `http://localhost:8000`
All paths below are prefixed with `/api`.

---

## Conventions

- All request and response bodies are `application/json`, except document upload
  (`multipart/form-data`) and document download (`application/pdf`).
- Timestamps are ISO-8601 UTC strings: `"2026-09-15T10:32:04Z"`.
- Money is an integer number of rupees. The UI formats it.
- IDs are integers.
- Authentication is a signed JWT carried in an **httpOnly cookie** named `gv_session`.
  The frontend never reads the token; it sends `credentials: "include"` on every request.
- Errors use this envelope, with the appropriate HTTP status:

```json
{ "detail": "Human readable message", "code": "MACHINE_CODE" }
```

Common codes: `INVALID_CREDENTIALS`, `NOT_AUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`,
`VALIDATION_ERROR`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`, `DUPLICATE_EMAIL`,
`BID_NOT_EDITABLE`, `MISSING_REQUIRED_DOCUMENTS`.

---

## Enumerations

These strings are exact. The frontend switches on them.

```
Role                    BIDDER | ADMIN

BidStatus               DRAFT | SUBMITTED | PROCESSING | VERIFIED |
                        MANUAL_REVIEW | CLARIFICATION_REQUIRED |
                        APPROVED | REJECTED

DocumentStatus          PENDING | PROCESSING | VERIFIED | FAILED |
                        REVIEW | CLARIFICATION_REQUIRED | SUPERSEDED

CheckResult             PASS | FAIL | REVIEW | SKIPPED

ConsistencyVerdict      CONSISTENT | VARIATION |
                        POTENTIAL_INCONSISTENCY | INCONSISTENT

ConsistencyDimension    IDENTITY | ADDRESS | REGISTRATION | PAN | SIGNATORY

NotificationType        NEW_TENDER | CLARIFICATION_REQUIRED |
                        VERIFICATION_COMPLETED | BID_STATUS_CHANGED |
                        DOCUMENT_RESUBMITTED

DocumentType            CONTRACT | AADHAAR | PAN | GST_CERTIFICATE | UDYAM |
                        INCORPORATION | EPFO_ESIC | OEM_AUTHORISATION |
                        LOCAL_CONTENT | TURNOVER | EXPERIENCE | BANK_MANDATE
```

`DocumentType` values map to specimen filenames as
`CONTRACT → contract`, `GST_CERTIFICATE → gst-certificate`,
`OEM_AUTHORISATION → oem-authorisation`, etc. (upper snake ↔ lower kebab).

---

## Core object shapes

### User
```json
{
  "id": 3,
  "name": "Rajesh Kumar Sharma",
  "email": "rajesh@abcindustrial.example",
  "role": "BIDDER",
  "company_name": "ABC Industrial Systems Private Limited",
  "created_at": "2026-09-01T06:00:00Z"
}
```

### Tender
```json
{
  "id": 1,
  "tender_number": "GEM/2026/B/4471902",
  "title": "CPCL Industrial Equipment Procurement - 2026",
  "department": "Chennai Petroleum Corporation Limited",
  "description": "Supply of centrifugal process pumps, LT motor control centres...",
  "estimated_value": 48000000,
  "closing_date": "2026-09-28T23:59:59Z",
  "status": "OPEN",
  "required_documents": [
    { "document_type": "CONTRACT", "label": "Signed Tender Document", "mandatory": true },
    { "document_type": "AADHAAR",  "label": "Aadhaar of Authorised Signatory", "mandatory": true }
  ],
  "created_at": "2026-09-01T06:00:00Z"
}
```

`GET /tenders` returns tenders **without** `required_documents` and `description`.
`GET /tenders/{id}` returns the full object above.

### BidSummary — used in all list views
```json
{
  "id": 12,
  "tender_id": 1,
  "tender_number": "GEM/2026/B/4471902",
  "tender_title": "CPCL Industrial Equipment Procurement - 2026",
  "bidder_id": 3,
  "bidder_company": "ABC Industrial Systems Private Limited",
  "status": "MANUAL_REVIEW",
  "verification_score": 93.5,
  "document_count": 12,
  "documents_verified": 11,
  "documents_flagged": 1,
  "submitted_at": "2026-09-15T10:12:00Z",
  "updated_at": "2026-09-15T10:13:40Z"
}
```

`verification_score` is `null` until verification completes. It is a float 0–100.

### Document
```json
{
  "id": 140,
  "bid_id": 12,
  "document_type": "UDYAM",
  "original_filename": "d1-udyam.pdf",
  "size_bytes": 8421,
  "status": "REVIEW",
  "version": 1,
  "supersedes_id": null,
  "uploaded_at": "2026-09-15T10:11:20Z",
  "extracted_fields": {
    "enterprise_name": "ABC Industrial Systems Private Limited",
    "udyam_number": "UDYAM-TN-02-0012345",
    "pan": "AAACA1111C",
    "gstin": "33AAACA1111C1ZV",
    "address": "Plot 14, SIDCO Industrial Estate, Ambattur, Chennai, Tamil Nadu - 600098"
  }
}
```

`extracted_fields` is a flat object of string values; keys vary by `document_type`
and may be absent before processing. The UI renders it generically.

### VerificationResult — one deterministic check
```json
{
  "id": 901,
  "document_id": 140,
  "check_type": "UDYAM_FORMAT",
  "result": "PASS",
  "submitted_value": "UDYAM-TN-02-0012345",
  "registry_value": "UDYAM-TN-02-0012345",
  "confidence": 1.0,
  "reason": "format OK; matches registry record",
  "created_at": "2026-09-15T10:12:30Z"
}
```

`check_type` is a stable uppercase slug. The set in v1:
`PAN_FORMAT`, `PAN_REGISTRY_MATCH`, `PAN_NAME_MATCH`, `GSTIN_CHECKSUM`,
`GSTIN_REGISTRY_MATCH`, `GSTIN_PAN_LINKAGE`, `AADHAAR_VERHOEFF`, `UDYAM_FORMAT`,
`UDYAM_REGISTRY_MATCH`, `CIN_FORMAT`, `CIN_REGISTRY_MATCH`, `OEM_REGISTRY_MATCH`,
`OEM_VALIDITY`, `OEM_COVERAGE`, `TURNOVER_THRESHOLD`, `EXPERIENCE_THRESHOLD`,
`LOCAL_CONTENT_THRESHOLD`, `EPFO_STATUS`, `TENDER_REFERENCE_MATCH`,
`EXTRACTION_COMPLETENESS`.

### ConsistencyReport — the cross-document layer
```json
{
  "bid_id": 12,
  "overall_score": 93.5,
  "document_score": 100.0,
  "consistency_score": 87.0,
  "dimensions": [
    {
      "dimension": "IDENTITY",
      "score": 86.0,
      "verdict": "VARIATION",
      "canonical_value": "ABC Industrial Systems Private Limited",
      "canonical_source": "PAN",
      "observations": [
        {
          "document_type": "UDYAM",
          "document_id": 140,
          "value": "ABC Industrial Systems",
          "similarity": 0.82,
          "verdict": "VARIATION",
          "reason": "token subset of canonical value; corporate suffix omitted"
        }
      ]
    }
  ],
  "flags": [
    {
      "id": "IDENTITY-UDYAM-140",
      "dimension": "IDENTITY",
      "verdict": "VARIATION",
      "title": "Enterprise name on Udyam certificate differs from legal name",
      "documents_involved": ["PAN", "UDYAM"],
      "values": { "PAN": "ABC Industrial Systems Private Limited", "UDYAM": "ABC Industrial Systems" }
    }
  ],
  "computed_at": "2026-09-15T10:13:40Z"
}
```

`dimensions` always contains all five `ConsistencyDimension` values; a dimension
with nothing to compare has `score: null` and `verdict: "CONSISTENT"`.

### AiExplanation — generated, cacheable, never authoritative
```json
{
  "bid_id": 12,
  "kind": "ADMIN_SUMMARY",
  "text": "All twelve documents passed their individual checks...",
  "model": "qwen2.5:7b-instruct",
  "generated_at": "2026-09-15T10:14:10Z",
  "is_fallback": false
}
```

`kind` is `ADMIN_SUMMARY | FLAG_EXPLANATION | CLARIFICATION_DRAFT | DECISION_REASONING`.
`is_fallback: true` means Ollama was unavailable and templated text was used —
the UI must still render it, labelled the same way.

### Notification
```json
{
  "id": 55,
  "user_id": 3,
  "bid_id": 12,
  "type": "CLARIFICATION_REQUIRED",
  "title": "Clarification required on your Udyam Certificate",
  "message": "The enterprise name differs from the legal name on your PAN record.",
  "read": false,
  "created_at": "2026-09-15T10:20:00Z"
}
```

### AuditLog
```json
{
  "id": 320,
  "user_id": 2,
  "user_name": "Procurement Admin",
  "action": "ADMIN_VIEWED_DOCUMENT",
  "bid_id": 12,
  "document_id": 140,
  "details": "Viewed UDYAM (d1-udyam.pdf)",
  "created_at": "2026-09-15T10:18:02Z"
}
```

---

## Endpoints

### Auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/register` | — | Bidder self-registration only. Admins are seed-only. |
| POST | `/auth/login` | — | Sets the `gv_session` cookie. Role comes from the DB. |
| POST | `/auth/logout` | any | Clears the cookie. |
| GET | `/auth/me` | any | Current user, or 401. Frontend calls this on boot. |

`POST /auth/register`
```json
{ "name": "...", "email": "...", "password": "...", "company_name": "..." }
```
→ `201` with `User`. `409 DUPLICATE_EMAIL` if taken.

`POST /auth/login`
```json
{ "email": "...", "password": "..." }
```
→ `200` with `User`. `401 INVALID_CREDENTIALS` otherwise. The response body carries
the role; the frontend routes on `user.role`. There is no role selector at login.

### Tenders

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/tenders` | any | `?status=OPEN` optional. Returns `Tender[]` (list shape). |
| GET | `/tenders/{id}` | any | Full `Tender` including `required_documents`. |

### Bids — bidder

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/bids` | BIDDER | `{ "tender_id": 1 }` → creates a `DRAFT` bid. 1 draft per tender per bidder. |
| GET | `/bids` | BIDDER | Own bids only. `?status=` optional. Returns `BidSummary[]`. |
| GET | `/bids/{id}` | owner/ADMIN | `BidDetail` = `BidSummary` + `documents: Document[]` + `tender: Tender`. |
| POST | `/bids/{id}/submit` | owner | Validates mandatory documents present, sets `PROCESSING`, queues verification. |
| DELETE | `/bids/{id}` | owner | Only while `DRAFT`. |

`POST /bids/{id}/submit` → `202` with `BidSummary` (status `PROCESSING`).
`400 MISSING_REQUIRED_DOCUMENTS` with `detail` naming the missing types.

### Documents

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/bids/{id}/documents` | owner | `multipart/form-data`: `document_type` (string), `file` (PDF). Replaces any existing document of that type on a `DRAFT` bid. |
| GET | `/documents/{id}` | owner/ADMIN | Streams `application/pdf`. Logged in the audit trail. |
| GET | `/documents/{id}/meta` | owner/ADMIN | `Document` object. |
| GET | `/documents/{id}/verification` | owner/ADMIN | `VerificationResult[]` for that document. |
| POST | `/documents/{id}/resubmit` | owner | `multipart/form-data` with `file`. Creates a **new** document row with `version + 1` and `supersedes_id` set; the old row becomes `SUPERSEDED`. Re-runs verification for the bid. |

Upload limits: 10 MB per file, `application/pdf` only, verified by magic bytes,
not by the client-supplied content type or extension.

### Verification — read side

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/bids/{id}/verification` | owner/ADMIN | `{ "documents": [{ "document_id": n, "document_type": "...", "status": "...", "results": VerificationResult[] }] }` |
| GET | `/bids/{id}/consistency` | owner/ADMIN | `ConsistencyReport`. `404` until verification has run. |
| GET | `/bids/{id}/explanation?kind=ADMIN_SUMMARY` | owner/ADMIN | `AiExplanation`. Bidders may only request `CLARIFICATION_DRAFT` and `DECISION_REASONING`. |
| POST | `/bids/{id}/explanation/regenerate` | ADMIN | `{ "kind": "ADMIN_SUMMARY" }` → `202`. |

### Notifications

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/notifications` | any | Own only. `?unread_only=true`. Returns `{ "items": Notification[], "unread_count": n }`. |
| POST | `/notifications/{id}/read` | owner | → `204`. |
| POST | `/notifications/read-all` | any | → `204`. |

### Admin

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/admin/overview` | ADMIN | Counts + recent activity, shape below. |
| GET | `/admin/bids` | ADMIN | All bids. `?status=&tender_id=&q=` — `q` matches company or tender number. |
| POST | `/admin/bids/{id}/approve` | ADMIN | `{ "note": "..." }` → `BidSummary`. Notifies the bidder. |
| POST | `/admin/bids/{id}/reject` | ADMIN | `{ "reason": "..." }` → `BidSummary`. Notifies the bidder. |
| POST | `/admin/bids/{id}/clarification` | ADMIN | `{ "document_ids": [140], "message": "..." }` → `BidSummary`. Sets those documents to `CLARIFICATION_REQUIRED` and the bid to `CLARIFICATION_REQUIRED`, notifies the bidder. |
| GET | `/admin/audit-logs` | ADMIN | `?bid_id=&user_id=&limit=&offset=`. Returns `{ "items": AuditLog[], "total": n }`. |

`GET /admin/overview`
```json
{
  "total_bids": 18,
  "by_status": { "PROCESSING": 1, "VERIFIED": 9, "MANUAL_REVIEW": 5, "REJECTED": 2, "APPROVED": 1 },
  "recent_submissions": [ /* BidSummary[] */ ],
  "attention_required": [ /* BidSummary[] where status is MANUAL_REVIEW */ ],
  "pending_clarifications": [ /* BidSummary[] where status is CLARIFICATION_REQUIRED */ ]
}
```

### Bidder dashboard

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/dashboard` | BIDDER | Overview cards for the bidder portal. |

```json
{
  "active_bids": 3,
  "pending_verification": 1,
  "clarification_required": 1,
  "verified_bids": 1,
  "recent_bids": [ /* BidSummary[] */ ],
  "recent_notifications": [ /* Notification[] */ ],
  "action_required": [ /* BidSummary[] needing bidder action */ ],
  "open_tenders": [ /* Tender[] (list shape) */ ]
}
```

---

## Polling

The frontend polls these while a bid is `PROCESSING` and on dashboard screens:

- `GET /api/notifications?unread_only=true` every 8s
- `GET /api/dashboard` or `GET /api/admin/overview` every 10s
- `GET /api/bids/{id}` every 3s while status is `PROCESSING`, stopping once it is not

No WebSockets in v1.

---

## Changelog

- **v1** (2026-09-15) — initial frozen contract.
