import { Link, useNavigate } from 'react-router-dom'
import { dashboard } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { usePolling } from '@/hooks/usePolling'
import { BidTable } from '@/components/BidTable'
import { EmptyState, ErrorBanner, Loading, StatCard } from '@/components/Primitives'
import { formatCurrency, formatRelative, daysUntil } from '@/lib/format'
import { NOTIFICATION_LABEL } from '@/lib/labels'

export default function BidderOverview() {
  const nav = useNavigate()
  const d = useAsync(() => dashboard.bidder(), [])
  usePolling(d.reload, 10_000)

  if (d.loading && d.initial) return <Loading />
  if (d.error != null) {
    return <div className="page"><ErrorBanner error={d.error} onRetry={d.reload} /></div>
  }
  if (!d.data) return null
  const v = d.data

  return (
    <div className="page">
      <div className="page-header">
        <h1>Overview</h1>
        <p className="small muted">Your submissions and anything waiting on you.</p>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 'var(--s5)' }}>
        <StatCard label="Active bids" value={v.active_bids} />
        <StatCard label="Awaiting verification" value={v.pending_verification} tone="busy" />
        <StatCard
          label="Clarification needed" value={v.clarification_required}
          tone={v.clarification_required ? 'warn' : 'neutral'}
          hint={v.clarification_required ? 'Action required from you' : undefined}
        />
        <StatCard label="Verified" value={v.verified_bids} tone="ok" />
      </div>

      {v.action_required.length > 0 && (
        <div className="card" style={{ marginBottom: 'var(--s5)' }}>
          <div className="card-header">
            <div>
              <h2>Action required</h2>
              <p className="small muted" style={{ marginTop: 2 }}>
                The department has asked for something before it can proceed
              </p>
            </div>
          </div>
          <div className="card-body flush">
            <BidTable
              bids={v.action_required}
              basePath="/bidder/bids"
              showCompany={false}
              showScores={false}
            />
          </div>
        </div>
      )}

      <div className="grid grid-2" style={{ marginBottom: 'var(--s5)' }}>
        <div className="card">
          <div className="card-header">
            <h2>Recent bids</h2>
            <Link to="/bidder/bids" className="small">View all</Link>
          </div>
          <div className="card-body flush">
            <BidTable
              bids={v.recent_bids}
              basePath="/bidder/bids"
              showCompany={false}
              showScores={false}
              emptyTitle="No bids yet"
              emptyHint="Start from an open tender."
            />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2>Notifications</h2>
            <Link to="/bidder/notifications" className="small">View all</Link>
          </div>
          <div className="card-body flush">
            {v.recent_notifications.length === 0 ? (
              <EmptyState title="Nothing new" />
            ) : (
              <ul className="notif-list">
                {v.recent_notifications.slice(0, 5).map((n) => (
                  <li key={n.id} className={`notif-item${n.read ? '' : ' unread'}`}>
                    <div className="between">
                      <span className="eyebrow">{NOTIFICATION_LABEL[n.type]}</span>
                      <span className="small muted">{formatRelative(n.created_at)}</span>
                    </div>
                    <div className="strong small">{n.title}</div>
                    <div className="small secondary">{n.message}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Open tenders</h2>
          <Link to="/bidder/tenders" className="small">Browse all</Link>
        </div>
        <div className="card-body flush">
          {v.open_tenders.length === 0 ? (
            <EmptyState title="No open tenders" />
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Tender</th>
                  <th style={{ width: 230 }}>Department</th>
                  <th style={{ width: 120 }} className="num">Value</th>
                  <th style={{ width: 150 }}>Closes</th>
                </tr>
              </thead>
              <tbody>
                {v.open_tenders.map((t) => {
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
                      <td className="small">
                        {days !== null && days >= 0
                          ? <span className={days <= 7 ? 'strong' : ''}
                                  style={days <= 7 ? { color: 'var(--review)' } : undefined}>
                              in {days} day{days === 1 ? '' : 's'}
                            </span>
                          : <span className="muted">closed</span>}
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
