"""The verification engine must reproduce the dataset's ground truth.

`verification-report.json`, the `defect` column and the `cross_document_defect`
object in `manifest.json` are the dataset's own statement of what is wrong with
each bidder. This suite asserts that our engine reaches the same conclusions —
and, just as importantly, that it does **not** flag the clean bidders.

Ten datasets in two families:

  d1-d3   clean
  d4-d6   a field-level defect (checksum, stale name)
  d7-d10  every field valid; the defect exists only *between* documents

d7-d10 are the ones that justify the product. Pass 1 finds nothing in any of
them.

Run:  pytest -q          (from backend/)
"""

from __future__ import annotations

import json

import pytest

from app.config import SPECIMEN_DIR, settings
from app.models import CheckResult, ConsistencyVerdict, DocumentStatus, DocumentType
from app.verification import consistency, extraction, normalize, rules
from app.verification.registry import RegistryGateway, RegistryRecord
from app.verification.validators import gstin_check_char

TENDER = "GEM/2026/B/4471902"
MANIFEST = {r["dataset"]: r for r in json.loads((SPECIMEN_DIR / "manifest.json").read_text())}

#: Which check must flag each injected defect.
DEFECT_CHECK = {
    "none": None,
    "gstin_checksum": "GSTIN_CHECKSUM",
    "pan_name_mismatch": "PAN_NAME_MATCH",
    "aadhaar_checksum": "AADHAAR_VERHOEFF",
}


class _Doc:
    """Stands in for a Document row; the engine only reads these attributes."""

    def __init__(self, index, doc_type, fields, error):
        self.id = index
        self.document_type = doc_type.value
        self.extracted_fields = fields
        self.extraction_error = error
        self.status = DocumentStatus.PENDING.value
        self.results = []


class _Bid:
    def __init__(self, documents):
        self.id = 1
        self.active_documents = documents
        self.tender = type("T", (), {"tender_number": TENDER})()


class _Gateway(RegistryGateway):
    """Mirrors app.seed.seed: registries derived from the specimen documents,
    holding the *correct* value wherever a defect was injected."""

    def __init__(self):
        self.pans, self.gsts, self.udyams = {}, {}, {}
        self.cins, self.oems, self.epfos, self.fins = {}, {}, {}, {}
        for row in MANIFEST.values():
            ds, pan, company = row["dataset"], row["pan"], row["company"]
            gst = extraction.extract(_pdf(ds, DocumentType.GST_CERTIFICATE), DocumentType.GST_CERTIFICATE)
            inc = extraction.extract(_pdf(ds, DocumentType.INCORPORATION), DocumentType.INCORPORATION)
            udy = extraction.extract(_pdf(ds, DocumentType.UDYAM), DocumentType.UDYAM)
            address = gst.get("address", "")
            gstin = row["gstin"]
            if row["defect"] == "gstin_checksum":
                gstin = gstin[:14] + gstin_check_char(gstin[:14])
            self.pans[pan] = {"pan": pan, "name": company, "holder_type": "C", "status": "ACTIVE"}
            self.gsts[gstin] = {"gstin": gstin, "legal_name": company, "pan": pan,
                                "address": address, "status": "ACTIVE"}
            self.udyams[row["udyam"]] = {"udyam_number": row["udyam"], "business_name": company,
                                         "pan": pan, "address": udy.get("address", address),
                                         "status": "ACTIVE"}
            self.cins[row["cin"]] = {"cin": row["cin"], "company_name": company, "pan": pan,
                                     "registered_address": inc.get("address", address),
                                     "directors": [], "status": "ACTIVE"}
            self.oems[pan] = {"authorization_id": f"OEM-{ds.upper()}", "oem_name": "OEM",
                              "dealer_name": company, "dealer_pan": pan,
                              "tender_number": TENDER, "valid_until": None, "status": "ACTIVE"}
            self.epfos[row["epfo_code"]] = {"establishment_code": row["epfo_code"],
                                            "establishment_name": company, "pan": pan,
                                            "esic_code": row["esic_code"], "status": "ACTIVE"}
            self.fins[pan] = {"pan": pan, "turnover_cr": float(row["turnover_fy2024_25_cr"])}

    @staticmethod
    def _rec(source, table, key):
        row = table.get((key or "").upper())
        return RegistryRecord(source, bool(row), row or {})

    def pan(self, v): return self._rec("PAN_REGISTRY", self.pans, v)
    def gstin(self, v): return self._rec("GST_REGISTRY", self.gsts, v)
    def udyam(self, v): return self._rec("UDYAM_REGISTRY", self.udyams, v)
    def company(self, v): return self._rec("COMPANY_REGISTRY", self.cins, v)
    def epfo(self, v): return self._rec("EPFO_REGISTRY", self.epfos, v)
    def oem_for_dealer(self, dealer_pan, tender_number): return self._rec("OEM_REGISTRY", self.oems, dealer_pan)
    def financials(self, pan, financial_year="2024-25"): return self._rec("FINANCIAL_REGISTRY", self.fins, pan)


