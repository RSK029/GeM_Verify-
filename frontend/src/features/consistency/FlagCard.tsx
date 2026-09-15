import type { BidDocument, ConsistencyFlag } from '@/api/types'
import { VerdictPill } from '@/components/Primitives'
import {
  DIMENSION_LABEL, VERDICT_MEANING, isRegistrySource, sourceLabel,
} from '@/lib/labels'
import type { ConsistencyDimension } from '@/api/types'

/**
 * One finding, rendered as a comparison.
 *
 * The shape of `values` is not uniform. Most flags carry two entries — the
 * canonical source and the document that diverges from it. The GSTIN linkage
 * flags carry three, keyed by description rather than by document
 * ("PAN embedded in GSTIN", "PAN on record"). So this renders the general
 * case and only uses the two-column treatment when it genuinely applies.
 */
export function FlagCard({
  flag, canonicalSource, resolveDocument, onOpenDocument,
}: {
  flag: ConsistencyFlag
  /** The dimension's canonical_source, used to mark which value is the truth. */
  canonicalSource?: string | null
  resolveDocument?: (documentType: string) => BidDocument | null
  onOpenDocument?: (doc: BidDocument) => void
}) {
  const entries = Object.entries(flag.values ?? {})
  const dimensionLabel =
    DIMENSION_LABEL[flag.dimension as ConsistencyDimension] ?? flag.dimension

  // Which entry, if any, is the source of truth? Prefer the dimension's
  // canonical source; fall back to a registry key, which outranks a document.
  const canonicalKey =
    entries.find(([k]) => k === canonicalSource)?.[0] ??
    entries.find(([k]) => isRegistrySource(k))?.[0] ??
    null

  const pair = entries.length === 2 && canonicalKey !== null
  const ordered = pair
    ? [
        entries.find(([k]) => k === canonicalKey)!,
        entries.find(([k]) => k !== canonicalKey)!,
      ]
    : entries

  return (
    <article className={`flag-card flag-${flag.verdict}`}>
      <header className="flag-head">
        <div className="grow">
          <div className="flag-dimension eyebrow">{dimensionLabel}</div>
          <h3 className="flag-title">{flag.title}</h3>
        </div>
        <VerdictPill verdict={flag.verdict} />
      </header>

      <div className={pair ? 'flag-compare pair' : 'flag-compare stack-list'}>
        {ordered.map(([key, value], i) => {
          const isCanonical = key === canonicalKey
          return (
            <div
              key={key}
              className={`flag-value${isCanonical ? ' canonical' : ' divergent'}`}
            >
              <div className="flag-value-source">
                <span className="truncate">{sourceLabel(key)}</span>
                {isCanonical && <span className="chip-truth">Source of truth</span>}
                {isRegistrySource(key) && !isCanonical && (
                  <span className="chip-registry">Registry</span>
                )}
              </div>
              <div className="flag-value-text mono">{value || '—'}</div>
              {(() => {
                const doc = !isCanonical ? resolveDocument?.(key) : null
                if (!doc || !onOpenDocument) return null
                return (
                  <button
                    className="flag-open"
                    onClick={() => onOpenDocument(doc)}
                  >
                    Open this document →
                  </button>
                )
              })()}
              {pair && i === 0 && <span className="flag-vs" aria-hidden>vs</span>}
            </div>
          )
        })}
      </div>

      <footer className="flag-foot">
        <p className="flag-meaning">{VERDICT_MEANING[flag.verdict]}</p>
        {/* documents_involved can repeat the same entry — the linkage flags
            report ['CONTRACT','CONTRACT'] — so dedupe before offering links. */}
        {onOpenDocument && (() => {
          const seen = new Set<string>()
          const docs = flag.documents_involved
            .filter((k) => !seen.has(k) && seen.add(k))
            .map((k) => ({ key: k, doc: resolveDocument?.(k) ?? null }))
            .filter((x) => x.doc !== null)
          if (docs.length === 0 || pair) return null
          return (
            <div className="row gap2 wrap flag-links">
              {docs.map(({ key, doc }) => (
                <button key={key} className="flag-open"
                        onClick={() => onOpenDocument(doc!)}>
                  Open {sourceLabel(key)} →
                </button>
              ))}
            </div>
          )
        })()}
        {canonicalSource && (
          <p className="flag-provenance small muted">
            Compared against{' '}
            <strong>{sourceLabel(canonicalSource)}</strong>
            {isRegistrySource(canonicalSource)
              ? ' — an external registry record, not a document the bidder supplied.'
              : ' — the value attested by the rest of the submission.'}
          </p>
        )}
      </footer>
    </article>
  )
}
