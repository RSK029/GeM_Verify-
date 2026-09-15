import { useNavigate } from 'react-router-dom'
import type { BidSummary } from '@/api/types'
import { BidStatusPill, EmptyState, ScoreValue } from '@/components/Primitives'
import { formatRelative } from '@/lib/format'
import { sortBids } from '@/lib/severity'

/**
 * Shared bid list.
 *
 * Rows are ordered by `sortBids`, which ranks by status and then by how much
 * is flagged. Score is the last tiebreak and is rendered small on the right —
 * a bid scoring 100.0 can be the most serious in the set, so it must not be
 * what the eye lands on.
 *
 * `showScores` is off in the bidder portal. The score is an internal review
 * aid, not a grade the applicant is owed; the API withholds it from bidders
 * anyway, so the column would only ever render a dash.
 */
export function BidTable({
  bids, basePath, showCompany = true, showScores = true,
  emptyTitle = 'No bids', emptyHint,
}: {
  bids: BidSummary[]
  basePath: string
  showCompany?: boolean
  showScores?: boolean
  emptyTitle?: string
  emptyHint?: string
}) {
  const navigate = useNavigate()
  const rows = sortBids(bids)

  if (rows.length === 0) {
    return <EmptyState title={emptyTitle} hint={emptyHint} />
  }

  return (
    <table className="table">
      <thead>
        <tr>
          {showCompany && <th>Bidder</th>}
          <th>Tender</th>
          <th style={{ width: 170 }}>Status</th>
          <th style={{ width: 150 }}>Documents</th>
          {showScores && <th style={{ width: 92 }} className="num">Score</th>}
          <th style={{ width: 110 }}>Updated</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((b) => (
          <tr
            key={b.id}
            className="clickable"
            onClick={() => navigate(`${basePath}/${b.id}`)}
          >
            {showCompany && (
              <td>
                <div className="strong">{b.bidder_company}</div>
              </td>
            )}
            <td>
              <div className="mono small">{b.tender_number}</div>
              <div className="small muted truncate" style={{ maxWidth: 280 }}>
                {b.tender_title}
              </div>
            </td>
            <td><BidStatusPill status={b.status} /></td>
            <td>
              <DocumentBar bid={b} />
            </td>
            {showScores && (
              <td className="num">
                <ScoreValue score={b.verification_score} />
              </td>
            )}
            <td className="small muted">{formatRelative(b.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function DocumentBar({ bid }: { bid: BidSummary }) {
  const total = bid.document_count || 12
  const flagged = bid.documents_flagged
  const clear = bid.documents_verified

  return (
    <div className="stack gap1">
      <div className="docbar" aria-hidden>
        {Array.from({ length: total }).map((_, i) => (
          <span
            key={i}
            className={
              i < flagged ? 'docbar-cell flagged'
                : i < flagged + clear ? 'docbar-cell clear'
                  : 'docbar-cell pending'
            }
          />
        ))}
      </div>
      <span className="small muted tnum">
        {flagged > 0 ? `${flagged} flagged · ` : ''}{clear}/{total} clear
      </span>
    </div>
  )
}
