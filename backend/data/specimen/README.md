# Specimen Bidder Document Sets — SIH 2026 / PS SIH26100

Synthetic test fixtures for a tender-document verification prototype.
Six bidder submissions against tender **GEM/2026/B/4471902** —
*CPCL Industrial Equipment Procurement 2026*.

All companies, people, banks and OEMs are fictitious. Every page carries a
**SPECIMEN — SYNTHETIC TEST DATA — NOT A VALID DOCUMENT** watermark and banner.
Aadhaar numbers use the reserved 0/1 leading-digit range that UIDAI never
issues, so they carry a correct Verhoeff digit but cannot correspond to a real
person.

## Contents

```
pdfs/                    72 PDFs — 6 datasets × 12 document types
manifest.csv/.json       per-dataset identifier table + declared defect
verification-report.json machine-readable pass/fail per check
validators.py            Verhoeff, GSTIN mod-36, PAN, CIN, Udyam validators
datasets.py              the six datasets and where the defects are injected
render.py                PDF layout helper (watermark is not optional)
generate.py              rebuilds all 72 PDFs
verify.py                re-extracts text and re-runs every check
```

## Datasets

| # | Company | Status |
|---|---------|--------|
| d1 | ABC Industrial Systems Pvt Ltd | fully correct |
| d2 | XYZ Electromech Pvt Ltd | fully correct |
| d3 | PQR Engineering Works Pvt Ltd | fully correct |
| d4 | LMN Power Solutions Pvt Ltd | **GSTIN mod-36 check character wrong** |
| d5 | DEF Techno Equipments Pvt Ltd | **PAN card shows stale legal name** |
| d6 | GHI Automation Pvt Ltd | **Aadhaar Verhoeff check digit wrong** |
| d7 | Sterling Hydro Systems Pvt Ltd | legal name written three ways → `VARIATION` |
| d8 | Meridian Process Controls Pvt Ltd | address written three ways → `VARIATION` |
| d9 | Orion Thermal Engineering Pvt Ltd | signatory absent from GST director list → `INCONSISTENT` |
| d10 | Vertex Fluid Systems Pvt Ltd | GSTIN↔PAN and GSTIN↔CIN state break → `INCONSISTENT` |

In d4–d6 everything unrelated to the assigned defect is correct and consistent,
so a flag is attributable to exactly one field.

**d7–d10 are different in kind.** Every identifier is individually valid and
every threshold is met, so a document-at-a-time pipeline finds nothing. The
irregularity is a *disagreement between documents*, visible only to a
reconciliation pass. `verify.py` therefore runs two passes:

| Pass | Sees | Result for d7–d10 |
|------|------|-------------------|
| 1. per-document | format, own checksum, thresholds | all clean |
| 2. cross-document | same field across documents | the defect |

Verdicts: `CONSISTENT`, `VARIATION` (differences reduce away under
normalisation — suffix dropped, abbreviated, PIN omitted),
`POTENTIAL_INCONSISTENCY` (related but not reducible — needs a human),
`INCONSISTENT` (a real conflict). Each manifest row carries a
`cross_document_defect` of `{dimension, documents_involved, expected_verdict}`.

Note that d5's PAN-name defect surfaces in *both* passes: as a field check in
pass 1 and as a `POTENTIAL_INCONSISTENCY` on `legal_name` in pass 2. That
contrast against d7's `VARIATION` is worth a slide — same dimension, different
severity.

## Document types

`contract`, `aadhaar`, `pan`, `gst-certificate`, `udyam`, `incorporation`,
`epfo-esic`, `oem-authorisation`, `local-content`, `turnover`, `experience`,
`bank-mandate` — named `d{1-6}-{doctype}.pdf`.

## Usage

```bash
pip install reportlab          # only needed to regenerate
python3 verify.py              # extract text, re-run all checks
python3 generate.py            # rebuild the PDFs
```

`validators.py` is plain stdlib — import it straight into your pipeline:

```python
from validators import validate_gstin, validate_aadhaar, validate_pan

validate_gstin("24AAACL4444C1Z2")   # (False, "mod-36 checksum failed ...")
validate_aadhaar("011002203319")    # (True,  "Verhoeff OK ...")
validate_pan("AAACA1111C", expect_holder_type="C")
```

## Adding your own defects

Add a branch in `datasets.py::_build` and a case in the `expected_fail` map in
`verify.py`. Useful next ones: turnover below ₹5 crore, experience under 5
years, local content under 50%, EPFO status dormant, OEM letter excluding a
line item, expired OEM authorisation, GSTIN state code disagreeing with the
CIN state, signatory not listed among the directors.
