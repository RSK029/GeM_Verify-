"""Extraction must recover every identifier in every specimen document exactly.

This is the regression suite for the parsing layer. It runs the real extraction
module over all 72 specimen PDFs and compares each field against manifest.json,
which is the dataset's own ground truth.

Run:  pytest -q          (from backend/)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import SPECIMEN_DIR
from app.models import DocumentType
from app.verification import extraction

MANIFEST = json.loads((SPECIMEN_DIR / "manifest.json").read_text())

#: extracted field -> manifest key, per document type.
EXPECTED = {
    DocumentType.CONTRACT: {
        "pan": "pan", "gstin": "gstin", "cin": "cin", "udyam_number": "udyam",
        "company_name": "company", "signatory": "signatory",
    },
    DocumentType.AADHAAR: {
        "aadhaar_number": "aadhaar", "signatory": "signatory", "company_name": "company",
    },
    # pan_card_name, not company: d5's defect is precisely that they differ.
    DocumentType.PAN: {"pan": "pan", "company_name": "pan_card_name"},
    DocumentType.GST_CERTIFICATE: {"gstin": "gstin", "company_name": "company"},
    DocumentType.UDYAM: {
        "udyam_number": "udyam", "company_name": "company", "pan": "pan", "gstin": "gstin",
    },
    DocumentType.INCORPORATION: {"cin": "cin", "company_name": "company", "pan": "pan"},
    DocumentType.EPFO_ESIC: {
        "establishment_code": "epfo_code", "company_name": "company",
        "pan": "pan", "esic_code": "esic_code",
    },
    DocumentType.OEM_AUTHORISATION: {
        "company_name": "company", "pan": "pan", "gstin": "gstin",
    },
    DocumentType.LOCAL_CONTENT: {
        "company_name": "company", "pan": "pan", "gstin": "gstin",
        "local_content_pct": "local_content_pct",
    },
    DocumentType.TURNOVER: {
        "company_name": "company", "pan": "pan", "gstin": "gstin", "cin": "cin",
        "turnover_cr": "turnover_fy2024_25_cr",
    },
    # The experience statement's letterhead carries CIN and GSTIN but no PAN.
    DocumentType.EXPERIENCE: {
        "company_name": "company", "gstin": "gstin", "experience_years": "experience_years",
    },
    DocumentType.BANK_MANDATE: {"company_name": "company", "pan": "pan", "gstin": "gstin"},
}

CASES = [(row["dataset"], dt) for row in MANIFEST for dt in DocumentType]
ROWS = {row["dataset"]: row for row in MANIFEST}

#: Where a dataset's *point* is that a document deliberately disagrees with the
#: manifest, the manifest is not the expected value — the variant is.
#:
#: d7 injects a legal-name variation: its Udyam certificate drops the corporate
#: suffix and its bank mandate abbreviates it. Asserting equality with the
#: canonical name there would be asserting that the defect is absent. These
#: strings are pinned exactly, so a regression in extraction still fails.
OVERRIDES: dict[tuple[str, DocumentType], dict[str, str]] = {
    ("d7", DocumentType.UDYAM): {"company_name": "Sterling Hydro Systems"},
    ("d7", DocumentType.BANK_MANDATE): {
        "company_name": "Sterling Hydro Systems Pvt. Ltd"
    },
}


def _pdf(dataset: str, doc_type: DocumentType) -> Path:
    return SPECIMEN_DIR / "pdfs" / f"{dataset}-{doc_type.slug}.pdf"


@pytest.mark.parametrize("dataset,doc_type", CASES, ids=lambda v: str(v))
def test_fields_match_manifest(dataset: str, doc_type: DocumentType):
    path = _pdf(dataset, doc_type)
    assert path.exists(), f"specimen missing: {path.name}"

    fields = extraction.extract(path, doc_type)

    overrides = OVERRIDES.get((dataset, doc_type), {})

    for field, manifest_key in EXPECTED[doc_type].items():
        if field in overrides:
            expected, source = overrides[field], "this document deliberately reads"
        else:
            expected, source = str(ROWS[dataset][manifest_key]).strip(), "manifest says"
        assert fields.get(field) == expected, (
            f"{dataset}/{doc_type.value}: {field} was {fields.get(field)!r}, "
            f"{source} {expected!r}"
        )


@pytest.mark.parametrize("dataset,doc_type", CASES, ids=lambda v: str(v))
def test_no_missing_expected_fields(dataset: str, doc_type: DocumentType):
    fields = extraction.extract(_pdf(dataset, doc_type), doc_type)
    assert extraction.missing_fields(doc_type, fields) == []


def test_injected_name_variations_are_read_verbatim():
    """Extraction must report what the document actually says, not a tidied
    version. d7's whole purpose is that these three spellings differ."""
    udyam = extraction.extract(_pdf("d7", DocumentType.UDYAM), DocumentType.UDYAM)
    bank = extraction.extract(_pdf("d7", DocumentType.BANK_MANDATE), DocumentType.BANK_MANDATE)
    gst = extraction.extract(_pdf("d7", DocumentType.GST_CERTIFICATE), DocumentType.GST_CERTIFICATE)

    assert gst["company_name"] == "Sterling Hydro Systems Private Limited"
    assert udyam["company_name"] == "Sterling Hydro Systems"
    assert bank["company_name"] == "Sterling Hydro Systems Pvt. Ltd"
    assert len({gst["company_name"], udyam["company_name"], bank["company_name"]}) == 3


def test_watermark_is_stripped():
    """The rotated SPECIMEN watermark must not bleed into extracted values.

    Without the rotation filter, pdfplumber returns 'SIDCO InduNstrial Estate'
    for this address — a silently corrupted field.
    """
    fields = extraction.extract(_pdf("d1", DocumentType.GST_CERTIFICATE), DocumentType.GST_CERTIFICATE)
    assert fields["address"] == (
        "Plot 14, SIDCO Industrial Estate, Ambattur, Chennai, Tamil Nadu - 600098"
    )
    assert "InduNstrial" not in fields["address"]


def test_oem_coverage_is_read_from_the_item_table():
    """'No item ... is excluded' must not be read as an exclusion."""
    fields = extraction.extract(
        _pdf("d1", DocumentType.OEM_AUTHORISATION), DocumentType.OEM_AUTHORISATION
    )
    assert fields["covers_all_items"] == "YES"
    assert fields["items_excluded"] == "0"
