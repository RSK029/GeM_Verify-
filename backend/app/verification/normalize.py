"""Normalisation and similarity — the arithmetic behind every consistency verdict.

This module is the whole reason the system does not need an LLM to decide
anything. "ABC Industrial Systems" and "ABC Industrial Systems Private Limited"
are recognised as the same entity by a token-subset rule; "123 M.G. Road" and
"123 Mahatma Gandhi Road" by abbreviation expansion; "Ram Singh" and "John Kumar"
fall below the floor and are flagged. All of it is deterministic, so the same
bid always produces the same verdict and every number traces to a rule here or a
threshold in ``app.config``.

Similarity uses the standard library only (``difflib``), not rapidfuzz. That
keeps the result identical on every machine — a demo that scores 86% here must
score 86% on the presentation laptop — and removes a dependency from the
critical path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from ..config import settings
from ..models import ConsistencyVerdict

# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------

#: Expanded before comparison so an abbreviation is not read as a difference.
_ABBREVIATIONS = {
    # corporate
    "PVT": "PRIVATE",
    "PVT.": "PRIVATE",
    "PRIVATE": "PRIVATE",
    "LTD": "LIMITED",
    "LTD.": "LIMITED",
    "CO": "COMPANY",
    "CORP": "CORPORATION",
    "&": "AND",
    # address
    "RD": "ROAD",
    "ST": "STREET",
    "MG": "MAHATMA GANDHI",
    "NR": "NEAR",
    "OPP": "OPPOSITE",
    "BLDG": "BUILDING",
    "APT": "APARTMENT",
    "FLR": "FLOOR",
    "IND": "INDUSTRIAL",
    "INDL": "INDUSTRIAL",
    "EST": "ESTATE",
    "E": "EAST",
    "W": "WEST",
    "N": "NORTH",
    "S": "SOUTH",
    "PH": "PHASE",
    "SEC": "SECTOR",
    "DIST": "DISTRICT",
    "NO": "NUMBER",
}

#: Dropped from the comparison core. A company is still the same company whether
#: or not the document spells out "Private Limited".
_CORPORATE_SUFFIXES = {
    "PRIVATE",
    "LIMITED",
    "LTD",
    "PVT",
    "LLP",
    "INC",
    "INCORPORATED",
    "CORPORATION",
    "COMPANY",
    "ENTERPRISES",
    "ENTERPRISE",
}

#: Dropped from names: honorifics and trade prefixes.
_NAME_PREFIXES = {"M/S", "MS", "MESSRS", "MR", "MRS", "SHRI", "SMT", "DR", "THE"}

#: Dropped from addresses: filler that carries no locating information.
_ADDRESS_NOISE = {"NUMBER", "PLOT", "SHED", "SURVEY", "AT", "IN", "OF"}

_PIN_RE = re.compile(r"\b(\d{6})\b")


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------


def _tokenise(value: str) -> list[str]:
    cleaned = re.sub(r"[^A-Za-z0-9&/ ]+", " ", (value or "").upper())
    tokens: list[str] = []
    for raw in cleaned.split():
        expanded = _ABBREVIATIONS.get(raw.rstrip("."), raw)
        tokens.extend(expanded.split())
    return [t for t in tokens if t]


def normalize_name(value: str) -> str:
    tokens = [t for t in _tokenise(value) if t not in _NAME_PREFIXES]
    return " ".join(tokens)


def name_core(value: str) -> frozenset[str]:
    """Tokens that actually identify the entity: no suffixes, no honorifics."""
    return frozenset(t for t in normalize_name(value).split() if t not in _CORPORATE_SUFFIXES)


def normalize_address(value: str) -> str:
    tokens = [t for t in _tokenise(value) if t not in _ADDRESS_NOISE]
    return " ".join(tokens)


def address_pin(value: str) -> str | None:
    match = _PIN_RE.search(value or "")
    return match.group(1) if match else None


def normalize_identifier(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


# --------------------------------------------------------------------------
# similarity
# --------------------------------------------------------------------------


def _ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def token_set_ratio(a: str, b: str) -> float:
    """Order-insensitive similarity over token sets.

    Mirrors the classic token-set ratio: compare the shared tokens against each
    side's full token list, and take the best of the three pairings. Word order
    and duplicated tokens therefore do not count as differences.
    """
    ta, tb = set(a.split()), set(b.split())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    shared = " ".join(sorted(ta & tb))
    full_a = " ".join(sorted(ta & tb) + sorted(ta - tb)).strip()
    full_b = " ".join(sorted(ta & tb) + sorted(tb - ta)).strip()
    return max(_ratio(shared, full_a), _ratio(shared, full_b), _ratio(full_a, full_b))


def _initials_expand(a: str, b: str) -> bool:
    """True if one name is the other with some given names reduced to initials.

    "R SINGH" vs "RAM SINGH" -> True.  "R SINGH" vs "RAM KUMAR" -> False.
    """
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb) or not ta:
        return False
    saw_initial = False
    for x, y in zip(ta, tb):
        if x == y:
            continue
        short, long_ = (x, y) if len(x) < len(y) else (y, x)
        if len(short) == 1 and long_.startswith(short):
            saw_initial = True
            continue
        return False
    return saw_initial


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Comparison:
    similarity: float
    verdict: str
    reason: str

    @property
    def is_clean(self) -> bool:
        return self.verdict == ConsistencyVerdict.CONSISTENT.value


def _band(similarity: float) -> str:
    """The four thresholds every verdict in the system reduces to."""
    if similarity >= settings.SIM_CONSISTENT:
        return ConsistencyVerdict.CONSISTENT.value
    if similarity >= settings.SIM_POTENTIAL:
        return ConsistencyVerdict.POTENTIAL_INCONSISTENCY.value
    return ConsistencyVerdict.INCONSISTENT.value


def compare_names(a: str | None, b: str | None) -> Comparison:
    if not a or not b:
        return Comparison(0.0, ConsistencyVerdict.CONSISTENT.value, "nothing to compare")

    na, nb = normalize_name(a), normalize_name(b)
    if na == nb:
        return Comparison(1.0, ConsistencyVerdict.CONSISTENT.value, "identical after normalisation")

    ca, cb = name_core(a), name_core(b)
    if ca and cb and ca == cb:
        # Identical once the corporate suffix is set aside — but the documents
        # do not literally agree, and the system should be seen to have noticed
        # and judged it benign rather than silently normalising it away.
        # ("Pvt. Ltd." vs "Private Limited" normalises to the same string and
        # was already caught above; this is an omitted suffix, not an
        # abbreviated one.)
        return Comparison(
            0.95,
            ConsistencyVerdict.VARIATION.value,
            "same name; one document omits the corporate suffix",
        )

    # A strict subset is an abbreviation, not a contradiction: "ABC Industrial"
    # inside "ABC Industrial Systems". Worth a human glance, not a failure.
    if ca and cb and (ca < cb or cb < ca):
        shorter, longer = (ca, cb) if ca < cb else (cb, ca)
        coverage = len(shorter) / len(longer)
        return Comparison(
            round(0.70 + 0.25 * coverage, 3),
            ConsistencyVerdict.VARIATION.value,
            "one name is a shortened form of the other",
        )

    if _initials_expand(na, nb):
        return Comparison(
            0.88, ConsistencyVerdict.VARIATION.value, "given names abbreviated to initials"
        )

    similarity = round(token_set_ratio(" ".join(sorted(ca)), " ".join(sorted(cb))), 3)
    verdict = _band(similarity)

    # A shared distinctive token means these plausibly name the same entity
    # under a former or misspelled style — a rename, not a different company.
    # "DEF Technocraft" and "DEF Techno Equipments" share DEF and belong in
    # review; "Ram Singh" and "John Kumar" share nothing and do not.
    if verdict == ConsistencyVerdict.INCONSISTENT.value and _shares_distinctive_token(ca, cb):
        return Comparison(
            similarity,
            ConsistencyVerdict.POTENTIAL_INCONSISTENCY.value,
            "names share a distinctive element but differ substantially; "
            "may be a former or misspelled name",
        )

    reason = {
        ConsistencyVerdict.CONSISTENT.value: "minor spelling differences only",
        ConsistencyVerdict.POTENTIAL_INCONSISTENCY.value: "names are similar but not equivalent",
        ConsistencyVerdict.INCONSISTENT.value: "names do not correspond",
    }[verdict]
    return Comparison(similarity, verdict, reason)


def _shares_distinctive_token(a: frozenset[str], b: frozenset[str]) -> bool:
    return any(len(token) > 2 for token in (a & b))


def compare_addresses(a: str | None, b: str | None) -> Comparison:
    if not a or not b:
        return Comparison(0.0, ConsistencyVerdict.CONSISTENT.value, "nothing to compare")

    na, nb = normalize_address(a), normalize_address(b)
    if na == nb:
        return Comparison(1.0, ConsistencyVerdict.CONSISTENT.value, "identical after normalisation")

    pin_a, pin_b = address_pin(a), address_pin(b)
    if pin_a and pin_b and pin_a != pin_b:
        return Comparison(
            0.20,
            ConsistencyVerdict.INCONSISTENT.value,
            f"different PIN codes ({pin_a} and {pin_b})",
        )

    similarity = round(token_set_ratio(na, nb), 3)

    # Same PIN plus a strong textual match is formatting, not a different place.
    if pin_a and pin_b and pin_a == pin_b and similarity >= settings.SIM_POTENTIAL:
        return Comparison(
            max(similarity, 0.92),
            ConsistencyVerdict.CONSISTENT.value,
            "same PIN code; differences are formatting and abbreviation",
        )

    # One side simply omits the PIN or a locality — incomplete, not contradictory.
    # Scored by how much of the fuller address survives, and deliberately capped
    # below the CONSISTENT band so a flagged row never shows 100% in the UI.
    ta, tb = set(na.split()), set(nb.split())
    if ta and tb and (ta < tb or tb < ta):
        shorter, longer = (ta, tb) if ta < tb else (tb, ta)
        coverage = len(shorter) / len(longer)
        return Comparison(
            round(min(0.89, 0.70 + 0.20 * coverage), 3),
            ConsistencyVerdict.VARIATION.value,
            "one address omits components present in the other",
        )

    verdict = _band(similarity)
    reason = {
        ConsistencyVerdict.CONSISTENT.value: "differences are formatting only",
        ConsistencyVerdict.POTENTIAL_INCONSISTENCY.value: (
            "addresses overlap but differ in substance"
        ),
        ConsistencyVerdict.INCONSISTENT.value: "addresses do not correspond",
    }[verdict]
    return Comparison(similarity, verdict, reason)


def compare_identifiers(a: str | None, b: str | None) -> Comparison:
    """Identifiers are exact-match by nature. No bands, no interpretation."""
    if not a or not b:
        return Comparison(0.0, ConsistencyVerdict.CONSISTENT.value, "nothing to compare")
    ia, ib = normalize_identifier(a), normalize_identifier(b)
    if ia == ib:
        return Comparison(1.0, ConsistencyVerdict.CONSISTENT.value, "exact match")
    return Comparison(
        0.0, ConsistencyVerdict.INCONSISTENT.value, "identifiers differ"
    )
