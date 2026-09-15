import { useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { bids as bidsApi, documents as docsApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { DocStatusPill, ErrorBanner, Loading, Spinner } from '@/components/Primitives'
import { DOCUMENT_LABEL } from '@/lib/labels'
import { DOCUMENT_TYPES } from '@/api/types'
import type { BidDocument, DocumentType, RequiredDocument } from '@/api/types'
import { formatBytes } from '@/lib/format'
import { messageFor } from '@/api/errors'
import './submission.css'

const MAX_BYTES = 10 * 1024 * 1024

export default function Submission() {
  const { id } = useParams()
  const bidId = Number(id)
  const nav = useNavigate()
  const bid = useAsync(() => bidsApi.get(bidId), [bidId])
  const [submitError, setSubmitError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)

  const required: RequiredDocument[] = useMemo(() => {
    const declared = bid.data?.tender?.required_documents
    if (declared && declared.length) return declared
    return DOCUMENT_TYPES.map((t) => ({
      document_type: t, label: DOCUMENT_LABEL[t], mandatory: true,
    }))
  }, [bid.data])

  const byType = useMemo(() => {
    const m = new Map<DocumentType, BidDocument>()
    for (const d of bid.data?.documents ?? []) {
      if (d.status === 'SUPERSEDED') continue
      const prev = m.get(d.document_type)
      if (!prev || d.version > prev.version) m.set(d.document_type, d)
    }
    return m
  }, [bid.data])

  if (bid.loading && bid.initial) return <Loading />
  if (bid.error != null) {
    return <div className="page"><ErrorBanner error={bid.error} onRetry={bid.reload} /></div>
  }
  if (!bid.data) return null

  const editable = bid.data.status === 'DRAFT'
  const missing = required.filter(
    (r) => r.mandatory && !byType.has(r.document_type),
  )

  async function submit() {
    setSubmitting(true)
    setSubmitError(null)
    try {
      await bidsApi.submit(bidId)
      nav(`/bidder/bids/${bidId}`)
    } catch (e) {
      setSubmitError(e)
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <Link to={`/bidder/bids/${bidId}`} className="small back-link">← Back to bid</Link>

      <div className="page-header" style={{ marginTop: 'var(--s2)' }}>
        <h1>Upload documents</h1>
        <p className="small muted">
          {bid.data.tender_number} · {bid.data.tender_title}
        </p>
      </div>

      {!editable && (
        <div className="banner banner-warn" style={{ marginBottom: 'var(--s4)' }}>
          This bid has already been submitted and can no longer be changed.
        </div>
      )}

      <div className="upload-progress card">
        <div className="between">
          <div>
            <span className="eyebrow">Progress</span>
            <div className="strong tnum">
              {byType.size} of {required.length} documents uploaded
            </div>
          </div>
          {missing.length > 0 ? (
            <span className="small muted">
              {missing.length} mandatory document{missing.length === 1 ? '' : 's'} still needed
            </span>
          ) : (
            <span className="small" style={{ color: 'var(--verified)' }}>
              All mandatory documents present
            </span>
          )}
        </div>
        <div className="upload-bar" aria-hidden>
          <span style={{ width: `${(byType.size / required.length) * 100}%` }} />
        </div>
      </div>

      <div className="slot-grid">
        {required.map((r) => (
          <UploadSlot
            key={r.document_type}
            bidId={bidId}
            required={r}
            doc={byType.get(r.document_type) ?? null}
            editable={editable}
            onChanged={bid.reload}
          />
        ))}
      </div>

      {submitError != null && (
        <div className="banner banner-error" style={{ marginTop: 'var(--s4)' }}>
          {messageFor(submitError)}
        </div>
      )}

      {editable && (
        <div className="submit-bar card">
          <div className="grow">
            <div className="strong">Submit for verification</div>
            <p className="small muted">
              Once submitted the bid is locked and the twelve documents are
              checked against the registries and against one another.
            </p>
          </div>
          <button
            className="btn btn-primary btn-lg"
            onClick={submit}
            disabled={submitting || missing.length > 0}
          >
            {submitting ? 'Submitting…' : 'Submit bid'}
          </button>
        </div>
      )}
    </div>
  )
}

function UploadSlot({
  bidId, required, doc, editable, onChanged,
}: {
  bidId: number
  required: RequiredDocument
  doc: BidDocument | null
  editable: boolean
  onChanged: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [drag, setDrag] = useState(false)

  async function upload(file: File) {
    // Check locally first so an obvious mistake does not cost a round trip.
    // The server still checks magic bytes, which is what actually decides.
    if (file.size > MAX_BYTES) {
      setError('File exceeds the 10 MB limit')
      return
    }
    setBusy(true)
    setError(null)
    try {
      if (doc && !editable) await docsApi.resubmit(doc.id, file)
      else await docsApi.upload(bidId, required.document_type, file)
      onChanged()
    } catch (e) {
      setError(messageFor(e))
    } finally {
      setBusy(false)
    }
  }

  const canAct = editable || (doc !== null && doc.status === 'CLARIFICATION_REQUIRED')

  return (
    <div
      className={`slot${doc ? ' filled' : ''}${drag ? ' dragging' : ''}`}
      onDragOver={(e) => { if (canAct) { e.preventDefault(); setDrag(true) } }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        const f = e.dataTransfer.files?.[0]
        if (f && canAct) void upload(f)
      }}
    >
      <div className="slot-head">
        <span className="slot-label">{required.label || DOCUMENT_LABEL[required.document_type]}</span>
        {required.mandatory && <span className="slot-required">Required</span>}
      </div>

      {doc ? (
        <div className="slot-file">
          <span className="slot-file-name truncate" title={doc.original_filename}>
            {doc.original_filename}
          </span>
          <span className="small muted tnum">{formatBytes(doc.size_bytes)}</span>
          <DocStatusPill status={doc.status} size="sm" />
        </div>
      ) : (
        <p className="small muted slot-hint">PDF, up to 10 MB</p>
      )}

      {error && <p className="small slot-error">{error}</p>}

      {canAct && (
        <div className="slot-actions">
          <input
            ref={input}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void upload(f)
              e.target.value = ''
            }}
          />
          <button
            className="btn btn-sm"
            onClick={() => input.current?.click()}
            disabled={busy}
          >
            {busy ? <Spinner /> : doc ? 'Replace' : 'Choose file'}
          </button>
        </div>
      )}
    </div>
  )
}
