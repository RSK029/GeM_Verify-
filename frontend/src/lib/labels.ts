/** Human copy for the enum values the API switches on. */

import type {
  BidStatus, CheckResult, ConsistencyDimension, ConsistencyVerdict,
  DocumentStatus, DocumentType, ExplanationKind, NotificationType,
} from '@/api/types'

export const DOCUMENT_LABEL: Record<DocumentType, string> = {
  CONTRACT: 'Signed Tender Document',
  AADHAAR: 'Aadhaar of Signatory',
  PAN: 'PAN Card',
  GST_CERTIFICATE: 'GST Certificate',
  UDYAM: 'Udyam Registration',
  INCORPORATION: 'Certificate of Incorporation',
  EPFO_ESIC: 'EPFO / ESIC Proof',
  OEM_AUTHORISATION: 'OEM Authorisation',
  LOCAL_CONTENT: 'Local Content Declaration',
  TURNOVER: 'Turnover Certificate',
  EXPERIENCE: 'Work Experience',
  BANK_MANDATE: 'Bank Mandate',
}

/** Short form for tight columns. */
export const DOCUMENT_SHORT: Record<DocumentType, string> = {
  CONTRACT: 'Contract',
  AADHAAR: 'Aadhaar',
  PAN: 'PAN',
  GST_CERTIFICATE: 'GST',
  UDYAM: 'Udyam',
  INCORPORATION: 'Incorporation',
  EPFO_ESIC: 'EPFO/ESIC',
  OEM_AUTHORISATION: 'OEM',
  LOCAL_CONTENT: 'Local Content',
  TURNOVER: 'Turnover',
  EXPERIENCE: 'Experience',
  BANK_MANDATE: 'Bank',
}

export const BID_STATUS_LABEL: Record<BidStatus, string> = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  PROCESSING: 'Processing',
  VERIFIED: 'Verified',
  MANUAL_REVIEW: 'Manual Review',
  CLARIFICATION_REQUIRED: 'Clarification Required',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  WITHDRAWN: 'Withdrawn',
}

export const DOCUMENT_STATUS_LABEL: Record<DocumentStatus, string> = {
  PENDING: 'Pending',
  PROCESSING: 'Processing',
  VERIFIED: 'Verified',
  FAILED: 'Failed',
  REVIEW: 'Needs Review',
  CLARIFICATION_REQUIRED: 'Clarification Required',
  SUPERSEDED: 'Superseded',
}

export const VERDICT_LABEL: Record<ConsistencyVerdict, string> = {
  CONSISTENT: 'Consistent',
  VARIATION: 'Variation',
  POTENTIAL_INCONSISTENCY: 'Potential Inconsistency',
  INCONSISTENT: 'Inconsistent',
}

/**
 * VARIATION and POTENTIAL_INCONSISTENCY share amber but are different
 * findings, so the copy has to carry the distinction (brief §6).
 */
export const VERDICT_MEANING: Record<ConsistencyVerdict, string> = {
  CONSISTENT: 'Every document agrees on this.',
  VARIATION:
    'A benign difference in how the same value is written — an abbreviation, '
    + 'a dropped corporate suffix, a missing PIN code. Not a discrepancy.',
  POTENTIAL_INCONSISTENCY:
    'Plausibly the same entity, but the difference does not reduce away. '
    + 'A person needs to decide.',
  INCONSISTENT:
    'These values do not correspond. Treat as a substantive finding.',
}

export const DIMENSION_LABEL: Record<ConsistencyDimension, string> = {
  IDENTITY: 'Legal Identity',
  ADDRESS: 'Registered Address',
  PAN: 'PAN',
  REGISTRATION: 'Registration Numbers',
  SIGNATORY: 'Authorised Signatory',
}

export const DIMENSION_BLURB: Record<ConsistencyDimension, string> = {
  IDENTITY: 'Company name as it appears on every document',
  ADDRESS: 'Registered office address across documents',
  PAN: 'PAN as printed, and as embedded in the GSTIN',
  REGISTRATION: 'GSTIN, CIN, Udyam and EPFO numbers',
  SIGNATORY: 'Who signs, and whether they are on the board',
}

