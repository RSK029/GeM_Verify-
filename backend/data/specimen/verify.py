"""
verify.py - Independent check of the generated specimen sets.

Two passes, deliberately separated:

  PASS 1  per-document verification. Each field is checked on its own terms:
          format, own checksum, threshold. This is what a document-at-a-time
          pipeline can see. d1-d3 and d7-d10 clear it completely; d4-d6 each
          fail exactly one field.

  PASS 2  cross-document reconciliation. The same field is collected from
          every document that carries it and the renderings are compared.
          This is the only pass that can see the d7-d10 defects.
"""

import re, subprocess, sys, os, json

from validators import (validate_aadhaar, validate_pan, validate_gstin,
                        validate_udyam, validate_cin, validate_name_match,
                        classify_names, classify_addresses, classify_signatory,
                        classify_gstin_pan, classify_gstin_cin_state, worst)
from datasets import DATASETS, DOC_TYPES, TENDER_REF, doc_name, doc_address

OUT = "pdfs"

RX = {
    "pan":     re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "gstin":   re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b"),
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "udyam":   re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b"),
    "cin":     re.compile(r"\b[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b"),
}

# Document types that carry a legal name / a registered address.
NAME_DOCS = ["contract", "gst-certificate", "pan", "udyam", "incorporation",
             "turnover", "bank-mandate"]
ADDR_DOCS = ["gst-certificate", "udyam", "turnover", "incorporation", "epfo-esic"]


def text_of(path):
    # Plain extraction, not -layout: in layout mode a wrapped value's
    # continuation line is re-columned next to the following label, which
    # breaks reading order for multi-line addresses.
    return subprocess.run(["pdftotext", path, "-"],
                          capture_output=True, text=True, check=True).stdout


def flat(s):
    """Normalise for presence-testing against an extracted text layer.

    Collapses whitespace so a wrapped PDF line compares as one string, and
    drops hyphens because pdftotext removes a hyphen sitting at a line break
    ('... Karnataka - 560058' comes back as '... Karnataka 560058')."""
    return " ".join(str(s).replace("-", " ").split())


