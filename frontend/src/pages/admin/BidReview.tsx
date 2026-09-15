import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { admin, bids as bidsApi, documents as docsApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { usePolling } from '@/hooks/usePolling'
import { IntelligencePanel } from '@/features/consistency/IntelligencePanel'
import {
  DocumentChecklist, buildChecklist,
} from '@/features/documents/DocumentChecklist'
import { PdfViewer } from '@/features/documents/PdfViewer'
import { EvidencePanel } from '@/features/documents/EvidencePanel'
import {
  BidStatusPill, ErrorBanner, Loading, Pill, Spinner,
} from '@/components/Primitives'
import { Modal } from '@/components/Modal'
import { formatDateTime, formatPercent } from '@/lib/format'
import { messageFor } from '@/api/errors'
import type { BidDocument, DocumentType } from '@/api/types'
import './bidreview.css'

type ActionKind = 'approve' | 'reject' | 'clarify'

export default function BidReview() {
  const { id } = useParams()
  const bidId = Number(id)

  const bid = useAsync(() => bidsApi.get(bidId), [bidId])
  const verification = useAsync(() => bidsApi.verification(bidId), [bidId])
  const consistency = useAsync(() => bidsApi.consistency(bidId), [bidId])

  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [action, setAction] = useState<ActionKind | null>(null)
  const workspaceRef = useRef<HTMLDivElement>(null)

  const processing = bid.data?.status === 'PROCESSING'
  usePolling(() => {
    void bid.reload()
    void verification.reload()
    void consistency.reload()
  }, 3000, processing)

  const rows = useMemo(
    () => buildChecklist(bid.data?.documents ?? [], verification.data?.documents),
    [bid.data, verification.data],
  )

  // Open on whatever needs a person's attention first, not on document one.
  useEffect(() => {
    if (selectedId !== null || rows.length === 0) return
    const flagged = rows.find((r) => r.failed > 0 || r.review > 0)
    const first = flagged ?? rows.find((r) => r.doc)
    if (first?.doc) setSelectedId(first.doc.id)
  }, [rows, selectedId])

  const selectedDoc =
    rows.find((r) => r.doc?.id === selectedId)?.doc ?? null

  const docChecks = useAsync(
    () => docsApi.verification(selectedId!),
    [selectedId],
    { enabled: selectedId !== null },
  )

  const docByType = (type: string): BidDocument | null =>
    rows.find((r) => r.type === (type as DocumentType))?.doc ?? null

  if (bid.loading && bid.initial) return <Loading label="Opening bid…" />
  if (bid.error != null) {
    return (
      <div className="page">
        <ErrorBanner error={bid.error} onRetry={bid.reload} />
      </div>
    )
  }
  if (!bid.data) return null

  const b = bid.data
  const flagCount = consistency.data?.flags.length ?? 0
  const checkIssues = rows.reduce((n, r) => n + r.failed + r.review, 0)

  return (
    <div className="page page-wide review">
      {/* ---------------------------------------------------- header */}
      <header className="review-head">
        <div className="grow">
          <Link to="/admin/bids" className="small back-link">← All bids</Link>
          <h1 className="review-company">{b.bidder_company}</h1>
          <div className="row gap3 wrap small muted review-meta">
            <span className="mono">{b.tender_number}</span>
            <span>·</span>
            <span>{b.tender_title}</span>
            <span>·</span>
            <span>Submitted {formatDateTime(b.submitted_at)}</span>
          </div>
        </div>

        <div className="review-head-right">
          <BidStatusPill status={b.status} />
          {processing && <Spinner label="Verification running…" />}
        </div>
      </header>

      {/* Attention strip — findings, not scores, decide what this says. */}
      <div className={`review-strip ${flagCount || checkIssues ? 'strip-warn' : 'strip-ok'}`}>
        <div className="row gap4 wrap grow">
          <StripItem
            label="Documents"
            value={`${b.documents_verified} of ${b.document_count} clear`}
            tone={b.documents_flagged > 0 ? 'warn' : 'ok'}
          />
          <StripItem
            label="Per-document checks"
            value={checkIssues === 0 ? 'All passed' : `${checkIssues} need attention`}
            tone={checkIssues > 0 ? 'warn' : 'ok'}
          />
          <StripItem
            label="Cross-document"
            value={flagCount === 0 ? 'No disagreement' : `${flagCount} finding${flagCount > 1 ? 's' : ''}`}
            tone={flagCount > 0 ? 'warn' : 'ok'}
          />
          <StripItem
            label="Overall score"
            value={formatPercent(b.verification_score)}
            tone="neutral"
            muted
          />
        </div>

        {/* A withdrawn bid is out of the competition. The API refuses a
            decision on one, so the controls are disabled rather than left to
            fail on click. */}
        {b.status === 'WITHDRAWN' ? (
          <div className="small muted">
            Withdrawn by the bidder — no decision can be recorded.
          </div>
        ) : (
          <div className="row gap2">
            <button className="btn" onClick={() => setAction('clarify')}
                    disabled={b.status === 'APPROVED' || b.status === 'REJECTED'}>
              Request clarification
            </button>
            <button className="btn btn-danger" onClick={() => setAction('reject')}
                    disabled={b.status === 'REJECTED'}>
              Reject
            </button>
            <button className="btn btn-primary" onClick={() => setAction('approve')}
                    disabled={b.status === 'APPROVED'}>
              Approve
            </button>
          </div>
        )}
      </div>

      {b.decision_note && (
        <div className="banner banner-info review-note">
          <div>
            <span className="strong">Decision note · </span>{b.decision_note}
          </div>
        </div>
      )}

      {/* --------------------------------------- cross-document panel */}
      {consistency.loading && consistency.initial && (
        <div className="card"><Loading label="Comparing documents…" /></div>
      )}
      {consistency.notFound && (
        <div className="banner banner-info">
          Cross-document comparison has not run for this bid yet.
        </div>
      )}
      {consistency.error != null && !consistency.notFound && (
        <ErrorBanner error={consistency.error} onRetry={consistency.reload} />
      )}
      {consistency.data && (
        <IntelligencePanel
          report={consistency.data}
          bidId={bidId}
          bidStatus={b.status}
          canRegenerate
          resolveDocument={docByType}
          onOpenDocument={(doc) => {
            setSelectedId(doc.id)
            workspaceRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }}
        />
      )}

      {/* ---------------------------------------- document workspace */}
      <section className="workspace card" ref={workspaceRef}>
        <div className="workspace-head">
          <h2>Document review</h2>
          <span className="small muted">
            The page as submitted, with what was read from it alongside
          </span>
        </div>

        <div className="workspace-body">
          <aside className="workspace-list">
            <DocumentChecklist
              rows={rows}
              selectedId={selectedId}
              onSelect={(doc) => setSelectedId(doc.id)}
            />
          </aside>

          <div className="workspace-viewer">
            <PdfViewer
              documentId={selectedId}
              filename={selectedDoc?.original_filename}
            />
          </div>

          <aside className="workspace-evidence">
            <EvidencePanel
              doc={selectedDoc}
              results={docChecks.data ?? []}
              loading={docChecks.loading}
            />
          </aside>
        </div>
      </section>

      {action && (
        <ActionDialog
          kind={action}
          bidId={bidId}
          rows={rows}
          onClose={() => setAction(null)}
          onDone={() => {
            setAction(null)
            void bid.reload()
            void verification.reload()
          }}
        />
      )}
    </div>
  )
}

function StripItem({
  label, value, tone, muted,
}: {
  label: string
  value: string
  tone: 'ok' | 'warn' | 'neutral'
  muted?: boolean
}) {
  return (
    <span className={`strip-item strip-${tone}${muted ? ' strip-muted' : ''}`}>
      <span className="strip-label">{label}</span>
      <span className="strip-value tnum">{value}</span>
    </span>
  )
}

/* ------------------------------------------------------------- actions */

function ActionDialog({
  kind, bidId, rows, onClose, onDone,
}: {
  kind: ActionKind
  bidId: number
  rows: ReturnType<typeof buildChecklist>
  onClose: () => void
  onDone: () => void
}) {
  const [text, setText] = useState('')
  const [picked, setPicked] = useState<number[]>(() =>
    rows.filter((r) => r.doc && (r.failed > 0 || r.review > 0)).map((r) => r.doc!.id))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const title = {
    approve: 'Approve this bid',
    reject: 'Reject this bid',
    clarify: 'Request clarification',
  }[kind]

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      if (kind === 'approve') await admin.approve(bidId, text)
      else if (kind === 'reject') await admin.reject(bidId, text)
      else await admin.clarification(bidId, picked, text)
      onDone()
    } catch (e) {
      setError(e)
      setBusy(false)
    }
  }

  const needsText = kind !== 'approve'
  const disabled = busy || (needsText && text.trim().length === 0) ||
    (kind === 'clarify' && picked.length === 0)

  return (
    <Modal
      title={title}
      onClose={onClose}
      width={kind === 'clarify' ? 560 : 460}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button
            className={`btn ${kind === 'reject' ? 'btn-danger' : 'btn-primary'}`}
            onClick={submit}
            disabled={disabled}
          >
            {busy ? 'Working…' : title}
          </button>
        </>
      }
    >
      <div className="stack gap3">
        {kind === 'clarify' && (
          <div className="field">
            <label>Documents to query</label>
            <div className="clarify-list">
              {rows.filter((r) => r.doc).map((r) => (
                <label key={r.type} className="clarify-item">
                  <input
                    type="checkbox"
                    checked={picked.includes(r.doc!.id)}
                    onChange={(e) =>
                      setPicked((p) =>
                        e.target.checked
                          ? [...p, r.doc!.id]
                          : p.filter((x) => x !== r.doc!.id))}
                  />
                  <span className="grow">{r.type.replace(/_/g, ' ')}</span>
                  {(r.failed > 0 || r.review > 0) && (
                    <Pill tone={r.failed ? 'bad' : 'warn'} size="sm" dot={false}>
                      {r.failed + r.review}
                    </Pill>
                  )}
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="field">
          <label htmlFor="action-text">
            {kind === 'approve' ? 'Note (optional)'
              : kind === 'reject' ? 'Reason' : 'Message to the bidder'}
          </label>
          <textarea
            id="action-text"
            className="textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              kind === 'clarify'
                ? 'Explain precisely what the bidder must supply or correct.'
                : kind === 'reject'
                  ? 'This is recorded in the audit trail and sent to the bidder.'
                  : 'Recorded against the decision.'
            }
          />
        </div>

        {error != null && <div className="banner banner-error">{messageFor(error)}</div>}
      </div>
    </Modal>
  )
}
