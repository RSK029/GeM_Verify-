import type {
  BidDocument, DocumentVerification, DocumentType,
} from '@/api/types'
import { DOCUMENT_TYPES } from '@/api/types'
import { DocStatusPill } from '@/components/Primitives'
import { DOCUMENT_LABEL } from '@/lib/labels'
import './checklist.css'

export interface ChecklistRow {
  type: DocumentType
  doc: BidDocument | null
  verification: DocumentVerification | null
  failed: number
  review: number
}

export function buildChecklist(
  docs: BidDocument[],
  verification: DocumentVerification[] | undefined,
): ChecklistRow[] {
  // A resubmitted document supersedes the old row; show the live one.
  const live = new Map<DocumentType, BidDocument>()
  for (const d of docs) {
    if (d.status === 'SUPERSEDED') continue
    const prev = live.get(d.document_type)
    if (!prev || d.version > prev.version) live.set(d.document_type, d)
  }

  return DOCUMENT_TYPES.map((type) => {
    const doc = live.get(type) ?? null
    const v = verification?.find((x) => x.document_id === doc?.id) ?? null
    const results = v?.results ?? []
    return {
      type,
      doc,
      verification: v,
      failed: results.filter((r) => r.result === 'FAIL').length,
      review: results.filter((r) => r.result === 'REVIEW').length,
    }
  })
}

/**
 * The twelve required documents, always all twelve — a missing one is a
 * finding in itself, so the row stays visible with a "Not supplied" state
 * rather than disappearing from the list.
 */
export function DocumentChecklist({
  rows, selectedId, onSelect,
}: {
  rows: ChecklistRow[]
  selectedId: number | null
  onSelect: (doc: BidDocument) => void
}) {
  return (
    <ul className="checklist">
      {rows.map((row) => {
        const attention = row.failed > 0 || row.review > 0
        const selected = row.doc !== null && row.doc.id === selectedId
        return (
          <li key={row.type}>
            <button
              className={`checklist-row${selected ? ' selected' : ''}`}
              onClick={() => row.doc && onSelect(row.doc)}
              disabled={!row.doc}
              aria-current={selected}
            >
              <span className={`check-mark ${markTone(row)}`} aria-hidden>
                {markGlyph(row)}
              </span>

              <span className="check-identity">
                <span className="check-label truncate">{DOCUMENT_LABEL[row.type]}</span>
                <span className="check-sub truncate">
                  {row.doc
                    ? row.doc.original_filename
                    : <span className="muted">Not supplied</span>}
                  {row.doc && row.doc.version > 1 && (
                    <span className="version-tag">v{row.doc.version}</span>
                  )}
                </span>
              </span>

              {attention ? (
                <span className={`check-count ${row.failed ? 'bad' : 'warn'}`}>
                  {row.failed + row.review}
                </span>
              ) : row.doc ? (
                <DocStatusPill status={row.doc.status} size="sm" />
              ) : null}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

function markTone(row: ChecklistRow) {
  if (!row.doc) return 'mark-missing'
  if (row.failed > 0) return 'mark-bad'
  if (row.review > 0) return 'mark-warn'
  if (row.doc.status === 'VERIFIED') return 'mark-ok'
  return 'mark-neutral'
}

function markGlyph(row: ChecklistRow) {
  if (!row.doc) return '−'
  if (row.failed > 0) return '✕'
  if (row.review > 0) return '!'
  if (row.doc.status === 'VERIFIED') return '✓'
  return '·'
}
