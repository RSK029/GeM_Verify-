import type { BidDocument, VerificationResult } from '@/api/types'
import { CheckPill, EmptyState, FieldRow } from '@/components/Primitives'
import { checkLabel, fieldLabel, DOCUMENT_LABEL } from '@/lib/labels'
import { formatBytes, formatConfidence, formatDateTime } from '@/lib/format'
import './evidence.css'

/**
 * What the machine read, and what it concluded — sitting beside the page it
 * read it from. Checks that need attention come first; a reviewer should not
 * have to hunt past ten passes to find the one REVIEW.
 */
export function EvidencePanel({
  doc, results, loading,
}: {
  doc: BidDocument | null
  results: VerificationResult[]
  loading?: boolean
}) {
  if (!doc) {
    return <EmptyState title="No document selected" hint="Pick one from the checklist." />
  }

  const ordered = [...results].sort((a, b) => rank(a) - rank(b))
  const attention = ordered.filter((r) => r.result === 'FAIL' || r.result === 'REVIEW')
  const fields = Object.entries(doc.extracted_fields ?? {})

  return (
    <div className="evidence">
      <div className="evidence-section">
        <div className="evidence-head">
          <h3>{DOCUMENT_LABEL[doc.document_type]}</h3>
          <span className="small muted">
            {formatBytes(doc.size_bytes)} · uploaded {formatDateTime(doc.uploaded_at)}
            {doc.version > 1 && ` · version ${doc.version}`}
          </span>
        </div>
      </div>

      {doc.extraction_error && (
        <div className="evidence-section">
          {/* A field we could not parse is a gap on our side, not a defect in
              the document, and every other check on it still ran. Calling this
              "Extraction failed" in red overstated it — the document was read,
              some fields were not. */}
          <div className="banner banner-warn">
            <div>
              <div className="strong">Some fields could not be read</div>
              <div className="small">{doc.extraction_error}</div>
              <div className="small muted">
                Every other check on this document still ran.
              </div>
            </div>
          </div>
        </div>
      )}

      {attention.length > 0 && (
        <div className="evidence-section">
          <span className="eyebrow">Needs attention</span>
          <div className="check-cards">
            {attention.map((r) => <CheckCard key={r.id} r={r} highlight />)}
          </div>
        </div>
      )}

      <div className="evidence-section">
        <span className="eyebrow">Extracted fields</span>
        {fields.length === 0 ? (
          <p className="small muted" style={{ marginTop: 6 }}>
            Nothing was extracted from this document.
          </p>
        ) : (
          <div className="evidence-fields">
            {fields.map(([k, v]) => (
              <FieldRow key={k} label={fieldLabel(k)} value={v} mono />
            ))}
          </div>
        )}
      </div>

      <div className="evidence-section">
        <span className="eyebrow">
          All checks {results.length > 0 && `(${results.length})`}
        </span>
        {loading && <p className="small muted" style={{ marginTop: 6 }}>Loading checks…</p>}
        {!loading && ordered.length === 0 && (
          <p className="small muted" style={{ marginTop: 6 }}>
            No checks have run against this document yet.
          </p>
        )}
        <div className="check-cards">
          {ordered
            .filter((r) => r.result !== 'FAIL' && r.result !== 'REVIEW')
            .map((r) => <CheckCard key={r.id} r={r} />)}
        </div>
      </div>
    </div>
  )
}

function CheckCard({ r, highlight }: { r: VerificationResult; highlight?: boolean }) {
  const compare =
    r.submitted_value !== null &&
    r.registry_value !== null &&
    r.submitted_value !== r.registry_value

  return (
    <div className={`check-card${highlight ? ' check-card-attention' : ''}`}>
      <div className="check-card-head">
        <span className="check-card-name">{checkLabel(r.check_type)}</span>
        <CheckPill result={r.result} size="sm" />
      </div>

      {r.reason && <p className="check-card-reason">{r.reason}</p>}

      {compare && (
        <div className="check-compare">
          <div>
            <span className="eyebrow">On the document</span>
            <div className="mono check-compare-value">{r.submitted_value}</div>
          </div>
          <div>
            <span className="eyebrow">On record</span>
            <div className="mono check-compare-value">{r.registry_value}</div>
          </div>
        </div>
      )}

      {!compare && r.submitted_value && (
        <div className="mono check-single">{r.submitted_value}</div>
      )}

      {r.confidence !== null && r.confidence < 1 && (
        <div className="check-confidence">
          <span className="small muted">Match confidence</span>
          <span className="tnum small strong">{formatConfidence(r.confidence)}</span>
        </div>
      )}
    </div>
  )
}

function rank(r: VerificationResult): number {
  return { FAIL: 0, REVIEW: 1, PASS: 2, SKIPPED: 3 }[r.result] ?? 4
}
