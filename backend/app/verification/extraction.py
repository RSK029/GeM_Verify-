"""Document text extraction and structured field parsing.

Two things matter here.

**The watermark.** Every specimen PDF carries a rotated SPECIMEN watermark and a
rotated side banner. Their glyphs sit in the same content stream as the real
text, so a naive ``page.extract_text()`` interleaves them into the values:

    Address ... Plot 14, SIDCO InduNstrial Estate ...
    Period of Validity (To) : Not AMpplicable

Silently corrupted fields would produce confident wrong verdicts, which is worse
than failing to parse at all. Rotated glyphs are identifiable by their text
matrix, so :func:`page_text` drops any character whose matrix has a rotation
component and keeps only upright text.

**The labels.** Certificate PDFs lay out as ``Label : Value``, but right-aligned
values occasionally push the colon into the label ("Number of Subscribers (as on
31/08/2026:) 47"). Matching is therefore done on a punctuation-stripped form of
the line while the value is sliced out of the original, so a stray colon cannot
break a field.

No OCR is required: these are text-layer PDFs. :func:`page_text` falls back to an
empty string for an image-only page, and the caller records an extraction error
rather than guessing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence

import pdfplumber

from ..models import DocumentType

# --------------------------------------------------------------------------
# text layer
# --------------------------------------------------------------------------

_ROTATION_EPS = 1e-6


def _is_upright(obj: dict) -> bool:
    if obj["object_type"] != "char":
        return True
    matrix = obj.get("matrix")
    if not matrix:
        return True
    # matrix is (a, b, c, d, e, f); b and c carry rotation/skew.
    return abs(matrix[1]) < _ROTATION_EPS and abs(matrix[2]) < _ROTATION_EPS


def page_text(path: str | Path) -> str:
    """Full document text with rotated watermark glyphs removed."""
    out: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            upright = page.filter(_is_upright)
            out.append(upright.extract_text() or "")
    return "\n".join(out)


def lines_of(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


# --------------------------------------------------------------------------
# label / value matching
# --------------------------------------------------------------------------

_SQUASH = re.compile(r"[^a-z0-9]+")


def _squash_with_map(line: str) -> tuple[str, list[int]]:
    """Lowercased alphanumeric-only form of *line*, plus original indices."""
    chars: list[str] = []
    indices: list[int] = []
    for i, ch in enumerate(line):
        if ch.isalnum():
            chars.append(ch.lower())
            indices.append(i)
    return "".join(chars), indices


def _squash(text: str) -> str:
    return _SQUASH.sub("", text.lower())


def find_field(lines: Sequence[str], labels: Iterable[str]) -> str | None:
    """Return the value following the first matching label.

    Two tiers. First every label is tried as a line *prefix*, which is the
    normal certificate layout and the least ambiguous. Only if all of them miss
    is each label retried *anywhere* in the line, which rescues layouts that
    prepend something to the label — "PHOTO Address Unit 4, ..." on an identity
    card, for instance.

    ``labels`` is tried in order within each tier, so callers put the most
    specific label first ("Name of Holder" before "Name") to stop a shorter
    label swallowing a longer one.
    """
    labels = list(labels)
    for anywhere in (False, True):
        for label in labels:
            target = _squash(label)
            if not target:
                continue
            for line in lines:
                squashed, indices = _squash_with_map(line)
                if anywhere:
                    position = squashed.find(target)
                    if position < 0:
                        continue
                    end = position + len(target)
                else:
                    if not squashed.startswith(target):
                        continue
                    end = len(target)
                if len(indices) <= end:
                    continue  # label with nothing after it
                # The label must end where a word ends. Without this, "Tender
                # Reference" matches inside "for the tender referenced above"
                # and returns the stray "d" that follows.
                #
                # The test is against the very next character in the *original*
                # line, not the next alphanumeric one: "PAN : AAACA1111C" has a
                # separator there, while "referenced" does not.
                after = indices[end - 1] + 1
                if after < len(line) and line[after].isalnum():
                    continue
                value = line[indices[end] :].lstrip(" :\t-").strip()
                if value:
                    return value
    return None


def find_regex(text: str, pattern: str, group: int = 1) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(group).strip() if match else None


def _clean_name(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip(" .,")
    return value or None


def _identifier(value: str | None, pattern: str) -> str | None:
    """Pull a structured identifier out of whatever the label matched.

    A label found mid-sentence takes the rest of the line with it — "PAN
    ZZZFP0000Z and GSTIN 07ZZZFP0000Z1ZX, having its registered office at..."
    is a real example. An identifier has a shape, so the shape is what gets
    kept and everything around it discarded.
    """
    if not value:
        return None
    match = re.search(pattern, value.upper())
    return match.group(0) if match else None


def _first_number(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
    return match.group(0) if match else None


#: Designations that terminate a person's name in a table row. Without this the
#: name pattern runs on into "Managing Director Tamil Nadu", because every token
#: in the row is capitalised.
_DESIGNATION = (
    r"(?:Managing|Whole-time|Wholetime|Executive|Additional|Independent|Nominee)?\s*"
    r"(?:Director|Partner|Proprietor|Signatory|Secretary)"
)


def _table_rows(lines: Sequence[str], header_contains: str) -> list[str]:
    """Return the numbered rows that follow a table header line."""
    rows: list[str] = []
    started = False
    for line in lines:
        if not started:
            if _squash(header_contains) in _squash(line):
                started = True
            continue
        if re.match(r"^\d+\s+\S", line):
            rows.append(line)
        elif rows:
            break
    return rows


def _names_by_designation(lines: Sequence[str], header_contains: str) -> list[str]:
    """``Sl. Name Designation ...`` — name runs up to the designation token."""
    names = []
    for row in _table_rows(lines, header_contains):
        match = re.match(rf"^\d+\s+(.+?)\s+{_DESIGNATION}\b", row)
        if match:
            names.append(re.sub(r"\s+", " ", match.group(1)).strip())
    return names


def _names_by_din(lines: Sequence[str], header_contains: str) -> list[str]:
    """``Sl. Name DIN Designation`` — the 8-digit DIN terminates the name."""
    names = []
    for row in _table_rows(lines, header_contains):
        match = re.match(r"^\d+\s+(.+?)\s+\d{8}\b", row)
        if match:
            names.append(re.sub(r"\s+", " ", match.group(1)).strip())
    return names


# --------------------------------------------------------------------------
# per document type parsers
# --------------------------------------------------------------------------

#: A GeM tender reference is structured enough to find anywhere in a document,
#: which saves depending on any particular label wording.
_TENDER_RE = r"GEM/\d{4}/[A-Z]/\d+"
_PAN_RE = r"[A-Z]{5}[0-9]{4}[A-Z]"
_GSTIN_RE = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Zz][0-9A-Z]"
_CIN_RE = r"[LUu][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}"
_UDYAM_RE = r"UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}"


def _parse_contract(lines, text):
    return {
        "tender_number": find_field(lines, ["Tender Reference No.", "Tender Reference", "Tender Ref"])
        or find_regex(text, "(" + _TENDER_RE + ")"),
        "tender_title": find_field(lines, ["Tender Title", "Tender Description"]),
        "company_name": _clean_name(
            find_field(lines, ["Bidder (Legal Name)", "Bidder Legal Name", "Bidder Name", "Bidder"])
        ),
        "address": find_field(lines, ["Bidder Address", "Registered Address", "Registered Office"]),
        "gstin": _identifier(find_field(lines, ["GSTIN"]), _GSTIN_RE),
        "pan": _identifier(find_field(lines, ["PAN"]), _PAN_RE),
        "cin": _identifier(find_field(lines, ["CIN"]), _CIN_RE),
        "udyam_number": _identifier(find_field(lines, ["Udyam Registration No."]), _UDYAM_RE),
        "signatory": _clean_name(find_field(lines, ["Authorised Signatory"])),
        "designation": find_field(lines, ["Designation"]),
    }


def _parse_aadhaar(lines, text):
    return {
        "signatory": _clean_name(find_field(lines, ["Name"])),
        "aadhaar_number": find_field(
            lines, ["Aadhaar Number (unformatted)", "Aadhaar Number", "Aadhaar No", "UID"]
        )
        # Some layouts print the number on its own line with no label at all.
        or find_regex(text, r"\b(\d{4}\s\d{4}\s\d{4})\b"),
        "father_name": _clean_name(find_field(lines, ["Father's Name"])),
        "date_of_birth": find_field(lines, ["Date of Birth"]),
        "address": find_field(lines, ["Address"]),
        # Anchored to the declaration sentence. An unanchored "of" would match
        # "Unique Identification Authority of India" in the letterhead.
        "company_name": _clean_name(
            find_regex(text, r"\bof\s+([^,]+?),\s*confirm that the identity")
            or find_regex(text, r"authorised signatory of\s+(.+?)\s*$")
        ),
        "designation": find_field(lines, ["Designation"]),
    }


def _parse_pan(lines, text):
    return {
        "pan": _identifier(find_field(lines, ["Permanent Account No.", "PAN"]), _PAN_RE),
        "company_name": _clean_name(
            find_field(lines, ["Name of Holder (as printed on card)", "Name"])
        ),
        "constitution": find_field(lines, ["Constitution"]),
        "holder_type": find_field(lines, ["Holder Type (4th character)"]),
        "date_of_incorporation": find_field(lines, ["Date of Incorporation"]),
    }


def _parse_gst(lines, text):
    directors = _names_by_designation(lines, "Sl. Name Designation Resident of State")
    return {
        "gstin": _identifier(find_field(lines, ["Registration Number (GSTIN)", "GSTIN"]), _GSTIN_RE),
        "company_name": _clean_name(find_field(lines, ["Legal Name"])),
        "trade_name": _clean_name(find_field(lines, ["Trade Name, if any", "Trade Name"])),
        "constitution": find_field(lines, ["Constitution of Business"]),
        "address": find_field(lines, ["Address of Principal Place of Business"]),
        "registration_date": find_field(lines, ["Date of Liability"]),
        "validity_to": find_field(lines, ["Period of Validity (To)"]),
        "registration_type": find_field(lines, ["Type of Registration"]),
        "directors": " | ".join(directors) if directors else None,
    }


def _parse_udyam(lines, text):
    return {
        "udyam_number": _identifier(find_field(lines, ["Udyam Registration Number"]), _UDYAM_RE),
        "company_name": _clean_name(find_field(lines, ["Name of Enterprise"])),
        "enterprise_type": find_field(lines, ["Type of Enterprise (FY 2024-25)", "Type of Enterprise"]),
        "major_activity": find_field(lines, ["Major Activity"]),
        "address": find_field(lines, ["Official Address of Enterprise", "Official Address"]),
        "pan": _identifier(find_field(lines, ["PAN of Enterprise"]), _PAN_RE),
        "gstin": _identifier(find_field(lines, ["GSTIN of Enterprise"]), _GSTIN_RE),
        "registration_date": find_field(lines, ["Date of Udyam Registration"]),
    }


def _parse_incorporation(lines, text):
    directors = _names_by_din(lines, "Sl. Name DIN Designation")
    return {
        "cin": _identifier(find_field(lines, ["Corporate Identity Number (CIN)", "CIN"]), _CIN_RE),
        # A Limited Liability Partnership has an LLPIN and no CIN at all.
        "llpin": find_field(lines, ["LLP Identification Number (LLPIN)", "LLPIN"]),
        "company_name": _clean_name(
            find_field(lines, ["Name of Company", "Name of the Entity", "Name of Entity"])
            or find_regex(text, r"certify that\s+(.+?)\s+is this day incorporated")
        ),
        "date_of_incorporation": find_field(lines, ["Date of Incorporation"]),
        "class_of_company": find_field(lines, ["Class of Company"]),
        "pan": _identifier(find_field(lines, ["Permanent Account Number (PAN)", "PAN"]), _PAN_RE),
        "address": find_field(lines, ["Registered Office", "Registered Office Address"]),
        "directors": " | ".join(directors) if directors else None,
    }


def _parse_epfo(lines, text):
    return {
        "establishment_code": find_field(
            lines, ["Establishment Code Number", "EPF Establishment Code", "Establishment Code"]
        ),
        "company_name": _clean_name(
            find_field(lines, ["Name of Establishment", "Name of the Establishment"])
        ),
        "address": find_field(lines, ["Address"]),
        "pan": _identifier(find_field(lines, ["PAN"]), _PAN_RE),
        "epfo_status": find_field(lines, ["Status", "Contribution Status", "Coverage Status"]),
        "esic_code": find_field(lines, ["ESIC Employer Code"]),
        "date_of_coverage": find_field(lines, ["Date of Coverage"]),
        "dues_outstanding": find_field(lines, ["Dues Outstanding"]),
    }


def _parse_oem(lines, text):
    dealer = find_regex(text, r"authorise\s+(.+?)\s*\(GSTIN") or find_regex(
        text, r"authorise\s+(.+?),\s*having\s+its\s+registered\s+office"
    )
    covered = bool(
        re.search(r"ALL line items .{0,80}without exception", text, re.IGNORECASE | re.DOTALL)
    )
    # Authority comes from the item table's Covered column, not from prose. The
    # undertakings paragraph contains "No item ... is excluded from this
    # authorisation", so a keyword search for "excluded" inverts the meaning.
    item_rows = _table_rows(lines, "Description of Item Quantity Covered")
    row_verdicts = [
        m.group(1).upper()
        for m in (re.search(r"\b(Yes|No)\s*$", r) for r in item_rows)
        if m
    ]
    excluded = "NO" in row_verdicts
    if row_verdicts:
        covered = covered or not excluded
    elif not covered:
        # No item table and no "covers all items" wording. That is unknown, not
        # excluded — silence is not a refusal, and reporting it as one accuses
        # the bidder of something the document does not say.
        covered = None
    return {
        "tender_number": find_field(lines, ["Tender Reference No.", "Tender Reference"])
        or find_regex(text, "(" + _TENDER_RE + ")"),
        "tender_title": find_field(lines, ["Tender Title"]),
        "oem_name": _clean_name(find_regex(text, r"\bWe,\s*(.+?),\s*being an established")),
        "company_name": _clean_name(dealer),
        "gstin": find_regex(text, r"\(GSTIN\s*(" + _GSTIN_RE + r")"),
        "pan": find_regex(text, r"PAN\s*(" + _PAN_RE + r")\)"),
        "items_covered": str(len(row_verdicts)) if row_verdicts else None,
        "items_excluded": str(row_verdicts.count("NO")) if row_verdicts else None,
        "covers_all_items": (
            None if covered is None else ("YES" if (covered and not excluded) else "NO")
        ),
        "valid_until": _clean_name(find_regex(text, r"valid until\s+(.+?)\.")),
        "date": find_field(lines, ["Date"]),
    }


def _parse_local_content(lines, text):
    return {
        "tender_number": find_field(lines, ["Tender Reference No.", "Tender Reference"])
        or find_regex(text, "(" + _TENDER_RE + ")"),
        # Some declarations are on the bidder's own letterhead, so the name is
        # the first line rather than a labelled field.
        "company_name": _clean_name(
            find_field(lines, ["Bidder", "Declarant"]) or (lines[0] if lines else None)
        ),
        "local_content_pct": _first_number(
            find_field(lines, ["Local Content Declared", "Local Content Offered", "Local Content"])
        ),
        "certified_local_content_pct": _first_number(
            find_field(lines, ["Local Content Percentage"])
        ),
        "supplier_classification": find_field(lines, ["Supplier Classification"]),
        "minimum_required_pct": _first_number(find_field(lines, ["Minimum Required"])),
        "requirement_met": find_field(lines, ["Requirement Met"]),
        "pan": find_regex(text, r"PAN\s*(" + _PAN_RE + r")"),
        "gstin": find_regex(text, r"GSTIN[:\s]*(" + _GSTIN_RE + r")"),
    }


def _parse_turnover(lines, text):
    return {
        "company_name": _clean_name(
            find_field(lines, ["Name of Company", "Name of Entity"])
            or find_regex(text, r"records of\s+(.+?),\s*holding PAN")
        ),
        "pan": _identifier(find_field(lines, ["PAN"]), _PAN_RE)
        or find_regex(text, r"holding PAN\s*(" + _PAN_RE + r")"),
        "gstin": _identifier(find_field(lines, ["GSTIN"]), _GSTIN_RE)
        or find_regex(text, r"GSTIN\s*(" + _GSTIN_RE + r")"),
        "cin": find_field(lines, ["CIN"]),
        "financial_year": find_field(lines, ["Financial Year Certified"]),
        "turnover_cr": _first_number(
            find_field(
                lines,
                [
                    "Turnover Certified for FY 2024-25",
                    "Turnover Certified",
                    "Average Annual Turnover (3 years)",
                    "Average Annual Turnover",
                ],
            )
        ),
        "minimum_required_cr": _first_number(
            find_field(lines, ["Minimum Turnover Required by Tender"])
        ),
        "tender_number": find_field(lines, ["Tender Reference No."]),
        "auditor": _clean_name(lines[1] if len(lines) > 1 else None),
    }


def _parse_experience(lines, text):
    return {
        "company_name": _clean_name(
            find_field(lines, ["Bidder", "Contractor", "Supplier"])
            or find_regex(text, r"certify that\s+(.+?),\s*having its registered office")
        ),
        "tender_number": find_field(lines, ["Tender Reference No.", "Tender Reference"])
        or find_regex(text, "(" + _TENDER_RE + ")"),
        "experience_years": _first_number(
            find_field(lines, ["Years of Relevant Experience", "Years of Experience"])
        ),
        "minimum_required_years": _first_number(find_field(lines, ["Minimum Required by Tender"])),
        "year_of_commencement": find_field(lines, ["Year of Commencement of Business"]),
        "requirement_met": find_field(lines, ["Requirement Met"]),
        "pan": find_regex(text, r"PAN[:\s]*(" + _PAN_RE + r")"),
        "gstin": find_regex(text, r"GSTIN[:\s]*(" + _GSTIN_RE + r")"),
    }


def _parse_bank_mandate(lines, text):
    return {
        "tender_number": find_field(lines, ["Tender Reference No."]),
        "company_name": _clean_name(
            find_field(lines, ["Name of Account Holder", "Account Holder Name", "Submitted By"])
        ),
        "bank_name": find_field(lines, ["Bank Name and Branch", "Bank Name"]),
        "account_number": find_field(lines, ["Account Number"]),
        "account_type": find_field(lines, ["Account Type"]),
        "ifsc": find_field(lines, ["IFSC"]),
        "micr": find_field(lines, ["MICR Code"]),
        "pan": _identifier(find_field(lines, ["PAN of Account Holder"]), _PAN_RE),
        "gstin": _identifier(find_field(lines, ["GSTIN of Account Holder"]), _GSTIN_RE),
    }


_PARSERS = {
    DocumentType.CONTRACT: _parse_contract,
    DocumentType.AADHAAR: _parse_aadhaar,
    DocumentType.PAN: _parse_pan,
    DocumentType.GST_CERTIFICATE: _parse_gst,
    DocumentType.UDYAM: _parse_udyam,
    DocumentType.INCORPORATION: _parse_incorporation,
    DocumentType.EPFO_ESIC: _parse_epfo,
    DocumentType.OEM_AUTHORISATION: _parse_oem,
    DocumentType.LOCAL_CONTENT: _parse_local_content,
    DocumentType.TURNOVER: _parse_turnover,
    DocumentType.EXPERIENCE: _parse_experience,
    DocumentType.BANK_MANDATE: _parse_bank_mandate,
}

#: Fields each document type is expected to yield. Used for a completeness
#: check — a missing field routes the document to REVIEW rather than FAIL,
#: because a parser gap is our problem, not the bidder's.
#:
#: A tuple nested inside means "any one of these will do". A Limited Liability
#: Partnership has an LLPIN and no CIN at all, so demanding a CIN would report a
#: permanent, unfixable gap against a perfectly valid entity.
EXPECTED_FIELDS: dict[DocumentType, tuple[str | tuple[str, ...], ...]] = {
    DocumentType.CONTRACT: ("tender_number", "company_name", "gstin", "pan", "signatory"),
    DocumentType.AADHAAR: ("signatory", "aadhaar_number", "address"),
    DocumentType.PAN: ("pan", "company_name"),
    DocumentType.GST_CERTIFICATE: ("gstin", "company_name", "address"),
    # PAN is not printed on every Udyam certificate.
    DocumentType.UDYAM: ("udyam_number", "company_name"),
    DocumentType.INCORPORATION: (("cin", "llpin"), "company_name", "pan"),
    DocumentType.EPFO_ESIC: ("establishment_code", "company_name", "epfo_status"),
    DocumentType.OEM_AUTHORISATION: ("tender_number", "oem_name", "company_name"),
    DocumentType.LOCAL_CONTENT: ("company_name", "local_content_pct"),
    DocumentType.TURNOVER: ("company_name", "pan", "turnover_cr"),
    DocumentType.EXPERIENCE: ("company_name", "experience_years"),
    DocumentType.BANK_MANDATE: ("company_name", "account_number", "ifsc"),
}


def extract(path: str | Path, document_type: DocumentType | str) -> dict[str, str]:
    """Extract structured fields from a document. Empty values are dropped."""
    doc_type = DocumentType(str(document_type))
    text = page_text(path)
    if not text.strip():
        raise ValueError(
            "No text layer found in this PDF. Scanned images are not supported "
            "in this prototype."
        )
    lines = lines_of(text)
    parser = _PARSERS.get(doc_type)
    if parser is None:
        return {}
    fields = parser(lines, text)
    return {k: v.strip() for k, v in fields.items() if isinstance(v, str) and v.strip()}


def missing_fields(document_type: DocumentType | str, fields: dict) -> list[str]:
    """Expected fields this document did not yield.

    An entry that is itself a tuple is satisfied by any one of its members.
    """
    doc_type = DocumentType(str(document_type))
    missing: list[str] = []
    for expected in EXPECTED_FIELDS.get(doc_type, ()):
        alternatives = expected if isinstance(expected, tuple) else (expected,)
        if not any(fields.get(name) for name in alternatives):
            missing.append(" or ".join(alternatives))
    return missing
