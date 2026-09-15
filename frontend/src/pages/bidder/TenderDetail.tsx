import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { bids as bidsApi, tenders as tendersApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { ErrorBanner, Loading, Pill } from '@/components/Primitives'
import { formatCurrency, formatDate, daysUntil } from '@/lib/format'
import { DOCUMENT_LABEL } from '@/lib/labels'
import { messageFor } from '@/api/errors'

export default function TenderDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const tender = useAsync(() => tendersApi.get(Number(id)), [id])
  const myBids = useAsync(() => bidsApi.listMine(), [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  if (tender.loading && tender.initial) return <Loading />
  if (tender.error != null) {
    return <div className="page"><ErrorBanner error={tender.error} onRetry={tender.reload} /></div>
  }
  if (!tender.data) return null
  const t = tender.data

  const existing = myBids.data?.find((b) => b.tender_id === t.id)
  const days = daysUntil(t.closing_date)

  async function startBid() {
    setBusy(true)
    setError(null)
    try {
      const bid = await bidsApi.create(t.id)
      nav(`/bidder/bids/${bid.id}/documents`)
    } catch (e) {
      setError(e)
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <Link to="/bidder/tenders" className="small back-link">← Available tenders</Link>

      <div className="page-header" style={{ marginTop: 'var(--s2)' }}>
        <div className="mono small muted">{t.tender_number}</div>
        <h1>{t.title}</h1>
        <p className="small muted">{t.department}</p>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 'var(--s5)' }}>
        <div className="card card-body">
          <span className="eyebrow">Estimated value</span>
          <div className="tnum" style={{ fontSize: 20, fontWeight: 600 }}>
            {formatCurrency(t.estimated_value)}
          </div>
        </div>
        <div className="card card-body">
          <span className="eyebrow">Closing date</span>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{formatDate(t.closing_date)}</div>
          {days !== null && days >= 0 && (
            <span className="small muted">in {days} day{days === 1 ? '' : 's'}</span>
          )}
        </div>
        <div className="card card-body">
          <span className="eyebrow">Status</span>
          <div style={{ marginTop: 4 }}>
            <Pill tone={t.status === 'OPEN' ? 'ok' : 'neutral'}>{t.status}</Pill>
          </div>
        </div>
      </div>

      {t.description && (
        <div className="card" style={{ marginBottom: 'var(--s5)' }}>
          <div className="card-header"><h2>Scope</h2></div>
          <div className="card-body"><p className="secondary">{t.description}</p></div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 'var(--s5)' }}>
        <div className="card-header">
          <h2>Required documents</h2>
          <span className="small muted tnum">
            {t.required_documents?.length ?? t.required_document_count ?? 0} required
          </span>
        </div>
        <div className="card-body">
          <div className="req-grid">
            {(t.required_documents ?? []).map((r) => (
              <div key={r.document_type} className="req-item">
                <span className="req-dot" aria-hidden />
                <div>
                  <div className="small strong">{r.label || DOCUMENT_LABEL[r.document_type]}</div>
                  <div className="small muted">
                    {r.mandatory ? 'Mandatory' : 'Optional'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {error != null && (
        <div className="banner banner-error" style={{ marginBottom: 'var(--s3)' }}>
          {messageFor(error)}
        </div>
      )}

      {existing ? (
        <div className="banner banner-info">
          <div className="grow">
            You already have a bid against this tender.
          </div>
          <Link className="btn btn-sm" to={`/bidder/bids/${existing.id}`}>Open it</Link>
        </div>
      ) : (
        <button className="btn btn-primary btn-lg" onClick={startBid} disabled={busy}>
          {busy ? 'Creating…' : 'Start a bid'}
        </button>
      )}
    </div>
  )
}
