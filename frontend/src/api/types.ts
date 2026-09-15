/**
 * Transcribed from docs/API_CONTRACT.md v1.
 *
 * Fields marked OBSERVED are returned by the live backend but are not in the
 * contract. They are typed optional so the UI degrades if they disappear.
 * See HANDOVER.md.
 */

// ---------------------------------------------------------------- enums

export type Role = 'BIDDER' | 'ADMIN'

export type BidStatus =
  | 'DRAFT' | 'SUBMITTED' | 'PROCESSING' | 'VERIFIED'
  | 'MANUAL_REVIEW' | 'CLARIFICATION_REQUIRED' | 'APPROVED' | 'REJECTED'
  | 'WITHDRAWN'

export type DocumentStatus =
  | 'PENDING' | 'PROCESSING' | 'VERIFIED' | 'FAILED'
  | 'REVIEW' | 'CLARIFICATION_REQUIRED' | 'SUPERSEDED'

export type CheckResult = 'PASS' | 'FAIL' | 'REVIEW' | 'SKIPPED'

export type ConsistencyVerdict =
  | 'CONSISTENT' | 'VARIATION' | 'POTENTIAL_INCONSISTENCY' | 'INCONSISTENT'

export type ConsistencyDimension =
  | 'IDENTITY' | 'ADDRESS' | 'REGISTRATION' | 'PAN' | 'SIGNATORY'

export type NotificationType =
  | 'NEW_TENDER' | 'CLARIFICATION_REQUIRED' | 'VERIFICATION_COMPLETED'
  | 'BID_STATUS_CHANGED' | 'DOCUMENT_RESUBMITTED'

export type DocumentType =
  | 'CONTRACT' | 'AADHAAR' | 'PAN' | 'GST_CERTIFICATE' | 'UDYAM'
  | 'INCORPORATION' | 'EPFO_ESIC' | 'OEM_AUTHORISATION' | 'LOCAL_CONTENT'
  | 'TURNOVER' | 'EXPERIENCE' | 'BANK_MANDATE'

export type ExplanationKind =
  | 'ADMIN_SUMMARY' | 'FLAG_EXPLANATION'
  | 'CLARIFICATION_DRAFT' | 'DECISION_REASONING'

export const DOCUMENT_TYPES: DocumentType[] = [
  'CONTRACT', 'AADHAAR', 'PAN', 'GST_CERTIFICATE', 'UDYAM', 'INCORPORATION',
  'EPFO_ESIC', 'OEM_AUTHORISATION', 'LOCAL_CONTENT', 'TURNOVER',
  'EXPERIENCE', 'BANK_MANDATE',
]

export const CONSISTENCY_DIMENSIONS: ConsistencyDimension[] = [
  'IDENTITY', 'ADDRESS', 'PAN', 'REGISTRATION', 'SIGNATORY',
]

// ---------------------------------------------------------------- objects

export interface User {
  id: number
  name: string
  email: string
  role: Role
  company_name: string | null
  created_at: string
}

export interface RequiredDocument {
  document_type: DocumentType
  label: string
  mandatory: boolean
}

export interface Tender {
  id: number
  tender_number: string
  title: string
  department: string
  estimated_value: number
  closing_date: string
  status: string
  created_at: string
  /** Full object only (GET /tenders/{id}). */
  description?: string
  required_documents?: RequiredDocument[]
  /** OBSERVED — present on both list and detail shapes. */
  required_document_count?: number
}

export interface BidSummary {
  id: number
  tender_id: number
  tender_number: string
  tender_title: string
  bidder_id: number
  bidder_company: string
  status: BidStatus
  /** null until verification completes. */
  verification_score: number | null
  document_count: number
  documents_verified: number
  documents_flagged: number
  submitted_at: string | null
  updated_at: string
}

export interface BidDocument {
  id: number
  bid_id: number
  document_type: DocumentType
  original_filename: string
  size_bytes: number
  status: DocumentStatus
  version: number
  supersedes_id: number | null
  uploaded_at: string
  extracted_fields: Record<string, string> | null
  /** OBSERVED — set when extraction failed for this document. */
  extraction_error?: string | null
}

export interface BidDetail extends BidSummary {
  tender: Tender
  documents: BidDocument[]
  /** OBSERVED — populated after approve/reject. */
  decision_note?: string | null
}

export interface VerificationResult {
  id: number
  document_id: number
  check_type: string
  result: CheckResult
  submitted_value: string | null
  registry_value: string | null
  confidence: number | null
  reason: string | null
  created_at: string
}

export interface DocumentVerification {
  document_id: number
  document_type: DocumentType
  status: DocumentStatus
  results: VerificationResult[]
}

export interface BidVerification {
  documents: DocumentVerification[]
}

export interface ConsistencyObservation {
  document_type: DocumentType
  document_id: number
  value: string | null
  similarity: number | null
  verdict: ConsistencyVerdict
  reason: string | null
}

export interface ConsistencyDimensionReport {
  dimension: ConsistencyDimension
  /** null means nothing to compare — render "Not applicable", never 0%. */
  score: number | null
  verdict: ConsistencyVerdict
  canonical_value: string | null
  /**
   * Where the truth came from. A DocumentType, a registry name
   * (PAN_REGISTRY / GST_REGISTRY), or free text such as
   * "most attested across documents".
   */
  canonical_source: string | null
  observations: ConsistencyObservation[]
}

export interface ConsistencyFlag {
  id: string
  dimension: ConsistencyDimension | string
  verdict: ConsistencyVerdict
  title: string
  /**
   * May name registries as well as documents, and may repeat the same entry
   * (the GSTIN/PAN linkage flags report ['CONTRACT','CONTRACT']).
   */
  documents_involved: string[]
  /**
   * Keys are NOT always DocumentType. The linkage flags use descriptive keys
   * such as "PAN embedded in GSTIN". Render generically.
   */
  values: Record<string, string>
}

export interface ConsistencyReport {
  bid_id: number
  overall_score: number | null
  document_score: number | null
  consistency_score: number | null
  dimensions: ConsistencyDimensionReport[]
  flags: ConsistencyFlag[]
  computed_at: string
}

export interface AiExplanation {
  bid_id: number
  kind: ExplanationKind
  text: string
  /** null when the model was unavailable and templated text was used. */
  model: string | null
  generated_at: string
  is_fallback: boolean
}

export interface AppNotification {
  id: number
  user_id: number
  bid_id: number | null
  type: NotificationType
  title: string
  message: string
  read: boolean
  created_at: string
}

export interface NotificationList {
  items: AppNotification[]
  unread_count: number
}

export interface AuditLog {
  id: number
  user_id: number
  user_name: string
  action: string
  bid_id: number | null
  document_id: number | null
  details: string
  created_at: string
}

export interface AuditLogPage {
  items: AuditLog[]
  total: number
}

export interface AdminOverview {
  total_bids: number
  by_status: Partial<Record<BidStatus, number>>
  recent_submissions: BidSummary[]
  attention_required: BidSummary[]
  pending_clarifications: BidSummary[]
}

export interface BidderDashboard {
  active_bids: number
  pending_verification: number
  clarification_required: number
  verified_bids: number
  recent_bids: BidSummary[]
  recent_notifications: AppNotification[]
  action_required: BidSummary[]
  open_tenders: Tender[]
}

/** OBSERVED — GET /ai/status, not in the contract. */
export interface AiStatus {
  ready: boolean
  detail: string | null
}
