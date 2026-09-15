/**
 * Severity, tone and ordering.
 *
 * The rule from the brief (§6) that shapes this whole file: scores are weak
 * signal. They cluster at 97-100 and the worst bid in the seed set scores
 * 100.0 on every metric. So nothing here ranks or colours by score. Status and
 * findings decide; the number is only ever a detail.
 */

import type {
  BidStatus, BidSummary, CheckResult, ConsistencyVerdict, DocumentStatus,
} from '@/api/types'

export type Tone = 'ok' | 'warn' | 'bad' | 'busy' | 'neutral'

export const STATUS_TONE: Record<BidStatus, Tone> = {
  DRAFT: 'neutral',
  SUBMITTED: 'busy',
  PROCESSING: 'busy',
  VERIFIED: 'ok',
  MANUAL_REVIEW: 'warn',
  CLARIFICATION_REQUIRED: 'warn',
  APPROVED: 'ok',
  REJECTED: 'bad',
  WITHDRAWN: 'neutral',
}

export const DOC_STATUS_TONE: Record<DocumentStatus, Tone> = {
  PENDING: 'neutral',
  PROCESSING: 'busy',
  VERIFIED: 'ok',
  FAILED: 'bad',
  REVIEW: 'warn',
  CLARIFICATION_REQUIRED: 'warn',
  SUPERSEDED: 'neutral',
}

export const VERDICT_TONE: Record<ConsistencyVerdict, Tone> = {
  CONSISTENT: 'ok',
  VARIATION: 'warn',
  POTENTIAL_INCONSISTENCY: 'warn',
  INCONSISTENT: 'bad',
}

export const CHECK_TONE: Record<CheckResult, Tone> = {
  PASS: 'ok',
  FAIL: 'bad',
  REVIEW: 'warn',
  SKIPPED: 'neutral',
}

/** How serious a verdict is, for ranking findings within a bid. */
export const VERDICT_WEIGHT: Record<ConsistencyVerdict, number> = {
  INCONSISTENT: 3,
  POTENTIAL_INCONSISTENCY: 2,
  VARIATION: 1,
  CONSISTENT: 0,
}

/**
 * Queue order. Lower sorts first. Anything a person must act on comes before
 * anything already settled, whatever the scores involved.
 */
const STATUS_RANK: Record<BidStatus, number> = {
  CLARIFICATION_REQUIRED: 0,
  MANUAL_REVIEW: 1,
  PROCESSING: 2,
  SUBMITTED: 3,
  VERIFIED: 4,
  APPROVED: 5,
  REJECTED: 6,
  DRAFT: 7,
  WITHDRAWN: 8,
}

export function needsAttention(bid: BidSummary): boolean {
  return (
    bid.status === 'MANUAL_REVIEW' ||
    bid.status === 'CLARIFICATION_REQUIRED' ||
    bid.documents_flagged > 0
  )
}

/**
 * Sort by status first, then by how much is flagged, and only then by score.
 * Never by score alone — see the note at the top of this file.
 */
export function compareBids(a: BidSummary, b: BidSummary): number {
  const rank = STATUS_RANK[a.status] - STATUS_RANK[b.status]
  if (rank !== 0) return rank

  const flags = b.documents_flagged - a.documents_flagged
  if (flags !== 0) return flags

  const as = a.verification_score ?? 101
  const bs = b.verification_score ?? 101
  if (as !== bs) return as - bs

  return (b.updated_at ?? '').localeCompare(a.updated_at ?? '')
}

export function sortBids(list: BidSummary[]): BidSummary[] {
  return [...list].sort(compareBids)
}

/** The most severe tone in a set, for roll-ups. */
export function worstTone(tones: Tone[]): Tone {
  const order: Tone[] = ['neutral', 'busy', 'ok', 'warn', 'bad']
  return tones.reduce<Tone>(
    (acc, t) => (order.indexOf(t) > order.indexOf(acc) ? t : acc),
    'ok',
  )
}
