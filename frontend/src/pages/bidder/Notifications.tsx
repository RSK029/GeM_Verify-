import { notifications as notifApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import { usePolling } from '@/hooks/usePolling'
import { EmptyState, ErrorBanner, Loading } from '@/components/Primitives'
import { NOTIFICATION_LABEL } from '@/lib/labels'
import { formatDateTime } from '@/lib/format'
import { Link } from 'react-router-dom'

export default function Notifications() {
  const list = useAsync(() => notifApi.list(), [])
  usePolling(list.reload, 8000)

  async function markAll() {
    await notifApi.markAllRead()
    await list.reload()
  }

  async function mark(id: number) {
    await notifApi.markRead(id)
    await list.reload()
  }

  const unread = list.data?.unread_count ?? 0

  return (
    <div className="page">
      <div className="page-header">
        <h1>Notifications</h1>
        <p className="small muted">Updates on your bids from the department.</p>
      </div>

      <div className="card">
        <div className="card-header">
          <h2>{unread > 0 ? `${unread} unread` : 'All read'}</h2>
          {unread > 0 && (
            <button className="btn btn-sm" onClick={markAll}>Mark all read</button>
          )}
        </div>
        <div className="card-body flush">
          {list.loading && list.initial && <Loading />}
          {list.error != null && (
            <div style={{ padding: 'var(--s4)' }}>
              <ErrorBanner error={list.error} onRetry={list.reload} />
            </div>
          )}
          {list.data?.items.length === 0 && <EmptyState title="Nothing yet" />}
          <ul className="notif-list">
            {list.data?.items.map((n) => (
              <li key={n.id} className={`notif-item${n.read ? '' : ' unread'}`}>
                <div className="between">
                  <span className="eyebrow">{NOTIFICATION_LABEL[n.type]}</span>
                  <span className="small muted">{formatDateTime(n.created_at)}</span>
                </div>
                <div className="strong">{n.title}</div>
                <div className="small secondary">{n.message}</div>
                <div className="row gap3" style={{ marginTop: 6 }}>
                  {n.bid_id && (
                    <Link className="small" to={`/bidder/bids/${n.bid_id}`}>
                      Open bid →
                    </Link>
                  )}
                  {!n.read && (
                    <button className="btn btn-sm btn-ghost" onClick={() => mark(n.id)}>
                      Mark read
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