def _pdf(dataset, doc_type):
    return SPECIMEN_DIR / "pdfs" / f"{dataset}-{doc_type.slug}.pdf"


@pytest.fixture(scope="module")
def gateway():
    return _Gateway()


def _evaluate(dataset, gateway):
    documents = []
    for index, doc_type in enumerate(DocumentType, start=1):
        fields = extraction.extract(_pdf(dataset, doc_type), doc_type)
        missing = extraction.missing_fields(doc_type, fields)
        documents.append(
            _Doc(index, doc_type, fields, "Could not read: " + ", ".join(missing) if missing else None)
        )

    checks = []
    for document in documents:
        document_checks = rules.checks_for(document, gateway, TENDER)
        document.status = rules.status_for(document_checks)
        checks.extend(document_checks)

    report = consistency.analyse(_Bid(documents), gateway)
    return documents, checks, report


@pytest.mark.parametrize("dataset", sorted(MANIFEST))
def test_injected_defect_is_detected(dataset, gateway):
    _, checks, _ = _evaluate(dataset, gateway)
    expected = DEFECT_CHECK[MANIFEST[dataset]["defect"]]
    flagged = {
        c.check_type for c in checks
        if c.result in (CheckResult.FAIL.value, CheckResult.REVIEW.value)
    }
    if expected is None:
        assert flagged == set(), f"{dataset} is a clean dataset but raised {flagged}"
    else:
        assert expected in flagged, f"{dataset}: {expected} not among {flagged}"


@pytest.mark.parametrize("dataset", ["d1", "d2", "d3"])
def test_clean_datasets_are_fully_consistent(dataset, gateway):
    documents, _, report = _evaluate(dataset, gateway)
    assert all(d.status == DocumentStatus.VERIFIED.value for d in documents)
    assert report.flags == []
    assert consistency.worst_verdict(report) == ConsistencyVerdict.CONSISTENT.value


CROSS_DOC = [d for d in sorted(MANIFEST) if MANIFEST[d].get("cross_document_defect")]


@pytest.mark.parametrize("dataset", CROSS_DOC)
def test_cross_document_defect_is_caught_at_the_right_severity(dataset, gateway):
    """The dataset states the dimension and the verdict it expects. We must
    agree on both."""
    _, _, report = _evaluate(dataset, gateway)
    expected = MANIFEST[dataset]["cross_document_defect"]["expected_verdict"]
    verdicts = {f.verdict for f in report.flags}
    assert expected in verdicts, (
        f"{dataset}: expected a {expected} flag, got {verdicts or 'none'}"
    )


@pytest.mark.parametrize(
    "dataset", [d for d in CROSS_DOC if MANIFEST[d]["defect"] == "none"]
)
def test_pure_cross_document_defects_pass_every_individual_check(dataset, gateway):
    """The whole argument for the consistency layer: these bids are flawless
    document by document. Only reconciliation sees the problem."""
    documents, checks, report = _evaluate(dataset, gateway)
    escalated = [
        c.check_type
        for c in checks
        if c.result in (CheckResult.FAIL.value, CheckResult.REVIEW.value)
    ]
    assert escalated == [], f"{dataset} should pass pass 1 cleanly, got {escalated}"
    assert all(d.status == DocumentStatus.VERIFIED.value for d in documents)
    assert report.flags, f"{dataset} must still raise a cross-document flag"


@pytest.mark.parametrize("dataset", ["d4", "d5", "d6"])
def test_defective_datasets_escalate_but_never_auto_reject(dataset, gateway):
    documents, checks, report = _evaluate(dataset, gateway)
    assert any(
        d.status in (DocumentStatus.FAILED.value, DocumentStatus.REVIEW.value) for d in documents
    ) or report.flags, f"{dataset} should raise something"
    # The pipeline escalates to a human; rejection is never automatic.
    assert rules.score(checks) > 0


def test_pan_name_defect_surfaces_as_a_cross_document_flag(gateway):
    """d5's PAN card carries a stale legal name while every other document
    agrees — exactly the case per-document checking alone would miss."""
    _, _, report = _evaluate("d5", gateway)
    identity = next(d for d in report.dimensions if d.dimension == "IDENTITY")
    divergent = [o for o in identity.observations if o.verdict != ConsistencyVerdict.CONSISTENT.value]
    assert len(divergent) == 1
    assert divergent[0].document_type == DocumentType.PAN.value
    assert identity.canonical_source == "PAN_REGISTRY"


def test_corrupt_gstin_is_consistent_across_documents_but_fails_its_checksum(gateway):
    """d4 repeats the same bad GSTIN everywhere, so cross-document agreement is
    perfect. Only the deterministic checksum catches it — which is precisely why
    both layers exist."""
    _, checks, report = _evaluate("d4", gateway)
    registration = next(d for d in report.dimensions if d.dimension == "REGISTRATION")
    assert registration.verdict == ConsistencyVerdict.CONSISTENT.value
    checksum = next(c for c in checks if c.check_type == "GSTIN_CHECKSUM")
    assert checksum.result == CheckResult.FAIL.value


