import { useState } from 'react'
import type { ConsistencyDimensionReport, ConsistencyFlag } from '@/api/types'
import { Pill, VerdictPill } from '@/components/Primitives'
import {
  DIMENSION_BLURB, DIMENSION_LABEL, DOCUMENT_LABEL, sourceLabel,
} from '@/lib/labels'
import { VERDICT_TONE, dimensionIssue } from '@/lib/severity'
import { formatPercent } from '@/lib/format'

/**
 * One dimension. The bar is coloured by verdict, never by value — a 96.3%
 * POTENTIAL_INCONSISTENCY has to read as more serious than a 99.9% VARIATION,
 * and it cannot if the colour tracks the number.
 *
 * "Nothing to compare" renders as "Not applicable" with no bar, and must never
 * render as 0%. When the score is shown, a null score is that signal. When it
 * is hidden — the bidder portal — the score is null for every dimension, so the
 * signal has to come from the observations themselves instead. Reading it off
 * the score there labelled five perfectly consistent dimensions "Not
 * applicable".
 */
export function DimensionMeter({
  d, showScore = true, issuesOnly = false, flags = [],
}: {
  d: ConsistencyDimensionReport
  /** Off in the bidder portal: the verdict is shown, the percentage is not. */
  showScore?: boolean
  /**
   * On in the bidder portal. The row reports problems and stays silent
   * otherwise — no "Consistent", no "Not applicable". A clean dimension's
   * right-hand side is blank, so the badges that remain are all real findings
   * and the eye goes straight to them.
   */
  issuesOnly?: boolean
  /**
   * The report's flags, so a linkage finding raised against this dimension
   * shows here too. A linkage flag does not move the dimension's own verdict,
   * so without these the row would read clean while the finding sat above it.
   */
  flags?: ConsistencyFlag[]
}) {
  const [open, setOpen] = useState(false)
  const notApplicable = showScore
    ? d.score === null || d.score === undefined
    : d.observations.length === 0
  const tone = VERDICT_TONE[d.verdict]
  const issue = issuesOnly ? dimensionIssue(d, flags) : null

  const divergent = d.observations.filter((o) => o.verdict !== 'CONSISTENT')

  return (
    <div className={`meter meter-${tone}${notApplicable ? ' meter-na' : ''}`}>
      <button
        /* Without the bar, the row is a different grid — four columns, not
           five. Leaving the five-column template in place pushed the verdict
           pill into the 62px figure column, where it overflowed its own
           background. */
        className={`meter-head${
          issuesOnly ? ' meter-head-issues' : showScore ? '' : ' meter-head-plain'
        }`}
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

        {!issuesOnly && (notApplicable || showScore) && (
          <span className="meter-figure">
            {notApplicable
              ? <span className="small muted">Not applicable</span>
              : <span className="tnum meter-percent">{formatPercent(d.score)}</span>}
          </span>
        )}

        {issuesOnly
          ? issue && (
            <Pill tone={issue.tone} size="sm" dot={false}>
              <span className="issue-mark" aria-hidden>⚠</span>
              {issue.label}
            </Pill>
          )
          : <VerdictPill verdict={d.verdict} size="sm" />}
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
