import { useState } from 'react'
import type { ConsistencyDimensionReport } from '@/api/types'
import { VerdictPill } from '@/components/Primitives'
import {
  DIMENSION_BLURB, DIMENSION_LABEL, DOCUMENT_LABEL, sourceLabel,
} from '@/lib/labels'
import { VERDICT_TONE } from '@/lib/severity'
import { formatPercent } from '@/lib/format'

/**
 * One dimension. The bar is coloured by verdict, never by value — a 96.3%
 * POTENTIAL_INCONSISTENCY has to read as more serious than a 99.9% VARIATION,
 * and it cannot if the colour tracks the number.
 *
 * score === null means there was nothing to compare. That renders as
 * "Not applicable" with no bar. It must never render as 0%.
 */
export function DimensionMeter({
  d, showScore = true,
}: {
  d: ConsistencyDimensionReport
  /** Off in the bidder portal: the verdict is shown, the percentage is not. */
  showScore?: boolean
}) {
  const [open, setOpen] = useState(false)
  const notApplicable = d.score === null || d.score === undefined
  const tone = VERDICT_TONE[d.verdict]

  const divergent = d.observations.filter((o) => o.verdict !== 'CONSISTENT')

  return (
    <div className={`meter meter-${tone}${notApplicable ? ' meter-na' : ''}`}>
      <button
        className="meter-head"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="meter-caret" aria-hidden>{open ? '▾' : '▸'}</span>

        <span className="meter-identity">
          <span className="meter-label">{DIMENSION_LABEL[d.dimension]}</span>
          <span className="meter-blurb">{DIMENSION_BLURB[d.dimension]}</span>
        </span>

        {showScore && (
        <span className="meter-track" aria-hidden>
          {!notApplicable && (
            <span className="meter-fill" style={{ width: `${Math.max(2, d.score!)}%` }} />
          )}
        </span>
        )}

        <span className="meter-figure">
          {notApplicable
            ? <span className="small muted">Not applicable</span>
            : showScore
              ? <span className="tnum meter-percent">{formatPercent(d.score)}</span>
              : null}
        </span>

        <VerdictPill verdict={d.verdict} size="sm" />
      </button>

      {open && (
        <div className="meter-detail">
          <div className="meter-canonical">
            <span className="eyebrow">Canonical value</span>
            <div className="meter-canonical-value mono">
              {d.canonical_value ?? <span className="muted">Not established</span>}
            </div>
            <span className="small muted">
              from {sourceLabel(d.canonical_source)}
            </span>
          </div>

          {d.observations.length === 0 ? (
            <p className="small muted">No documents carry this field.</p>
          ) : (
            <table className="table obs-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Value as read</th>
                  {showScore && <th style={{ width: 70 }}>Match</th>}
                  <th style={{ width: 150 }}>Verdict</th>
                </tr>
              </thead>
              <tbody>
                {[...d.observations]
                  .sort((a, b) =>
                    (a.verdict === 'CONSISTENT' ? 1 : 0) -
                    (b.verdict === 'CONSISTENT' ? 1 : 0))
                  .map((o) => (
                    <tr key={`${o.document_id}-${o.document_type}`}
                        className={o.verdict !== 'CONSISTENT' ? 'obs-divergent' : undefined}>
                      <td>{DOCUMENT_LABEL[o.document_type] ?? o.document_type}</td>
                      <td className="mono obs-value" title={o.reason ?? undefined}>
                        {o.value ?? <span className="muted">—</span>}
                      </td>
                      {showScore && (
                        <td className="num tnum">
                          {o.similarity === null || o.similarity === undefined
                            ? '—'
                            : `${Math.round(o.similarity * 100)}%`}
                        </td>
                      )}
                      <td><VerdictPill verdict={o.verdict} size="sm" /></td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}

          {divergent.length > 0 && divergent[0].reason && (
            <p className="small secondary meter-reason">
              <strong>Why:</strong> {divergent[0].reason}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
