"""Structural relationships between identifiers.

Some facts are not properties of a single field but of the relation between two.
A GSTIN can carry a perfectly valid mod-36 check character *for the GSTIN as
written* while embedding a PAN that is not the bidder's. A CIN can be
well-formed while naming a different state from the GSTIN. A signatory's Aadhaar
can pass its Verhoeff check while that person is not on the company's board.

None of these is detectable by validating fields one at a time, and none needs a
language model. They are exact comparisons over structure.

State codes: a GSTIN begins with a two-digit state code, a CIN carries a
two-letter one in positions 7-8. The map below relates them.
"""

from __future__ import annotations

import re

from .normalize import normalize_identifier, normalize_name

#: GST numeric state code -> MCA two-letter state code.
GST_TO_MCA_STATE = {
    "01": "JK", "02": "HP", "03": "PB", "04": "CH", "05": "UR", "06": "HR",
    "07": "DL", "08": "RJ", "09": "UP", "10": "BR", "11": "SK", "12": "AR",
    "13": "NL", "14": "MN", "15": "MZ", "16": "TR", "17": "ML", "18": "AS",
    "19": "WB", "20": "JH", "21": "OR", "22": "CT", "23": "MP", "24": "GJ",
    "26": "DN", "27": "MH", "29": "KA", "30": "GA", "31": "LD", "32": "KL",
    "33": "TN", "34": "PY", "35": "AN", "36": "TG", "37": "AP", "38": "LA",
}

_CIN_RE = re.compile(r"^([UL])(\d{5})([A-Z]{2})(\d{4})([A-Z]{3})(\d{6})$")


def gstin_embedded_pan(gstin: str | None) -> str | None:
    """Characters 3-12 of a GSTIN are the registered person's PAN."""
    raw = normalize_identifier(gstin or "")
    return raw[2:12] if len(raw) == 15 else None


def gstin_state(gstin: str | None) -> str | None:
    raw = normalize_identifier(gstin or "")
    return raw[:2] if len(raw) >= 2 else None


def cin_state(cin: str | None) -> str | None:
    match = _CIN_RE.match(normalize_identifier(cin or ""))
    return match.group(3) if match else None


def pan_matches_gstin(pan: str | None, gstin: str | None) -> tuple[bool, str] | None:
    """None when there is nothing to compare."""
    embedded = gstin_embedded_pan(gstin)
    declared = normalize_identifier(pan or "")
    if not embedded or not declared:
        return None
    if embedded == declared:
        return True, f"GSTIN embeds the declared PAN {declared}"
    return False, (
        f"GSTIN embeds PAN {embedded}, but the PAN card reads {declared}. "
        "Both identifiers are individually valid; the relationship between them is not."
    )


def gstin_agrees_with_cin_state(gstin: str | None, cin: str | None) -> tuple[bool, str] | None:
    gst_code = gstin_state(gstin)
    mca_code = cin_state(cin)
    if not gst_code or not mca_code:
        return None
    expected = GST_TO_MCA_STATE.get(gst_code)
    if expected is None:
        return None
    if expected == mca_code:
        return True, f"GSTIN and CIN both register the company in {expected}"
    return False, (
        f"GSTIN state code {gst_code} ({expected}) does not agree with the "
        f"CIN state code {mca_code}"
    )


def signatory_is_a_director(
    signatory: str | None, directors: list[str] | str | None
) -> tuple[bool, str] | None:
    """Membership, not similarity: is this person on the board at all?"""
    if not signatory or not directors:
        return None
    if isinstance(directors, str):
        directors = [d.strip() for d in directors.split("|") if d.strip()]
    if not directors:
        return None

    target = normalize_name(signatory)
    listed = {normalize_name(d) for d in directors}
    if target in listed:
        return True, "signatory is listed among the company's directors"

    # Tolerate an initial or a dropped middle name before escalating.
    target_tokens = set(target.split())
    for candidate in listed:
        tokens = set(candidate.split())
        if target_tokens and (target_tokens <= tokens or tokens <= target_tokens):
            return True, "signatory matches a listed director allowing for a shortened name"

    return False, (
        f"{signatory} is not among the directors on record "
        f"({', '.join(directors)})"
    )
