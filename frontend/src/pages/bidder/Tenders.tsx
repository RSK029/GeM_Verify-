import { useNavigate } from 'react-router-dom'
import { tenders as tendersApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { EmptyState, ErrorBanner, Loading, Pill } from '@/components/Primitives'
import { formatCurrency, formatDate, daysUntil } from '@/lib/format'

export default function Tenders() {
  const nav = useNavigate()
  const list = useAsync(() => tendersApi.list(), [])

  return (
    <div className="page">
      <div className="page-header">
        <h1>Available tenders</h1>
        <p className="small muted">Open invitations you can bid against.</p>
      </div>

      <div className="card">
        <div className="card-body flush">
          {list.loading && list.initial && <Loading />}
          {list.error != null && (
            <div style={{ padding: 'var(--s4)' }}>
              <ErrorBanner error={list.error} onRetry={list.reload} />
            </div>
          )}
          {list.data?.length === 0 && (
            <EmptyState title="No tenders are open" hint="Check back later." />
          )}
          {list.data && list.data.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th>Tender</th>
                  <th style={{ width: 240 }}>Department</th>
                  <th style={{ width: 110 }} className="num">Value</th>
                  <th style={{ width: 96 }} className="num">Documents</th>
                  <th style={{ width: 170 }}>Closing</th>
                  <th style={{ width: 90 }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {list.data.map((t) => {
                  const days = daysUntil(t.closing_date)
                  return (
                    <tr key={t.id} className="clickable"
                        onClick={() => nav(`/bidder/tenders/${t.id}`)}>
                      <td>
                        <div className="mono small">{t.tender_number}</div>
                        <div className="strong">{t.title}</div>
                      </td>
                      <td className="small secondary">{t.department}</td>
                      <td className="num tnum">{formatCurrency(t.estimated_value)}</td>
                      <td className="num tnum">{t.required_document_count ?? '—'}</td>
                      <td className="small">
                        {formatDate(t.closing_date)}
                        {days !== null && days >= 0 && (
                          <div className="small muted">in {days} day{days === 1 ? '' : 's'}</div>
                        )}
                      </td>
                      <td>
                        <Pill tone={t.status === 'OPEN' ? 'ok' : 'neutral'} size="sm">
                          {t.status}
                        </Pill>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
