import { useState } from 'react'
import { bids as bidsApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { BidTable } from '@/components/BidTable'
import { ErrorBanner, Loading } from '@/components/Primitives'
import { BID_STATUS_LABEL } from '@/lib/labels'
import type { BidStatus } from '@/api/types'

const STATUSES = Object.keys(BID_STATUS_LABEL) as BidStatus[]

export default function MyBids() {
  const [status, setStatus] = useState<BidStatus | ''>('')
  const list = useAsync(() => bidsApi.listMine(status || undefined), [status])

  return (
    <div className="page">
      <div className="page-header">
        <h1>My bids</h1>
        <p className="small muted">Every bid you have started or submitted.</p>
      </div>

      <div className="card">
        <div className="toolbar">
          <select
            className="select"
            style={{ maxWidth: 210 }}
            value={status}
            onChange={(e) => setStatus(e.target.value as BidStatus | '')}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{BID_STATUS_LABEL[s]}</option>
            ))}
          </select>
          <span className="grow" />
          {list.data && (
            <span className="small muted tnum">{list.data.length} bids</span>
          )}
        </div>
        <div className="card-body flush">
          {list.loading && list.initial && <Loading />}
          {list.error != null && (
            <div style={{ padding: 'var(--s4)' }}>
              <ErrorBanner error={list.error} onRetry={list.reload} />
            </div>
          )}
          {list.data && (
            <BidTable
              bids={list.data}
              basePath="/bidder/bids"
              showCompany={false}
              showScores={false}
              emptyTitle="No bids"
              emptyHint="Start one from an open tender."
            />
          )}
        </div>
      </div>
    </div>
  )
}