def main():
    failures = []
    results = []

    for d in DATASETS:
        texts = {}
        for dt in DOC_TYPES:
            path = os.path.join(OUT, f"d{d['id']}-{dt}.pdf")
            t = text_of(path)
            if len(t.strip()) < 200:
                failures.append(f"d{d['id']}-{dt}: extracted only {len(t.strip())} chars")
            if "SPECIMEN" not in t:
                failures.append(f"d{d['id']}-{dt}: SPECIMEN marking missing from text layer")
            texts[dt] = t

        # ==================================================================
        # PASS 1 - per-document checks
        # ==================================================================
        # Note: GSTIN is checked for its OWN check character only, and CIN for
        # its own structure only. Whether the GSTIN embeds the declared PAN, and
        # whether its state agrees with the CIN, are relations between
        # documents and belong to pass 2.
        ok_pan,  m_pan  = validate_pan(d["pan"], expect_holder_type="C")
        ok_gst,  m_gst  = validate_gstin(d["gstin"])
        ok_aad,  m_aad  = validate_aadhaar(d["aadhaar"])
        ok_udy,  m_udy  = validate_udyam(d["udyam"])
        ok_cin,  m_cin  = validate_cin(d["cin"])
        ok_name, m_name = validate_name_match(d["company"], d["pan_name"])

        checks = {
            "PAN":            (ok_pan,  m_pan),
            "GSTIN":          (ok_gst,  m_gst),
            "Aadhaar":        (ok_aad,  m_aad),
            "Udyam":          (ok_udy,  m_udy),
            "CIN":            (ok_cin,  m_cin),
            "PAN name match": (ok_name, m_name),
        }

        checks["Turnover >= 5 cr"]    = (float(d["turnover_cr"]) >= 5.0,
                                         f"Rs. {d['turnover_cr']} crore")
        checks["Experience >= 5 yrs"] = (d["experience_yrs"] >= 5,
                                         f"{d['experience_yrs']} years")
        checks["Local content >= 50%"] = (d["local_content"] >= 50,
                                          f"{d['local_content']}%")
        checks["EPFO active"]  = ("ACTIVE" in texts["epfo-esic"], "status ACTIVE")
        checks["OEM covers all items"] = (
            TENDER_REF in texts["oem-authorisation"]
            and "without exception" in texts["oem-authorisation"],
            "tender ref quoted, no exclusions")

        # ---------- identifier consistency across the set ----------
        for key, rx in RX.items():
            vals = set()
            for dt, t in texts.items():
                for m in rx.findall(t):
                    vals.add(m.replace(" ", ""))
            if key == "aadhaar":
                vals = {v for v in vals if not v.startswith("9")}   # drop VID
            extra = vals - {d[key].replace(" ", "")}
            if extra:
                failures.append(f"d{d['id']}: {key} unexpected value(s) {sorted(extra)}")

        if d["defect"] != "pan_name_mismatch" and not ok_name:
            failures.append(f"d{d['id']}: PAN card name differs from company name")

        expected_fail = {
            "gstin_checksum": "GSTIN",
            "pan_name_mismatch": "PAN name match",
            "aadhaar_checksum": "Aadhaar",
        }.get(d["defect"])

        for name, (ok, msg) in checks.items():
            if name == expected_fail:
                if ok:
                    failures.append(f"d{d['id']}: {name} was supposed to FAIL but passed")
            elif not ok:
                failures.append(f"d{d['id']}: unexpected failure on {name} -- {msg}")

        # ==================================================================
        # PASS 2 - cross-document reconciliation
        # ==================================================================
        names = {dt: (d["pan_name"] if dt == "pan" else doc_name(d, dt))
                 for dt in NAME_DOCS}
        addrs = {dt: doc_address(d, dt) for dt in ADDR_DOCS}

        # every rendering must actually appear in that document's text layer
        for dt, v in list(names.items()) + list(addrs.items()):
            if flat(v) not in flat(texts[dt]):
                failures.append(f"d{d['id']}-{dt}: '{v}' not found in extracted text")

        findings = []

        v, why = classify_names(list(names.values()))
        if v != "CONSISTENT":
            findings.append({"dimension": "legal_name",
                             "documents_involved": sorted(names),
                             "verdict": v, "detail": why})

        v, why = classify_addresses(list(addrs.values()))
        if v != "CONSISTENT":
            findings.append({"dimension": "registered_address",
                             "documents_involved": sorted(addrs),
                             "verdict": v, "detail": why})

        v, why = classify_signatory(d["signatory"], d["gst_directors"])
        if v != "CONSISTENT":
            findings.append({"dimension": "authorised_signatory",
                             "documents_involved": ["contract", "aadhaar",
                                                    "gst-certificate"],
                             "verdict": v, "detail": why})

        v1, why1 = classify_gstin_pan(d["gstin"], d["pan"])
        v2, why2 = classify_gstin_cin_state(d["gstin"], d["cin"])
        if v1 != "CONSISTENT" or v2 != "CONSISTENT":
            detail = "; ".join(x for x, vv in ((why1, v1), (why2, v2))
                               if vv != "CONSISTENT")
            findings.append({"dimension": "gstin_pan_and_state_linkage",
                             "documents_involved": ["gst-certificate", "pan",
                                                    "incorporation"],
                             "verdict": worst([v1, v2]), "detail": detail})

        overall = worst([f["verdict"] for f in findings])

        # ---------- compare against the declared expectation ----------
        exp = d["xdoc"]
        if exp is None:
            if findings:
                failures.append(
                    f"d{d['id']}: unexpected cross-document finding(s): "
                    + "; ".join(f["dimension"] for f in findings))
        else:
            got = [f for f in findings if f["dimension"] == exp["dimension"]]
            if not got:
                failures.append(
                    f"d{d['id']}: expected a {exp['dimension']} finding, found none")
            elif got[0]["verdict"] != exp["expected_verdict"]:
                failures.append(
                    f"d{d['id']}: {exp['dimension']} verdict was "
                    f"{got[0]['verdict']}, expected {exp['expected_verdict']}")
            for f in findings:
                if f["dimension"] != exp["dimension"]:
                    failures.append(
                        f"d{d['id']}: extra cross-document finding on {f['dimension']}")

        results.append({
            "dataset": f"d{d['id']}",
            "company": d["company"],
            "defect": d["defect"] or "none",
            "individual_checks": {k: {"pass": v[0], "detail": v[1]}
                                  for k, v in checks.items()},
            "cross_document_findings": findings,
            "cross_document_verdict": overall,
            "cross_document_defect": d["xdoc"],
        })

        # ---------------------------- report ----------------------------
        tag = f"  [FIELD DEFECT: {d['defect']}]" if d["defect"] else ""
        print(f"\nd{d['id']}  {d['company']}{tag}")
        for name, (ok, msg) in checks.items():
            mark = "PASS" if ok else "FAIL"
            flag = "  <-- expected defect" if (not ok and name == expected_fail) else ""
            print(f"    [{mark}] {name:<22} {msg}{flag}")
        if findings:
            for f in findings:
                print(f"    [{f['verdict']}] {f['dimension']}")
                print(f"           {f['detail']}")
        else:
            print(f"    [CONSISTENT] no cross-document disagreement")

    with open("verification-report.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 72)
    if failures:
        print(f"{len(failures)} PROBLEM(S):")
        for f_ in failures:
            print("  -", f_)
        sys.exit(1)

    indiv_clean = [r["dataset"] for r in results
                   if all(c["pass"] for c in r["individual_checks"].values())]
    print(f"All {len(results)} datasets behave as specified.")
    print(f"  Per-document checks clean: {', '.join(indiv_clean)}")
    print("  d4-d6 each fail exactly one field, as declared.")
    print("  d7-d10 pass every per-document check and are caught only by")
    print("  cross-document reconciliation.")
    print(f"  All {len(results) * len(DOC_TYPES)} PDFs are text-extractable and "
          f"carry the SPECIMEN marking.")


if __name__ == "__main__":
    main()
