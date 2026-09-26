import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { bids as bidsApi, documents as docsApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { usePolling } from '@/hooks/usePolling'
import { IntelligencePanel } from '@/features/consistency/IntelligencePanel'
import {
  DocumentChecklist, buildChecklist,
} from '@/features/documents/DocumentChecklist'
import { EvidencePanel } from '@/features/documents/EvidencePanel'
import { AiAssessment } from '@/features/ai/AiAssessment'
import {
  BidStatusPill, ErrorBanner, Loading, Spinner,
} from '@/components/Primitives'
import { formatDateTime } from '@/lib/format'
import type { BidStatus } from '@/api/types'

/** States the bidder may pull a bid back from. Mirrors the API's own rule. */
const WITHDRAWABLE: BidStatus[] = [
  'SUBMITTED', 'PROCESSING', 'VERIFIED', 'MANUAL_REVIEW', 'CLARIFICATION_REQUIRED',
]

/** States the bidder may start again from. */
const REAPPLICABLE: BidStatus[] = ['WITHDRAWN', 'REJECTED']

export default function BidDetail() {
  const { id } = useParams()
  const bidId = Number(id)
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<unknown>(null)

  const bid = useAsync(() => bidsApi.get(bidId), [bidId])
  const verification = useAsync(() => bidsApi.verification(bidId), [bidId])
  const consistency = useAsync(() => bidsApi.consistency(bidId), [bidId])
  const [selectedId, setSelectedId] = useState<number | null>(null)

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

  const selectedDoc = rows.find((r) => r.doc?.id === selectedId)?.doc ?? null
  const docChecks = useAsync(
    () => docsApi.verification(selectedId!),
    [selectedId],
    { enabled: selectedId !== null },
  )

  if (bid.loading && bid.initial) return <Loading />
  if (bid.error != null) {
    return <div className="page"><ErrorBanner error={bid.error} onRetry={bid.reload} /></div>
  }
  if (!bid.data) return null
  const b = bid.data

  const isDraft = b.status === 'DRAFT'
  const needsAction = b.status === 'CLARIFICATION_REQUIRED'
  const canWithdraw = WITHDRAWABLE.includes(b.status)
  const canReapply = REAPPLICABLE.includes(b.status) && b.tender.status === 'OPEN'

  async function onWithdraw() {
    setBusy(true)
    setActionError(null)
    try {
      await bidsApi.withdraw(bidId)
      setConfirming(false)
      await bid.reload()
    } catch (err) {
      setActionError(err)
    } finally {
      setBusy(false)
    }
  }

  async function onReapply() {
    setBusy(true)
    setActionError(null)
    try {
      const fresh = await bidsApi.reapply(bidId)
      // Land on the upload screen of the new draft: the documents were carried
      // over, so the only thing left is to replace what needs replacing.
      navigate(`/bidder/bids/${fresh.id}/documents`)
    } catch (err) {
      setActionError(err)
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <Link to="/bidder/bids" className="small back-link">← My bids</Link>

      <header className="between" style={{ marginTop: 'var(--s2)', marginBottom: 'var(--s4)' }}>
        <div>
          <div className="mono small muted">{b.tender_number}</div>
          <h1>{b.tender_title}</h1>
          <p className="small muted">
            {b.submitted_at
              ? `Submitted ${formatDateTime(b.submitted_at)}`
              : 'Not yet submitted'}
          </p>
        </div>
        <div className="row gap3">
          {processing && <Spinner label="Verifying…" />}
          <BidStatusPill status={b.status} />
          {canWithdraw && !confirming && (
            <button
              className="btn btn-sm"
              onClick={() => { setActionError(null); setConfirming(true) }}
            >
              Withdraw bid
            </button>
          )}
          {canReapply && (
            <button
              className="btn btn-sm btn-primary"
              disabled={busy}
              onClick={onReapply}
            >
              {busy ? 'Starting…' : 'Reapply for this tender'}
            </button>
          )}
        </div>
      </header>

      {actionError != null && (
        <div style={{ marginBottom: 'var(--s4)' }}>
          <ErrorBanner error={actionError} />
        </div>
      )}

      {confirming && (
        <div className="banner banner-warn" style={{ marginBottom: 'var(--s4)' }}>
          <div className="grow">
            <div className="strong">Withdraw this bid?</div>
            <div className="small">
              It leaves the department's queue and can no longer be approved.
              Nothing is deleted — the bid and its documents stay on record, and
              you can reapply for this tender afterwards while it is still open.
            </div>
          </div>
          <div className="row gap2">
            <button
              className="btn btn-sm"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              Keep it
            </button>
            <button
              className="btn btn-sm btn-danger"
              disabled={busy}
              onClick={onWithdraw}
            >
              {busy ? 'Withdrawing…' : 'Yes, withdraw'}
            </button>
          </div>
        </div>
      )}

      {b.status === 'WITHDRAWN' && (
        <div className="banner banner-info" style={{ marginBottom: 'var(--s4)' }}>
          <div className="grow">
            You withdrew this bid. It is kept here for your records and is no
            longer being reviewed.
          </div>
        </div>
      )}

      {isDraft && (
        <div className="banner banner-info" style={{ marginBottom: 'var(--s4)' }}>
          <div className="grow">
            This bid is still a draft. Upload the required documents and submit it.
          </div>
          <Link className="btn btn-sm btn-primary" to={`/bidder/bids/${bidId}/documents`}>
            Continue
          </Link>
        </div>
      )}

      {needsAction && (
        <div className="banner banner-warn" style={{ marginBottom: 'var(--s4)' }}>
          <div className="grow">
            <div className="strong">The department has asked for a clarification</div>
            <div className="small">
              Replace the documents marked below, then the bid is re-checked
              automatically.
            </div>
          </div>
          <Link className="btn btn-sm" to={`/bidder/bids/${bidId}/documents`}>
            Resubmit documents
          </Link>
        </div>
      )}

      {b.decision_note && (
        <div className="banner banner-info" style={{ marginBottom: 'var(--s4)' }}>
          <div><span className="strong">Decision note · </span>{b.decision_note}</div>
        </div>
      )}

      {processing && (
        <div className="banner banner-info" style={{ marginBottom: 'var(--s4)' }}>
          <span className="spinner" />
          <div>
            Your documents are being checked. This page updates on its own.
          </div>
        </div>
      )}

      {/* Bidders get the same evidence the reviewer sees — the point of the
          product is that a finding is explainable, not that it is hidden. */}
      <div className="card" style={{ marginBottom: 'var(--s4)' }}>
        <div className="card-header">
          <h2>Your documents</h2>
          <span className="small muted tnum">
            {b.documents_verified} of {b.document_count} clear
            {b.documents_flagged > 0 && ` · ${b.documents_flagged} flagged`}
          </span>
        </div>
        <div className="bidder-docs">
          <aside className="bidder-docs-list">
            <DocumentChecklist
              rows={rows}
              selectedId={selectedId}
              onSelect={(doc) => setSelectedId(doc.id)}
            />
          </aside>
          <div className="bidder-docs-evidence">
            <EvidencePanel
              doc={selectedDoc}
              results={docChecks.data ?? []}
              loading={docChecks.loading}
            />
          </div>
        </div>
      </div>

      {consistency.data && (
        <div style={{ marginBottom: 'var(--s4)' }}>
          <IntelligencePanel
            report={consistency.data}
            bidId={bidId}
            bidStatus={b.status}
            explanationKind={null}
            showScores={false}
            issuesOnly
          />
        </div>
      )}
      {consistency.notFound && !isDraft && (
        <div className="banner banner-info" style={{ marginBottom: 'var(--s4)' }}>
          Cross-document comparison has not run yet.
        </div>
      )}

      {/* The contract restricts bidders to these two kinds. */}
      {(b.status === 'APPROVED' || b.status === 'REJECTED') && (
        <div style={{ marginBottom: 'var(--s4)' }}>
          <AiAssessment bidId={bidId} kind="DECISION_REASONING" />
        </div>
      )}
      {needsAction && (
        <AiAssessment bidId={bidId} kind="CLARIFICATION_DRAFT" />
      )}
    </div>
  )
}
