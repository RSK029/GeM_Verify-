import { useState } from 'react'
import { admin } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { EmptyState, ErrorBanner, Loading } from '@/components/Primitives'
import { formatDateTime } from '@/lib/format'

const PAGE = 40

export default function AuditLog() {
  const [offset, setOffset] = useState(0)
  const [bidId, setBidId] = useState('')

  const logs = useAsync(
    () => admin.auditLogs({
      limit: PAGE,
      offset,
      bid_id: bidId ? Number(bidId) : undefined,
    }),
    [offset, bidId],
  )

  const total = logs.data?.total ?? 0

  return (
    <div className="page">
      <div className="page-header">
        <h1>Audit log</h1>
        <p className="small muted">
          Every read and every decision is recorded, including each time an
          administrator opened a bidder's document.
        </p>
      </div>

      <div className="card">
        <div className="toolbar">
          <input
            className="input"
            style={{ maxWidth: 180 }}
            placeholder="Filter by bid ID…"
            value={bidId}
            inputMode="numeric"
            onChange={(e) => {
              setBidId(e.target.value.replace(/\D/g, ''))
              setOffset(0)
            }}
          />
          <span className="grow" />
          <span className="small muted tnum">{total} entries</span>
        </div>

        <div className="card-body flush">
          {logs.loading && logs.initial && <Loading />}
          {logs.error != null && (
            <div style={{ padding: 'var(--s4)' }}>
              <ErrorBanner error={logs.error} onRetry={logs.reload} />
            </div>
          )}
          {logs.data && logs.data.items.length === 0 && (
            <EmptyState title="No entries" hint="Nothing has been recorded for this filter." />
          )}
          {logs.data && logs.data.items.length > 0 && (
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 160 }}>When</th>
                  <th style={{ width: 210 }}>Action</th>
                  <th style={{ width: 170 }}>By</th>
                  <th>Detail</th>
                  <th style={{ width: 70 }} className="num">Bid</th>
                </tr>
              </thead>
              <tbody>
                {logs.data.items.map((l) => (
                  <tr key={l.id}>
                    <td className="small muted tnum">{formatDateTime(l.created_at)}</td>
                    <td><code className="audit-action">{l.action}</code></td>
                    <td className="small">{l.user_name}</td>
                    <td className="small secondary">{l.details}</td>
                    <td className="num small tnum">{l.bid_id ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {total > PAGE && (
          <div className="toolbar" style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }}>
            <button className="btn btn-sm" disabled={offset === 0}
                    onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
              Previous
            </button>
            <span className="small muted tnum">
              {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
            </span>
            <button className="btn btn-sm" disabled={offset + PAGE >= total}
                    onClick={() => setOffset((o) => o + PAGE)}>
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