export const CHECK_RESULT_LABEL: Record<CheckResult, string> = {
  PASS: 'Pass',
  FAIL: 'Fail',
  REVIEW: 'Review',
  SKIPPED: 'Skipped',
}

export const NOTIFICATION_LABEL: Record<NotificationType, string> = {
  NEW_TENDER: 'New tender',
  CLARIFICATION_REQUIRED: 'Clarification required',
  VERIFICATION_COMPLETED: 'Verification completed',
  BID_STATUS_CHANGED: 'Status changed',
  DOCUMENT_RESUBMITTED: 'Document resubmitted',
}

export const EXPLANATION_LABEL: Record<ExplanationKind, string> = {
  ADMIN_SUMMARY: 'Reviewer summary',
  FLAG_EXPLANATION: 'Finding explanation',
  CLARIFICATION_DRAFT: 'Draft clarification request',
  DECISION_REASONING: 'Decision reasoning',
}

/** `check_type` is a stable uppercase slug; turn it into a readable label. */
const CHECK_TYPE_LABEL: Record<string, string> = {
  PAN_FORMAT: 'PAN format',
  PAN_REGISTRY_MATCH: 'PAN found in registry',
  PAN_NAME_MATCH: 'PAN holder name matches',
  GSTIN_CHECKSUM: 'GSTIN checksum',
  GSTIN_REGISTRY_MATCH: 'GSTIN found in registry',
  GSTIN_PAN_LINKAGE: 'GSTIN embeds the declared PAN',
  AADHAAR_VERHOEFF: 'Aadhaar checksum (Verhoeff)',
  UDYAM_FORMAT: 'Udyam format',
  UDYAM_REGISTRY_MATCH: 'Udyam found in registry',
  CIN_FORMAT: 'CIN format',
  CIN_REGISTRY_MATCH: 'CIN found in registry',
  OEM_REGISTRY_MATCH: 'OEM is a known manufacturer',
  OEM_VALIDITY: 'OEM authorisation is current',
  OEM_COVERAGE: 'OEM covers every line item',
  TURNOVER_THRESHOLD: 'Turnover meets the threshold',
  EXPERIENCE_THRESHOLD: 'Experience meets the threshold',
  LOCAL_CONTENT_THRESHOLD: 'Local content meets the threshold',
  EPFO_STATUS: 'EPFO establishment is active',
  TENDER_REFERENCE_MATCH: 'Tender reference matches',
  // Neutral: this row carries the *reason*, which may report fields that
  // were missed. A label asserting success contradicted its own body.
  EXTRACTION_COMPLETENESS: 'Field extraction',
}

export function checkLabel(slug: string): string {
  return (
    CHECK_TYPE_LABEL[slug] ??
    slug.toLowerCase().replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
  )
}

/**
 * `canonical_source` and flag `documents_involved` may name a DocumentType, a
 * registry, or free text such as "most attested across documents".
 */
export function sourceLabel(source: string | null | undefined): string {
  if (!source) return 'Unknown'
  if (source in DOCUMENT_LABEL) return DOCUMENT_LABEL[source as DocumentType]
  switch (source) {
    case 'PAN_REGISTRY': return 'PAN Registry'
    case 'GST_REGISTRY': return 'GST Registry'
    case 'UDYAM_REGISTRY': return 'Udyam Registry'
    case 'COMPANY_REGISTRY': return 'Company Registry (MCA)'
    case 'EPFO_REGISTRY': return 'EPFO Registry'
    default: return source
  }
}

/** True when the source is a government registry rather than a bid document. */
export function isRegistrySource(source: string | null | undefined): boolean {
  return !!source && /_REGISTRY$/.test(source)
}

/** Field keys inside `extracted_fields` are snake_case and vary by type. */
export function fieldLabel(key: string): string {
  const special: Record<string, string> = {
    pan: 'PAN', gstin: 'GSTIN', cin: 'CIN',
    udyam_number: 'Udyam Number', aadhaar: 'Aadhaar', ifsc: 'IFSC',
    epfo_code: 'EPFO Code', esic_code: 'ESIC Code',
  }
  if (key in special) return special[key]
  return key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
}
