"""Cross-document consistency analysis.

Per-document verification is the easy half. Every document in a bid can pass its
own registry lookup while the set still fails to describe one coherent entity:
the GST certificate says "Ram Singh", the Udyam certificate says "Ram". This
module is where that is caught.

**Canonical comparison, not pairwise.** Comparing twelve documents pairwise
across five dimensions is 330 comparisons and produces an unreadable matrix.
Instead each dimension picks one canonical value — from the registry where one
exists, otherwise the most frequently attested document value — and compares
every document against it. That is twelve comparisons per dimension, and it
renders as a sentence a human can act on: "ten documents agree, one diverges."

Nothing here calls a language model. Verdicts come from ``normalize``, whose
bands live in ``app.config``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from ..models import (
    Bid,
    ConsistencyDimension,
    ConsistencyReport,
    ConsistencyVerdict,
    Document,
    DocumentType,
    utcnow,
)
from . import linkage, normalize
from .normalize import Comparison
from .registry import RegistryGateway

#: Rank order for choosing a canonical value when the registry has nothing to
#: say. A certificate issued by an authority outranks a self-declaration.
_AUTHORITY = [
    DocumentType.PAN,
    DocumentType.GST_CERTIFICATE,
    DocumentType.INCORPORATION,
    DocumentType.UDYAM,
    DocumentType.EPFO_ESIC,
    DocumentType.CONTRACT,
    DocumentType.TURNOVER,
    DocumentType.BANK_MANDATE,
    DocumentType.OEM_AUTHORISATION,
    DocumentType.LOCAL_CONTENT,
    DocumentType.EXPERIENCE,
    DocumentType.AADHAAR,
]

_SEVERITY = {
    ConsistencyVerdict.CONSISTENT.value: 0,
    ConsistencyVerdict.VARIATION.value: 1,
    ConsistencyVerdict.POTENTIAL_INCONSISTENCY.value: 2,
    ConsistencyVerdict.INCONSISTENT.value: 3,
}


@dataclass
class Observation:
    document_type: str
    document_id: int | None
    value: str | None
    similarity: float | None
    verdict: str
    reason: str


@dataclass
class DimensionReport:
    dimension: str
    score: float | None
    verdict: str
    canonical_value: str | None = None
    canonical_source: str | None = None
    observations: list[Observation] = field(default_factory=list)


@dataclass
class Flag:
    id: str
    dimension: str
    verdict: str
    title: str
    documents_involved: list[str]
    values: dict[str, str | None]


@dataclass
class Report:
    dimensions: list[DimensionReport]
    flags: list[Flag]
    consistency_score: float

    def to_payload(self) -> dict:
        return {
            "dimensions": [asdict(d) for d in self.dimensions],
            "flags": [asdict(f) for f in self.flags],
        }


# --------------------------------------------------------------------------
# dimension definitions
# --------------------------------------------------------------------------


def _values(documents: list[Document], key: str) -> list[tuple[Document, str]]:
    out = []
    for document in documents:
        value = (document.extracted_fields or {}).get(key)
        if value:
            out.append((document, str(value)))
    return out


def _modal(pairs: list[tuple[Document, str]], comparer) -> tuple[str, str] | None:
    """Most-attested value, ties broken by document authority."""
    if not pairs:
        return None
    counts = Counter(v for _, v in pairs)
    best_count = max(counts.values())
    candidates = [v for v, c in counts.items() if c == best_count]
    if len(candidates) == 1:
        chosen = candidates[0]
    else:
        order = {t.value: i for i, t in enumerate(_AUTHORITY)}
        chosen = min(
            candidates,
            key=lambda v: min(
                order.get(d.document_type, 99) for d, val in pairs if val == v
            ),
        )
    source = next(d.document_type for d, v in pairs if v == chosen)
    _ = comparer
    return chosen, source


def _build_dimension(
    dimension: ConsistencyDimension,
    pairs: list[tuple[Document, str]],
    comparer,
    canonical: tuple[str, str] | None,
) -> DimensionReport:
    if not pairs:
        return DimensionReport(
            dimension=dimension.value,
            score=None,
            verdict=ConsistencyVerdict.CONSISTENT.value,
            observations=[],
        )

    canonical = canonical or _modal(pairs, comparer)
    canonical_value, canonical_source = canonical

    observations: list[Observation] = []
    for document, value in pairs:
        comparison: Comparison = comparer(value, canonical_value)
        observations.append(
            Observation(
                document_type=document.document_type,
                document_id=document.id,
                value=value,
                similarity=comparison.similarity,
                verdict=comparison.verdict,
                reason=comparison.reason,
            )
        )

    worst = max(observations, key=lambda o: _SEVERITY[o.verdict]).verdict
    score = round(100.0 * sum(o.similarity or 0.0 for o in observations) / len(observations), 1)
    return DimensionReport(
        dimension=dimension.value,
        score=score,
        verdict=worst,
        canonical_value=canonical_value,
        canonical_source=canonical_source,
        observations=observations,
    )


def _signatory_pairs(documents: list[Document]) -> list[tuple[Document, str]]:
    """Signatory names only.

    Director lists are deliberately *not* folded in here. Whether the signatory
    appears on the board is a membership question, not a similarity one — a
    contract signed by someone absent from the register is a different problem
    from two spellings of the same name. See :func:`_relational_flags`.
    """
    return _values(documents, "signatory")


def _relational_flags(documents: list[Document]) -> list[Flag]:
    """Findings that exist only in the relation between two valid identifiers.

    Each of these can hold while every field passes its own check, which is why
    they live here and not in the per-document rules.
    """
    flags: list[Flag] = []

    def canonical(key: str) -> tuple[str, str] | None:
        return _modal(_values(documents, key), normalize.compare_identifiers)

    gstin = canonical("gstin")
    cin = canonical("cin")
    pan = canonical("pan")

    if gstin and pan:
        outcome = linkage.pan_matches_gstin(pan[0], gstin[0])
        if outcome and not outcome[0]:
            flags.append(
                Flag(
                    id="LINKAGE-GSTIN-PAN",
                    dimension=ConsistencyDimension.PAN.value,
                    verdict=ConsistencyVerdict.INCONSISTENT.value,
                    title="GSTIN does not embed the PAN shown on the PAN card",
                    documents_involved=[gstin[1], pan[1]],
                    values={
                        "GSTIN": gstin[0],
                        "PAN embedded in GSTIN": linkage.gstin_embedded_pan(gstin[0]),
                        "PAN on record": pan[0],
                    },
                )
            )

    if gstin and cin:
        outcome = linkage.gstin_agrees_with_cin_state(gstin[0], cin[0])
        if outcome and not outcome[0]:
            flags.append(
                Flag(
                    id="LINKAGE-GSTIN-CIN-STATE",
                    dimension=ConsistencyDimension.REGISTRATION.value,
                    verdict=ConsistencyVerdict.INCONSISTENT.value,
                    title="GSTIN and CIN place the company in different states",
                    documents_involved=[gstin[1], cin[1]],
                    values={"GSTIN": gstin[0], "CIN": cin[0]},
                )
            )

    signatory = _modal(_values(documents, "signatory"), normalize.compare_names)
    if signatory:
        for document in documents:
            directors = (document.extracted_fields or {}).get("directors")
            outcome = linkage.signatory_is_a_director(signatory[0], directors)
            if outcome and not outcome[0]:
                pretty = DocumentType(document.document_type).pretty
                flags.append(
                    Flag(
                        id=f"LINKAGE-SIGNATORY-{document.document_type}-{document.id}",
                        dimension=ConsistencyDimension.SIGNATORY.value,
                        verdict=ConsistencyVerdict.INCONSISTENT.value,
                        title=f"Authorised signatory is not listed as a director on the {pretty}",
                        documents_involved=[signatory[1], document.document_type],
                        values={"Signatory": signatory[0], f"Directors on {pretty}": directors},
                    )
                )
    return flags


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def analyse(bid: Bid, gw: RegistryGateway) -> Report:
    documents = [d for d in bid.active_documents if d.extracted_fields]

    # Canonical identity and address come from the registry where possible, so
    # a single document carrying a stale name cannot drag the canonical value
    # with it. The PAN registry is the authority on a company's legal name.
    canonical_identity = None
    canonical_address = None
    canonical_pan = None

    pan_pairs = _values(documents, "pan")
    if pan_pairs:
        modal_pan = _modal(pan_pairs, normalize.compare_identifiers)
        if modal_pan:
            record = gw.pan(modal_pan[0])
            if record.found:
                canonical_identity = (record.get("name"), "PAN_REGISTRY")
                canonical_pan = (record.get("pan"), "PAN_REGISTRY")

    gst_pairs = _values(documents, "gstin")
    if gst_pairs:
        modal_gstin = _modal(gst_pairs, normalize.compare_identifiers)
        if modal_gstin:
            record = gw.gstin(modal_gstin[0])
            if record.found and record.get("address"):
                canonical_address = (record.get("address"), "GST_REGISTRY")

    dimensions = [
        _build_dimension(
            ConsistencyDimension.IDENTITY,
            _values(documents, "company_name"),
            normalize.compare_names,
            canonical_identity,
        ),
        _build_dimension(
            ConsistencyDimension.ADDRESS,
            _values(documents, "address"),
            normalize.compare_addresses,
            canonical_address,
        ),
        _build_dimension(
            ConsistencyDimension.PAN,
            pan_pairs,
            normalize.compare_identifiers,
            canonical_pan,
        ),
        _build_dimension(
            ConsistencyDimension.REGISTRATION,
            gst_pairs + _values(documents, "cin") + _values(documents, "udyam_number"),
            normalize.compare_identifiers,
            None,
        ),
        _build_dimension(
            ConsistencyDimension.SIGNATORY,
            _signatory_pairs(documents),
            normalize.compare_names,
            None,
        ),
    ]

    # REGISTRATION mixes three identifier families; comparing a CIN against a
    # GSTIN is meaningless, so it is scored per family instead.
    dimensions[3] = _registration_dimension(documents)

    flags = _flags(dimensions) + _relational_flags(documents)
    flags.sort(key=lambda f: -_SEVERITY[f.verdict])
    scored = [d.score for d in dimensions if d.score is not None]
    consistency_score = round(sum(scored) / len(scored), 1) if scored else 100.0
    return Report(dimensions=dimensions, flags=flags, consistency_score=consistency_score)


def _registration_dimension(documents: list[Document]) -> DimensionReport:
    """GSTIN, CIN and Udyam each compared within their own family."""
    observations: list[Observation] = []
    canonical_bits: list[str] = []
    for key, label in (("gstin", "GSTIN"), ("cin", "CIN"), ("udyam_number", "Udyam")):
        pairs = _values(documents, key)
        if not pairs:
            continue
        canonical = _modal(pairs, normalize.compare_identifiers)
        if not canonical:
            continue
        canonical_bits.append(f"{label} {canonical[0]}")
        for document, value in pairs:
            comparison = normalize.compare_identifiers(value, canonical[0])
            observations.append(
                Observation(
                    document_type=document.document_type,
                    document_id=document.id,
                    value=f"{label}: {value}",
                    similarity=comparison.similarity,
                    verdict=comparison.verdict,
                    reason=comparison.reason,
                )
            )

    if not observations:
        return DimensionReport(
            ConsistencyDimension.REGISTRATION.value,
            None,
            ConsistencyVerdict.CONSISTENT.value,
        )
    worst = max(observations, key=lambda o: _SEVERITY[o.verdict]).verdict
    score = round(100.0 * sum(o.similarity or 0.0 for o in observations) / len(observations), 1)
    return DimensionReport(
        dimension=ConsistencyDimension.REGISTRATION.value,
        score=score,
        verdict=worst,
        canonical_value="; ".join(canonical_bits),
        canonical_source="most attested across documents",
        observations=observations,
    )


_TITLES = {
    ConsistencyDimension.IDENTITY.value: "Company name on {doc} differs from the registered legal name",
    ConsistencyDimension.ADDRESS.value: "Address on {doc} differs from the registered address",
    ConsistencyDimension.PAN.value: "PAN on {doc} differs from the PAN used elsewhere",
    ConsistencyDimension.REGISTRATION.value: "Registration identifier on {doc} differs from the rest of the bid",
    ConsistencyDimension.SIGNATORY.value: "Signatory on {doc} differs from the signatory named elsewhere",
}


def _flags(dimensions: list[DimensionReport]) -> list[Flag]:
    flags: list[Flag] = []
    for dimension in dimensions:
        for observation in dimension.observations:
            if observation.verdict == ConsistencyVerdict.CONSISTENT.value:
                continue
            pretty = DocumentType(observation.document_type).pretty
            flags.append(
                Flag(
                    id=f"{dimension.dimension}-{observation.document_type}-{observation.document_id}",
                    dimension=dimension.dimension,
                    verdict=observation.verdict,
                    title=_TITLES[dimension.dimension].format(doc=pretty),
                    documents_involved=[
                        dimension.canonical_source or "registry",
                        observation.document_type,
                    ],
                    values={
                        dimension.canonical_source or "canonical": dimension.canonical_value,
                        observation.document_type: observation.value,
                    },
                )
            )
    flags.sort(key=lambda f: -_SEVERITY[f.verdict])
    return flags


def persist(db: Session, bid: Bid, report: Report, document_score: float, overall: float) -> None:
    existing = bid.consistency_report
    if existing:
        db.delete(existing)
        db.flush()
    db.add(
        ConsistencyReport(
            bid_id=bid.id,
            overall_score=overall,
            document_score=document_score,
            consistency_score=report.consistency_score,
            payload=report.to_payload(),
            computed_at=utcnow(),
        )
    )
    db.flush()


def worst_verdict(report: Report) -> str:
    if not report.flags:
        return ConsistencyVerdict.CONSISTENT.value
    return max(report.flags, key=lambda f: _SEVERITY[f.verdict]).verdict
