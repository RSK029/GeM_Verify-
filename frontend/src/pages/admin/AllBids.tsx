import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { admin } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { BidTable } from '@/components/BidTable'
import { ErrorBanner, Loading } from '@/components/Primitives'
import { BID_STATUS_LABEL } from '@/lib/labels'
import type { BidStatus } from '@/api/types'

const STATUSES = Object.keys(BID_STATUS_LABEL) as BidStatus[]

export default function AllBids() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as BidStatus | null) ?? undefined
  const [query, setQuery] = useState(params.get('q') ?? '')

  // Debounce the server-side search so typing does not fire a request a keystroke.
  const [debounced, setDebounced] = useState(query)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 250)
    return () => clearTimeout(t)
  }, [query])

  const list = useAsync(
    () => admin.bids({ status, q: debounced || undefined }),
    [status, debounced],
  )

  function setStatus(next: string) {
    const p = new URLSearchParams(params)
    if (next) p.set('status', next)
    else p.delete('status')
    setParams(p, { replace: true })
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>All bids</h1>
        <p className="small muted">
          Ordered by what needs a decision first, not by score.
        </p>
      </div>

      <div className="card">
        <div className="toolbar">
          <input
            className="input"
            style={{ maxWidth: 300 }}
            placeholder="Search company or tender number…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            className="select"
            style={{ maxWidth: 210 }}
            value={status ?? ''}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{BID_STATUS_LABEL[s]}</option>
            ))}
          </select>
          <span className="grow" />
          {list.data && (
            <span className="small muted tnum">
              {list.data.length} {list.data.length === 1 ? 'bid' : 'bids'}
            </span>
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
              basePath="/admin/bids"
              emptyTitle="No bids match"
              emptyHint="Try a different status or search term."
            />
          )}
        </div>
      </div>
    </div>
  )
}
