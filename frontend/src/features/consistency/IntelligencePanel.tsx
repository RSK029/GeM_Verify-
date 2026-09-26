import type {
  BidDocument, BidStatus, ConsistencyReport, ExplanationKind,
} from '@/api/types'
import { CONSISTENCY_DIMENSIONS } from '@/api/types'
import { DimensionMeter } from './DimensionMeter'
import { FlagCard } from './FlagCard'
import { AiAssessment } from '@/features/ai/AiAssessment'
import { Pill } from '@/components/Primitives'
import { VERDICT_WEIGHT, worstTone, VERDICT_TONE } from '@/lib/severity'
import { formatPercent, formatDateTime } from '@/lib/format'
import './consistency.css'

/**
 * The cross-document layer.
 *
 * Ordering is the argument this panel makes. Findings come first because they
 * carry the signal; the dimension meters are context underneath them; the
 * generated summary comes last because it is commentary. Scores appear only as
 * small figures inside the meters and in one muted strip at the bottom — never
 * as a headline. A bid can score 100.0 on every dimension and still be the most
 * serious case in the set (d10 does exactly that), so a big green number at the
 * top would actively mislead.
 */
export function IntelligencePanel({
  report, bidId, bidStatus, canRegenerate, resolveDocument, onOpenDocument,
  explanationKind = 'ADMIN_SUMMARY', showScores = true, issuesOnly = false,
}: {
  report: ConsistencyReport
  bidId: number
  bidStatus: BidStatus
  canRegenerate?: boolean
  /**
   * Off in the bidder portal. The findings and verdicts stay — a bidder is
   * entitled to see what was found in their own documents — but the numbers
   * are review apparatus and belong to the officer. The API sends bidders
   * nulls for all of them, so this only suppresses the empty chrome.
   */
  showScores?: boolean
  /**
   * On in the bidder portal: the dimension rows badge problems only, and stay
   * blank when there is nothing wrong. See DimensionMeter.
   */
  issuesOnly?: boolean
  /**
   * Which narration to show beneath the findings, or null for none.
   * ADMIN_SUMMARY is admin-only — the API answers a bidder asking for it with
   * 403 — so the bidder portal passes null and renders the kinds it is
   * allowed (CLARIFICATION_DRAFT, DECISION_REASONING) separately.
   */
  explanationKind?: ExplanationKind | null
  /** Maps a flag's document key to a real document on this bid, if there is one. */
  resolveDocument?: (documentType: string) => BidDocument | null
  /** Jumps the viewer to that document, so a finding leads straight to the page. */
  onOpenDocument?: (doc: BidDocument) => void
}) {
  const flags = [...(report.flags ?? [])].sort(
    (a, b) => VERDICT_WEIGHT[b.verdict] - VERDICT_WEIGHT[a.verdict],
  )

  // Keep the five dimensions in the contract's order even if the API reorders.
  const dims = CONSISTENCY_DIMENSIONS
    .map((name) => report.dimensions.find((d) => d.dimension === name))
    .filter((d): d is NonNullable<typeof d> => Boolean(d))

  const canonicalFor = (dimension: string) =>
    report.dimensions.find((d) => d.dimension === dimension)?.canonical_source

  const headlineTone = flags.length
    ? worstTone(flags.map((f) => VERDICT_TONE[f.verdict]))
    : 'ok'

  const inReview =
    bidStatus === 'MANUAL_REVIEW' || bidStatus === 'CLARIFICATION_REQUIRED'

  return (
    <section className="intel card">
      <header className="intel-head">
        <div className="grow">
          <h2>Cross-document intelligence</h2>
          <p className="small muted">
            Every document compared against the others and against the
            registries, across five dimensions.
          </p>
        </div>
        {flags.length > 0 ? (
          <Pill tone={headlineTone}>
            {flags.length} {flags.length === 1 ? 'finding' : 'findings'}
          </Pill>
        ) : (
          <Pill tone="ok">No disagreements</Pill>
        )}
      </header>

      {/* ---------------------------------------------------- findings */}
      <div className="intel-section">
        <div className="intel-section-head">
          <h3>Findings</h3>
          <span className="small muted">
            What the comparison actually turned up
          </span>
        </div>

        {flags.length > 0 ? (
          <div className="flag-list">
            {flags.map((f) => (
              <FlagCard
                key={f.id}
                flag={f}
                canonicalSource={canonicalFor(f.dimension)}
                resolveDocument={resolveDocument}
                onOpenDocument={onOpenDocument}
              />
            ))}
          </div>
        ) : (
          <div className="no-flags">
            <div className="no-flags-mark" aria-hidden>✓</div>
            <div>
              <div className="strong">No cross-document disagreement</div>
              <p className="small secondary">
                Every document agrees on the company identity, address, PAN,
                registration numbers and signatory.
              </p>
              {inReview && (
                /* d4 is exactly this case: perfect consistency, a corrupt
                   GSTIN repeated faithfully in all twelve documents. Saying so
                   stops the clean panel from reading as "nothing is wrong". */
                <p className="small no-flags-note">
                  This bid is still in review because of a{' '}
                  <strong>per-document check</strong>, not a cross-document one.
                  The finding is in the document checklist — a value can be
                  internally consistent across every document and still be
                  invalid on its own.
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* -------------------------------------------------- dimensions */}
      <div className="intel-section">
        <div className="intel-section-head">
          <h3>Dimensions</h3>
          <span className="small muted">
            Select a dimension to see every document's value
          </span>
        </div>
        <div className="meter-list">
          {dims.map((d) => (
            <DimensionMeter
              key={d.dimension}
              d={d}
              showScore={showScores}
              issuesOnly={issuesOnly}
              flags={flags}
            />
          ))}
        </div>
      </div>

      {/* --------------------------------------------------- narration */}
      {explanationKind && (
        <div className="intel-section intel-ai">
          <AiAssessment
            bidId={bidId}
            kind={explanationKind}
            canRegenerate={canRegenerate}
          />
        </div>
      )}

      {/* Scores last, small, and clearly secondary. */}
      <footer className="intel-scores">
        {showScores && (
          <>
            <ScoreChip label="Document checks" value={report.document_score} />
            <ScoreChip label="Cross-document" value={report.consistency_score} />
            <ScoreChip label="Overall" value={report.overall_score} />
          </>
        )}
        <span className="grow" />
        <span className="small muted">
          Computed {formatDateTime(report.computed_at)}
        </span>
      </footer>
    </section>
  )
}

function ScoreChip({ label, value }: { label: string; value: number | null }) {
  return (
    <span className="score-chip">
      <span className="score-chip-label">{label}</span>
      <span className="score-chip-value tnum">{formatPercent(value)}</span>
    </span>
  )
}
