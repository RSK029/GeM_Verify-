/** Formatting helpers. */

/**
 * The contract promises ISO-8601 UTC with a Z ("2026-09-15T10:32:04Z"), but the
 * server sends naive local-looking strings ("2026-09-15T12:25:23.842600").
 * `new Date()` reads those as LOCAL time, which shifts every timestamp by the
 * viewer's offset. Append Z when no designator is present so they are read as
 * UTC, which is what the backend actually means. See HANDOVER.md.
 */
export function parseApiDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  const d = new Date(hasZone ? value : `${value}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

const DATE_TIME: Intl.DateTimeFormatOptions = {
  day: '2-digit', month: 'short', year: 'numeric',
  hour: '2-digit', minute: '2-digit', hour12: false,
}
const DATE_ONLY: Intl.DateTimeFormatOptions = {
  day: '2-digit', month: 'short', year: 'numeric',
}

export function formatDateTime(value: string | null | undefined): string {
  const d = parseApiDate(value)
  return d ? new Intl.DateTimeFormat('en-IN', DATE_TIME).format(d) : '—'
}

export function formatDate(value: string | null | undefined): string {
  const d = parseApiDate(value)
  return d ? new Intl.DateTimeFormat('en-IN', DATE_ONLY).format(d) : '—'
}

export function formatRelative(value: string | null | undefined): string {
  const d = parseApiDate(value)
  if (!d) return '—'
  const secs = Math.round((Date.now() - d.getTime()) / 1000)
  if (secs < 45) return 'just now'
  const mins = Math.round(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.round(hrs / 24)
  if (days < 7) return `${days}d ago`
  return formatDate(value)
}

/** Days until a date; negative once past. */
export function daysUntil(value: string | null | undefined): number | null {
  const d = parseApiDate(value)
  if (!d) return null
  return Math.ceil((d.getTime() - Date.now()) / 86_400_000)
}

/** Money is an integer number of rupees. Indian grouping. */
export function formatCurrency(rupees: number | null | undefined): string {
  if (rupees === null || rupees === undefined) return '—'
  if (rupees >= 10_000_000)
    return `₹${(rupees / 10_000_000).toFixed(2).replace(/\.00$/, '')} Cr`
  if (rupees >= 100_000)
    return `₹${(rupees / 100_000).toFixed(2).replace(/\.00$/, '')} L`
  return `₹${new Intl.NumberFormat('en-IN').format(rupees)}`
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** One decimal place, or an em dash. Scores are never invented. */
export function formatScore(score: number | null | undefined): string {
  return score === null || score === undefined ? '—' : score.toFixed(1)
}

export function formatPercent(score: number | null | undefined): string {
  return score === null || score === undefined ? '—' : `${score.toFixed(1)}%`
}

export function formatConfidence(c: number | null | undefined): string {
  return c === null || c === undefined ? '—' : `${Math.round(c * 100)}%`
}

export function initials(name: string | null | undefined): string {
  if (!name) return '?'
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('')
}
