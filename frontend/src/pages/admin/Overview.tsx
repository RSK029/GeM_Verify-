import { useNavigate } from 'react-router-dom'
import { admin } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { usePolling } from '@/hooks/usePolling'
import { BidTable } from '@/components/BidTable'
import { ErrorBanner, Loading, StatCard } from '@/components/Primitives'
import { BID_STATUS_LABEL } from '@/lib/labels'
import { STATUS_TONE } from '@/lib/severity'
import type { BidStatus } from '@/api/types'

export default function AdminOverview() {
  const nav = useNavigate()
  const ov = useAsync(() => admin.overview(), [])
  usePolling(ov.reload, 10_000)

  if (ov.loading && ov.initial) return <Loading />
  if (ov.error != null) {
    return <div className="page"><ErrorBanner error={ov.error} onRetry={ov.reload} /></div>
  }
  if (!ov.data) return null

  const d = ov.data
  const attention = d.attention_required.length
  const clarifications = d.pending_clarifications.length

  return (
    <div className="page">
      <div className="page-header">
        <h1>Verification overview</h1>
        <p className="small muted">
          Bids awaiting a decision are listed first. Nothing is auto-rejected —
          every outcome here is a recommendation for a person to act on.
        </p>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 'var(--s5)' }}>
        <StatCard label="Total bids" value={d.total_bids} />
        <StatCard
          label="Needs review" value={attention} tone={attention ? 'warn' : 'ok'}
          hint={attention ? 'Awaiting a decision' : 'Queue is clear'}
          onClick={() => nav('/admin/bids?status=MANUAL_REVIEW')}
        />
        <StatCard
          label="Clarifications open" value={clarifications}
          tone={clarifications ? 'warn' : 'neutral'}
          hint={clarifications ? 'Waiting on bidders' : 'None outstanding'}
        />
        <StatCard
          label="Verified" value={d.by_status.VERIFIED ?? 0} tone="ok"
          hint="Cleared every check"
        />
      </div>

      <div className="card" style={{ marginBottom: 'var(--s5)' }}>
        <div className="card-header"><h2>Bids by status</h2></div>
        <div className="card-body">
          <div className="row gap3 wrap">
            {(Object.entries(d.by_status) as [BidStatus, number][])
              .sort((a, b) => b[1] - a[1])
              .map(([status, count]) => (
                <button
                  key={status}
                  className={`status-chip tone-${STATUS_TONE[status]}`}
                  onClick={() => nav(`/admin/bids?status=${status}`)}
                >
                  <span className="tnum status-chip-count">{count}</span>
                  <span>{BID_STATUS_LABEL[status]}</span>
                </button>
              ))}
          </div>
        </div>
      </div>

      {attention > 0 && (
        <div className="card" style={{ marginBottom: 'var(--s5)' }}>
          <div className="card-header">
            <div>
              <h2>Attention required</h2>
              <p className="small muted" style={{ marginTop: 2 }}>
                Verification finished and found something a person needs to judge
              </p>
            </div>
          </div>
          <div className="card-body flush">
            <BidTable bids={d.attention_required} basePath="/admin/bids" />
          </div>
        </div>
      )}

      {clarifications > 0 && (
        <div className="card" style={{ marginBottom: 'var(--s5)' }}>
          <div className="card-header"><h2>Pending clarifications</h2></div>
          <div className="card-body flush">
            <BidTable bids={d.pending_clarifications} basePath="/admin/bids" />
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-header"><h2>Recent submissions</h2></div>
        <div className="card-body flush">
          <BidTable
            bids={d.recent_submissions}
            basePath="/admin/bids"
            emptyTitle="No submissions yet"
          />
        </div>
      </div>
    </div>
  )
}
