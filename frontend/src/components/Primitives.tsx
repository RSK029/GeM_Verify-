import type { ReactNode } from 'react'
import type {
  BidStatus, CheckResult, ConsistencyVerdict, DocumentStatus,
} from '@/api/types'
import {
  BID_STATUS_LABEL, CHECK_RESULT_LABEL, DOCUMENT_STATUS_LABEL, VERDICT_LABEL,
} from '@/lib/labels'
import {
  CHECK_TONE, DOC_STATUS_TONE, STATUS_TONE, VERDICT_TONE,
} from '@/lib/severity'
import type { Tone } from '@/lib/severity'
import { messageFor } from '@/api/errors'
import { formatScore } from '@/lib/format'
import './primitives.css'

/* ------------------------------------------------------------------ pill */

export function Pill({
  tone, children, dot = true, size = 'md',
}: {
  tone: Tone
  children: ReactNode
  dot?: boolean
  size?: 'sm' | 'md'
}) {
  return (
    <span className={`pill pill-${tone} ${size === 'sm' ? 'pill-sm' : ''}`}>
      {dot && <i className="pill-dot" aria-hidden />}
      {children}
    </span>
  )
}

export function BidStatusPill({ status, size }: { status: BidStatus; size?: 'sm' | 'md' }) {
  return (
    <Pill tone={STATUS_TONE[status]} size={size}>
      {BID_STATUS_LABEL[status]}
    </Pill>
  )
}

export function DocStatusPill({ status, size }: { status: DocumentStatus; size?: 'sm' | 'md' }) {
  return (
    <Pill tone={DOC_STATUS_TONE[status]} size={size}>
      {DOCUMENT_STATUS_LABEL[status]}
    </Pill>
  )
}

export function VerdictPill({ verdict, size }: { verdict: ConsistencyVerdict; size?: 'sm' | 'md' }) {
  return (
    <Pill tone={VERDICT_TONE[verdict]} size={size}>
      {VERDICT_LABEL[verdict]}
    </Pill>
  )
}

export function CheckPill({ result, size }: { result: CheckResult; size?: 'sm' | 'md' }) {
  return (
    <Pill tone={CHECK_TONE[result]} size={size} dot={false}>
      {CHECK_RESULT_LABEL[result]}
    </Pill>
  )
}

/* --------------------------------------------------------------- metrics */

/**
 * A score, deliberately understated. Never the largest thing on a card and
 * never coloured by value — a 100.0 can be the worst bid in the set.
 */
export function ScoreValue({
  score, label, suffix = '%',
}: {
  score: number | null | undefined
  label?: string
  suffix?: string
}) {
  return (
    <span className="score-value">
      {label && <span className="score-label">{label}</span>}
      <span className="tnum score-number">
        {formatScore(score)}
        {score !== null && score !== undefined && (
          <span className="score-suffix">{suffix}</span>
        )}
      </span>
    </span>
  )
}

export function StatCard({
  label, value, tone = 'neutral', hint, onClick,
}: {
  label: string
  value: ReactNode
  tone?: Tone
  hint?: ReactNode
  onClick?: () => void
}) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag
      className={`stat-card card stat-${tone}${onClick ? ' stat-clickable' : ''}`}
      onClick={onClick}
      type={onClick ? 'button' : undefined}
    >
      <span className="stat-label">{label}</span>
      <span className="stat-value tnum">{value}</span>
      {hint && <span className="stat-hint">{hint}</span>}
    </Tag>
  )
}

/* ---------------------------------------------------------------- states */

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="row gap2" role="status">
      <span className="spinner" />
      {label && <span className="small muted">{label}</span>}
    </span>
  )
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="empty">
      <div className="row gap2" style={{ justifyContent: 'center' }}>
        <span className="spinner" />
        <span>{label}</span>
      </div>
    </div>
  )
}

export function EmptyState({
  title, hint, action,
}: {
  title: string
  hint?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="empty">
      <div className="strong" style={{ color: 'var(--text-secondary)' }}>{title}</div>
      {hint && <div className="small" style={{ marginTop: 4 }}>{hint}</div>}
      {action && <div style={{ marginTop: 'var(--s3)' }}>{action}</div>}
    </div>
  )
}

export function ErrorBanner({
  error, onRetry,
}: {
  error: unknown
  onRetry?: () => void
}) {
  if (!error) return null
  return (
    <div className="banner banner-error">
      <div className="grow">{messageFor(error)}</div>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>Retry</button>
      )}
    </div>
  )
}

/* ------------------------------------------------------------ data pairs */

export function FieldRow({
  label, value, mono, title,
}: {
  label: string
  value: ReactNode
  mono?: boolean
  title?: string
}) {
  return (
    <div className="field-row">
      <span className="field-row-label">{label}</span>
      <span className={`field-row-value${mono ? ' mono' : ''}`} title={title}>
        {value ?? <span className="muted">—</span>}
      </span>
    </div>
  )
}

export function SectionTitle({
  children, hint, action,
}: {
  children: ReactNode
  hint?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="between section-title">
      <div>
        <h2>{children}</h2>
        {hint && <div className="small muted" style={{ marginTop: 2 }}>{hint}</div>}
      </div>
      {action}
    </div>
  )
}