# --------------------------------------------------------------------------
# the normalisation rules the verdicts rest on
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("ABC Industrial Systems Private Limited", "ABC Industrial Systems Pvt. Ltd.", "CONSISTENT"),
        # An *abbreviated* suffix normalises to the same string and is clean;
        # an *omitted* one is surfaced as a benign variation rather than hidden.
        ("ABC Industrial Systems Private Limited", "ABC Industrial Systems", "VARIATION"),
        ("M/s Ram Singh", "RAM SINGH", "CONSISTENT"),
        ("Ram Singh", "Ram", "VARIATION"),
        ("Ram Singh", "R. Singh", "VARIATION"),
        ("Ram Singh", "John Kumar", "INCONSISTENT"),
    ],
)
def test_name_bands(a, b, expected):
    assert normalize.compare_names(a, b).verdict == expected


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("123 MG Road, New Delhi, Delhi - 110001", "123, M.G. Road, Delhi 110001", "CONSISTENT"),
        (
            "Plot 22, MIDC Industrial Area, Andheri East, Mumbai, Maharashtra - 400093",
            "Plot 22, M.I.D.C. Indl. Area, Andheri (E), Mumbai 400093",
            "CONSISTENT",
        ),
        (
            "Plot 14, SIDCO Industrial Estate, Ambattur, Chennai - 600098",
            "B-42, MIDC Industrial Area, Bhosari, Pune - 411026",
            "INCONSISTENT",
        ),
    ],
)
def test_address_bands(a, b, expected):
    assert normalize.compare_addresses(a, b).verdict == expected


def test_identifiers_never_use_fuzzy_bands():
    """A near-miss identifier is a mismatch, not a variation."""
    assert normalize.compare_identifiers("AAACD5555C", "AAACD5555D").verdict == "INCONSISTENT"
    assert normalize.compare_identifiers("33AAACA1111C1ZV", "33aaaca1111c1zv").similarity == 1.0


def test_similarity_is_deterministic():
    """Same inputs, same score — the demo must not drift between runs."""
    first = normalize.compare_names("Ram Singh", "Ram").similarity
    for _ in range(20):
        assert normalize.compare_names("Ram Singh", "Ram").similarity == first


def test_thresholds_are_configurable_not_hardcoded():
    assert 0 < settings.SIM_POTENTIAL < settings.SIM_CONSISTENT <= 1.0


# --------------------------------------------------------------------------
# structural relationships between identifiers
# --------------------------------------------------------------------------


def test_gstin_embedded_pan_relation():
    """d10's case: both identifiers individually valid, the relation broken."""
    from app.verification import linkage

    ok, _ = linkage.pan_matches_gstin("AAACV3434C", "27AAACV3434C1ZP")
    assert ok is True

    broken = linkage.pan_matches_gstin("AAACV1212C", "27AAACV3434C1ZP")
    assert broken[0] is False
    assert "AAACV3434C" in broken[1] and "AAACV1212C" in broken[1]


def test_gstin_and_cin_must_agree_on_state():
    from app.verification import linkage

    assert linkage.gstin_agrees_with_cin_state("33AAACA1111C1ZV", "U29253TN2014PTC101234")[0]
    mismatch = linkage.gstin_agrees_with_cin_state("27AAACV3434C1ZP", "U29253KA2014PTC101234")
    assert mismatch[0] is False
    assert "MH" in mismatch[1] and "KA" in mismatch[1]


def test_signatory_must_appear_on_the_board():
    """d9's case: a valid Aadhaar for someone who is not a director."""
    from app.verification import linkage

    directors = "Harish Malhotra | Sneha Kulkarni"
    assert linkage.signatory_is_a_director("Deepak Ranganathan", directors)[0] is False
    assert linkage.signatory_is_a_director("Harish Malhotra", directors)[0] is True
    # A shortened form of a listed director is not a finding.
    assert linkage.signatory_is_a_director("Harish", directors)[0] is True


def test_missing_inputs_produce_no_finding():
    """Absent data is not evidence of a problem."""
    from app.verification import linkage

    assert linkage.pan_matches_gstin(None, "27AAACV3434C1ZP") is None
    assert linkage.gstin_agrees_with_cin_state("27AAACV3434C1ZP", None) is None
    assert linkage.signatory_is_a_director("Someone", None) is None


def test_stale_name_lands_in_review_not_rejection():
    """"DEF Technocraft" vs "DEF Techno Equipments" share a distinctive token,
    so they are a possible rename — review, not a different company."""
    assert (
        normalize.compare_names(
            "DEF Technocraft Private Limited", "DEF Techno Equipments Private Limited"
        ).verdict
        == "POTENTIAL_INCONSISTENCY"
    )
