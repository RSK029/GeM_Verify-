import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { admin, bids as bidsApi } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import {
  BidStatusPill, EmptyState, ErrorBanner, Loading, VerdictPill,
} from '@/components/Primitives'
import { CONSISTENCY_DIMENSIONS } from '@/api/types'
import type { ConsistencyReport } from '@/api/types'
import { DIMENSION_LABEL } from '@/lib/labels'
import { formatPercent } from '@/lib/format'
import { sortBids, VERDICT_WEIGHT } from '@/lib/severity'
import './compare.css'

const MAX = 3

export default function Compare() {
  const list = useAsync(() => admin.bids(), [])
  const [picked, setPicked] = useState<number[]>([])

  const reports = useAsync(
    () => Promise.all(
      picked.map((id) =>
        bidsApi.consistency(id)
          .then((r) => [id, r] as const)
          .catch(() => [id, null] as const)),
    ),
    [picked.join(',')],
    { enabled: picked.length > 0 },
  )

  const byId = useMemo(
    () => new Map(reports.data ?? []),
    [reports.data],
  )

  const chosen = (list.data ?? []).filter((b) => picked.includes(b.id))

  function toggle(id: number) {
    setPicked((p) =>
      p.includes(id) ? p.filter((x) => x !== id)
        : p.length >= MAX ? p : [...p, id])
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Compare bids</h1>
        <p className="small muted">
          Put up to {MAX} submissions side by side. Useful for seeing why two
          bids with near-identical scores are not equivalent.
        </p>
      </div>

      <div className="card" style={{ marginBottom: 'var(--s5)' }}>
        <div className="card-header">
          <h2>Select bids</h2>
          <span className="small muted tnum">{picked.length} of {MAX} selected</span>
        </div>
        <div className="card-body">
          {list.loading && list.initial && <Loading />}
          {list.error != null && <ErrorBanner error={list.error} onRetry={list.reload} />}
          <div className="pick-grid">
            {sortBids(list.data ?? []).map((b) => {
              const on = picked.includes(b.id)
              return (
                <button
                  key={b.id}
                  className={`pick-item${on ? ' on' : ''}`}
                  onClick={() => toggle(b.id)}
                  disabled={!on && picked.length >= MAX}
                >
                  <span className="pick-check" aria-hidden>{on ? '✓' : ''}</span>
                  <span className="grow truncate">{b.bidder_company}</span>
                  <BidStatusPill status={b.status} size="sm" />
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {chosen.length === 0 ? (
        <div className="card">
          <EmptyState
            title="Nothing selected"
            hint="Pick two or three bids above to compare them."
          />
        </div>
      ) : (
        <div className="card">
          <div className="card-header"><h2>Comparison</h2></div>
          <div className="card-body flush" style={{ overflowX: 'auto' }}>
            <table className="table compare-table">
              <thead>
                <tr>
                  <th style={{ width: 190 }}>Attribute</th>
                  {chosen.map((b) => (
                    <th key={b.id}>
                      <Link to={`/admin/bids/${b.id}`}>{b.bidder_company}</Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="strong">Status</td>
                  {chosen.map((b) => (
                    <td key={b.id}><BidStatusPill status={b.status} /></td>
                  ))}
                </tr>

                <tr className="compare-highlight">
                  <td className="strong">
                    Findings
                    <div className="small muted">What the comparison turned up</div>
                  </td>
                  {chosen.map((b) => {
                    const r = byId.get(b.id)
                    const flags = r?.flags ?? []
                    return (
                      <td key={b.id}>
                        {reports.loading && !r ? <span className="small muted">Loading…</span>
                          : flags.length === 0
                            ? <span className="small" style={{ color: 'var(--verified)' }}>
                                No disagreement
                              </span>
                            : (
                              <ul className="compare-flags">
                                {[...flags]
                                  .sort((x, y) => VERDICT_WEIGHT[y.verdict] - VERDICT_WEIGHT[x.verdict])
                                  .map((f) => (
                                    <li key={f.id}>
                                      <VerdictPill verdict={f.verdict} size="sm" />
                                      <span className="small">{f.title}</span>
                                    </li>
                                  ))}
                              </ul>
                            )}
                      </td>
                    )
                  })}
                </tr>

                <tr>
                  <td className="strong">Documents clear</td>
                  {chosen.map((b) => (
                    <td key={b.id} className="tnum">
                      {b.documents_verified} / {b.document_count}
                      {b.documents_flagged > 0 && (
                        <span className="small" style={{ color: 'var(--review)' }}>
                          {' '}· {b.documents_flagged} flagged
                        </span>
                      )}
                    </td>
                  ))}
                </tr>

                {CONSISTENCY_DIMENSIONS.map((dim) => (
                  <tr key={dim}>
                    <td>{DIMENSION_LABEL[dim]}</td>
                    {chosen.map((b) => {
                      const d = byId.get(b.id)?.dimensions.find((x) => x.dimension === dim)
                      if (!d) return <td key={b.id} className="muted">—</td>
                      return (
                        <td key={b.id}>
                          <div className="row gap2">
                            <VerdictPill verdict={d.verdict} size="sm" />
                            <span className="small muted tnum">
                              {d.score === null ? 'n/a' : formatPercent(d.score)}
                            </span>
                          </div>
                        </td>
                      )
                    })}
                  </tr>
                ))}

                <tr className="compare-scores">
                  <td className="small muted">Scores</td>
                  {chosen.map((b) => {
                    const r: ConsistencyReport | null | undefined = byId.get(b.id)
                    return (
                      <td key={b.id} className="small muted tnum">
                        docs {formatPercent(r?.document_score ?? null)}
                        {' · '}cross {formatPercent(r?.consistency_score ?? null)}
                        {' · '}overall {formatPercent(b.verification_score)}
                      </td>
                    )
                  })}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
