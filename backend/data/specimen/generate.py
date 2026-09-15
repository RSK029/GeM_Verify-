"""
generate.py - Build all specimen bidder document sets.
SIH 2026, PS SIH26100.
"""

import os, json, csv
from reportlab.lib.units import mm

from render import Doc
from datasets import (DATASETS, DOC_TYPES, TENDER_REF, TENDER_TITLE, BUYER,
                      LINE_ITEMS, doc_name, doc_address)

OUT = "pdfs"
BID_DATE = "10/09/2026"
CA_DATE = "28/08/2026"
PLACE = lambda d: d["city"]


def k(d):
    """Single-digit form of the dataset id, for cosmetic filler values only.
    Keeps d10's reference numbers the same length as d1-d9's, so they cannot
    collide with the identifier regexes."""
    return d["id"] % 10


def p(d, doctype):
    return os.path.join(OUT, f"d{d['id']}-{doctype}.pdf")


# ---------------------------------------------------------------- 1 contract
def contract(d):
    doc = Doc(p(d, "contract"))
    doc.authority([
        BUYER,
        "(A Government of India Enterprise)",
        "Materials & Contracts Department, Manali, Chennai - 600068",
    ])
    doc.title("SIGNED TENDER DOCUMENT / BID ACCEPTANCE FORM")
    doc.fields([
        ("Tender Reference No.", TENDER_REF),
        ("Tender Title", TENDER_TITLE),
        ("Bid Due Date", BID_DATE),
        ("Bidder (Legal Name)", d["company"]),
        ("Bidder Address", f"{d['addr']}, {d['city']} - {d['pin']}, {d['state_name']}"),
        ("GSTIN", d["gstin"]),
        ("PAN", d["pan"]),
        ("CIN", d["cin"]),
        ("Udyam Registration No.", d["udyam"]),
        ("Authorised Signatory", d["signatory"]),
        ("Designation", d["designation"]),
    ], bold_values={"Tender Reference No.", "Bidder (Legal Name)", "GSTIN", "PAN"})

    doc.heading("1. SCOPE")
    doc.para(
        f"This bid is submitted against Tender Reference {TENDER_REF} - {TENDER_TITLE} "
        f"floated by {BUYER}. The bidder offers to supply the following items in full, "
        f"in accordance with the technical specifications, terms and conditions set out "
        f"in the tender document and its corrigenda, if any.")
    doc.table(
        ["Sl.", "Description of Item", "Quantity"],
        [[a, b, c] for a, b, c in LINE_ITEMS],
        [14 * mm, 116 * mm, 40 * mm],
    )

    doc.heading("2. DECLARATIONS")
    doc.bullets([
        f"The bidder has read and accepts all terms, conditions and specifications of "
        f"Tender {TENDER_REF} without deviation or reservation.",
        "All documents submitted with this bid are true and correct, and the statutory "
        "registrations quoted above are valid and subsisting as on the bid due date.",
        f"The bidder is a Class-I Local Supplier within the meaning of the Public "
        f"Procurement (Preference to Make in India) Order, with local content of "
        f"{d['local_content']}%, supported by the cost-breakup certificate enclosed.",
        f"The bidder has not been blacklisted or debarred by {BUYER} or by any Central "
        f"or State Government entity as on the bid due date.",
        f"The bidder has {d['experience_yrs']} years of experience in the supply of "
        f"comparable industrial equipment, evidenced by the completion certificates enclosed.",
        "The person signing this document is duly authorised by the Board of Directors "
        "to submit this bid and to bind the bidder.",
    ])

    doc.heading("3. ENCLOSURES")
    doc.para(
        "Aadhaar of authorised signatory; PAN of the bidder; GST registration certificate "
        "(Form GST REG-06); Udyam registration certificate; certificate of incorporation; "
        "EPFO/ESIC establishment proof; OEM authorisation letter; local content declaration "
        "with CA-certified cost breakup; CA-certified turnover statement for FY 2024-25; "
        "work experience and completion certificates; bank mandate form.")

    doc.signature(d["signatory"], d["designation"], d["company"], PLACE(d), BID_DATE,
                  seal_text=d["short"].upper() + " SEAL")
    doc.save()


# ---------------------------------------------------------------- 2 aadhaar
def aadhaar(d):
    doc = Doc(p(d, "aadhaar"))
    doc.authority([
        "GOVERNMENT OF INDIA",
        "Unique Identification Authority of India",
        "Aadhaar - Aam Aadmi ka Adhikar",
    ])
    doc.title("AADHAAR - IDENTITY DOCUMENT OF AUTHORISED SIGNATORY", 11.5)
    doc.idcard([
        ("Name", d["signatory"], True),
        ("Father's Name", d["father"], False),
        ("Date of Birth", d["dob"], False),
        ("Gender", d["gender"], False),
        ("Aadhaar Number", " ".join([d["aadhaar"][0:4], d["aadhaar"][4:8], d["aadhaar"][8:12]]), True),
    ])
    doc.fields([
        ("Aadhaar Number (unformatted)", d["aadhaar"]),
        ("Address", f"{d['addr']}, {d['city']}, {d['state_name']} - {d['pin']}"),
        ("Enrolment No.", f"10{k(d)}4/2{k(d)}119/{k(d)}0{k(d)}45"),
        ("Date of Issue", "17/05/2019"),
        ("VID", f"9{d['aadhaar'][1:]}{k(d)}1{k(d)}3"),
    ], bold_values={"Aadhaar Number (unformatted)"})
    doc.note(
        "Aadhaar is proof of identity, not of citizenship or date of birth. "
        "This specimen carries a number in the reserved 0/1 leading-digit range, which "
        "UIDAI does not issue; it can never correspond to a real resident.")
    doc.heading("DECLARATION")
    doc.para(
        f"I, {d['signatory']}, {d['designation']} of {d['company']}, confirm that the "
        f"identity particulars above are mine and that I am the authorised signatory for "
        f"the bid submitted against Tender {TENDER_REF}.")
    doc.signature(d["signatory"], d["designation"], d["company"], PLACE(d), BID_DATE)
    doc.save()


# ---------------------------------------------------------------- 3 pan
def pan(d):
    doc = Doc(p(d, "pan"))
    doc.authority([
        "INCOME TAX DEPARTMENT",
        "GOVERNMENT OF INDIA",
        "Permanent Account Number Card",
    ])
    doc.title("PERMANENT ACCOUNT NUMBER (PAN) - COMPANY", 11.5)
    doc.idcard([
        ("Permanent Account No.", d["pan"], True),
        ("Name", d["pan_name"], True),
        ("Constitution", "Company", False),
        ("Date of Incorporation", d["incorporated"], False),
    ], photo_label="EMBLEM")
    doc.fields([
        ("PAN", d["pan"]),
        ("Name of Holder (as printed on card)", d["pan_name"]),
        ("Holder Type (4th character)", f"'{d['pan'][3]}' - Company"),
        ("Assessing Officer Code", f"{d['state_abbr']}W{k(d)}{k(d)}0{k(d)}"),
        ("Jurisdiction", f"Circle {k(d)}({k(d)}), {d['city']}"),
    ], bold_values={"PAN", "Name of Holder (as printed on card)"})
    doc.note(
        "The name printed on the PAN card is the legal name on record with the Income Tax "
        "Department and must correspond to the bidder's legal name in the other bid documents.")
    doc.save()


# ------------------------------------------------------------ 4 gst reg-06
def gst(d):
    doc = Doc(p(d, "gst-certificate"))
    doc.authority([
        "GOVERNMENT OF INDIA",
        "Goods and Services Tax",
        "FORM GST REG-06  [See Rule 10(1)]",
    ])
    doc.title("REGISTRATION CERTIFICATE", 12.5)
    doc.fields([
        ("Registration Number (GSTIN)", d["gstin"]),
        ("Legal Name", doc_name(d, "gst-certificate")),
        ("Trade Name, if any", d["short"]),
        ("Constitution of Business", "Private Limited Company"),
        ("Address of Principal Place of Business", doc_address(d, "gst-certificate")),
        ("Date of Liability", "01/07/2017"),
        ("Period of Validity (From)", "01/07/2017"),
        ("Period of Validity (To)", "Not Applicable"),
        ("Type of Registration", "Regular"),
        ("Particulars of Approving Authority", f"State Tax Officer, {d['city']}"),
        ("Signature", "Digitally signed"),
        ("Date of issue of Certificate", "01/07/2017"),
    ], bold_values={"Registration Number (GSTIN)", "Legal Name"})

    doc.heading("Annexure A - Details of Additional Places of Business")
    doc.para("Nil.")

    doc.heading("Annexure B - Details of Proprietor / Partners / Directors")
    doc.table(
        ["Sl.", "Name", "Designation", "Resident of State"],
        [[str(i + 1), nm, desig, d["state_name"]]
         for i, (nm, desig) in enumerate(d["gst_directors"])],
        [14 * mm, 62 * mm, 48 * mm, 46 * mm],
    )
    doc.note(
        "GSTIN structure: characters 1-2 state code, 3-12 PAN of the registered person, "
        "13 entity number within the state, 14 the letter Z, 15 a mod-36 check character "
        "computed over the preceding fourteen characters.")
    doc.save()


# ---------------------------------------------------------------- 5 udyam
def udyam(d):
    doc = Doc(p(d, "udyam"))
    doc.authority([
        "GOVERNMENT OF INDIA",
        "Ministry of Micro, Small and Medium Enterprises",
        "Udyam Registration Portal",
    ])
    doc.title("UDYAM REGISTRATION CERTIFICATE", 12.5)
    doc.fields([
        ("Udyam Registration Number", d["udyam"]),
        ("Name of Enterprise", doc_name(d, "udyam")),
        ("Type of Enterprise (FY 2024-25)", "Small"),
        ("Major Activity", "Manufacturing"),
        ("Social Category of Entrepreneur", "General"),
        ("Name of Unit", d["short"] + " Unit I"),
        ("Official Address of Enterprise", doc_address(d, "udyam")),
        ("Mobile", f"9{k(d)}876{k(d)}43{k(d)}0"),
        ("Email", f"contact@{d['short'].lower().replace(' ', '')}.example"),
        ("Date of Incorporation / Registration", d["incorporated"]),
        ("Date of Commencement of Production", d["incorporated"]),
        ("National Industry Classification (NIC) Code", "28131 - Manufacture of pumps and compressors"),
        ("Number of Persons Employed", str(40 + d["id"] * 7)),
        ("PAN of Enterprise", d["pan"]),
        ("GSTIN of Enterprise", d["gstin"]),
        ("Date of Udyam Registration", "14/09/2020"),
    ], bold_values={"Udyam Registration Number", "Name of Enterprise"})
    doc.note(
        "This certificate is issued on self-declaration basis. Classification is based on "
        "investment in plant and machinery and on turnover as per the MSMED Act, 2006.")
    doc.save()


# -------------------------------------------------------- 6 incorporation
def incorporation(d):
    doc = Doc(p(d, "incorporation"))
    doc.authority([
        "GOVERNMENT OF INDIA",
        "Ministry of Corporate Affairs",
        f"Office of the Registrar of Companies, {d['city']}",
        "Form INC-11  [Pursuant to Rule 18 of the Companies (Incorporation) Rules, 2014]",
    ])
    doc.title("CERTIFICATE OF INCORPORATION", 12.5)
    doc.para(
        f"I hereby certify that {d['company']} is incorporated on this "
        f"{d['incorporated']} under the Companies Act, 2013 and that the company is "
        f"limited by shares.")
    doc.fields([
        ("Corporate Identity Number (CIN)", d["cin"]),
        ("Name of Company", d["company"]),
        ("Date of Incorporation", d["incorporated"]),
        ("Class of Company", "Private"),
        ("Category", "Company limited by Shares"),
        ("Sub-category", "Non-government company"),
        ("Permanent Account Number (PAN)", d["pan"]),
        ("Registered Office",
         f"{d['addr']}, {d['city']}, {d['state_name']} - {d['pin']}"),
        ("Authorised Share Capital", "Rs. 1,00,00,000"),
        ("Paid-up Share Capital", f"Rs. {50 + d['id'] * 5},00,000"),
        ("Registrar of Companies", f"RoC - {d['city']}"),
    ], bold_values={"Corporate Identity Number (CIN)", "Name of Company"})

    doc.heading("Directors on the date of this certificate")
    doc.table(
        ["Sl.", "Name", "DIN", "Designation"],
        [["1", d["signatory"], f"0{k(d)}12345{k(d)}", d["designation"]],
         ["2", d["father"], f"0{k(d)}98765{k(d)}", "Director"]],
        [14 * mm, 62 * mm, 40 * mm, 54 * mm],
    )
    doc.note(
        "CIN structure: listing status (1), industry code (5), state code (2), year of "
        "incorporation (4), ownership code (3), registration number (6).")
    doc.save()


# ------------------------------------------------------------- 7 epfo/esic
def epfo(d):
    doc = Doc(p(d, "epfo-esic"))
    doc.authority([
        "EMPLOYEES' PROVIDENT FUND ORGANISATION",
        "Ministry of Labour & Employment, Government of India",
        f"Regional Office, {d['city']}",
    ])
    doc.title("ESTABLISHMENT PROOF / COVERAGE STATUS", 12)
    doc.fields([
        ("Establishment Code Number", d["epfo"]),
        ("Name of Establishment", d["company"]),
        ("Address", f"{d['addr']}, {d['city']}, {d['state_name']} - {d['pin']}"),
        ("PAN", d["pan"]),
        ("Date of Coverage", d["incorporated"]),
        ("Status", "ACTIVE"),
        ("Exemption Status", "Un-exempted"),
        ("Number of Subscribers (as on 31/08/2026)", str(40 + d["id"] * 7)),
        ("Last ECR Filed For", "August 2026"),
        ("Last Remittance Date", "12/09/2026"),
        ("Dues Outstanding", "Nil"),
    ], bold_values={"Establishment Code Number", "Status"})

    doc.heading("EMPLOYEES' STATE INSURANCE CORPORATION")
    doc.fields([
        ("ESIC Employer Code", d["esic"]),
        ("Name of Employer", d["company"]),
        ("Status", "ACTIVE"),
        ("Date of Registration", d["incorporated"]),
        ("Number of Insured Persons", str(36 + d["id"] * 6)),
        ("Contribution Paid Up To", "August 2026"),
    ], bold_values={"ESIC Employer Code", "Status"})

    doc.heading("REMITTANCE HISTORY - LAST SIX WAGE MONTHS")
    doc.table(
        ["Wage Month", "ECR No.", "Subscribers", "Amount Remitted (Rs.)", "Status"],
        [
            ["March 2026",  f"ECR/26/03/{k(d)}0011", str(38 + d["id"] * 7), "4,86,320", "Paid"],
            ["April 2026",  f"ECR/26/04/{k(d)}0012", str(39 + d["id"] * 7), "4,91,870", "Paid"],
            ["May 2026",    f"ECR/26/05/{k(d)}0013", str(39 + d["id"] * 7), "4,91,870", "Paid"],
            ["June 2026",   f"ECR/26/06/{k(d)}0014", str(40 + d["id"] * 7), "5,02,440", "Paid"],
            ["July 2026",   f"ECR/26/07/{k(d)}0015", str(40 + d["id"] * 7), "5,02,440", "Paid"],
            ["August 2026", f"ECR/26/08/{k(d)}0016", str(40 + d["id"] * 7), "5,07,910", "Paid"],
        ],
        [30 * mm, 42 * mm, 26 * mm, 46 * mm, 26 * mm],
    )
    doc.note("System-generated statement. Establishment coverage status is ACTIVE with no "
             "outstanding dues as on the date of generation.")
    doc.save()


# ------------------------------------------------------------------- 8 oem
def oem(d):
    doc = Doc(p(d, "oem-authorisation"))
    doc.authority([
        d["oem"].upper(),
        "Original Equipment Manufacturer",
        f"Works: Industrial Area, {d['city']}, {d['state_name']}",
    ])
    doc.title("MANUFACTURER'S AUTHORISATION FORM", 12.5)
    doc.fields([
        ("To", f"The Head - Materials & Contracts, {BUYER}"),
        ("Tender Reference No.", TENDER_REF),
        ("Tender Title", TENDER_TITLE),
        ("Date", "02/09/2026"),
    ], bold_values={"Tender Reference No."})

    doc.para(
        f"We, {d['oem']}, being an established Original Equipment Manufacturer of the "
        f"equipment specified in Tender Reference {TENDER_REF} - {TENDER_TITLE}, having "
        f"our registered works at {d['city']}, {d['state_name']}, do hereby authorise "
        f"{d['company']} (GSTIN {d['gstin']}, PAN {d['pan']}) to submit a bid against the "
        f"said tender, and to negotiate and conclude a contract with you, in relation to "
        f"the equipment manufactured by us.")

    doc.heading("ITEMS COVERED BY THIS AUTHORISATION")
    doc.para("This authorisation extends to ALL line items of the said tender, without "
             "exception, exclusion or reservation as to any item, quantity or sub-assembly:")
    doc.table(
        ["Sl.", "Description of Item", "Quantity", "Covered"],
        [[a, b, c, "Yes"] for a, b, c in LINE_ITEMS],
        [14 * mm, 96 * mm, 32 * mm, 28 * mm],
    )

    doc.heading("UNDERTAKINGS")
    doc.bullets([
        "No item, sub-assembly or accessory of the tender scope is excluded from this "
        "authorisation.",
        "We extend our full standard warranty of 24 months from the date of commissioning, "
        "or 30 months from the date of despatch, whichever occurs earlier, for the goods "
        "supplied against this tender by the above bidder.",
        "We undertake to make available spare parts and after-sales support for a minimum "
        "period of ten years from the date of commissioning.",
        f"This authorisation is valid until the conclusion of the contract arising out of "
        f"Tender {TENDER_REF}, including the warranty period thereunder.",
        f"{d['company']} is our authorised channel partner and has been trained and equipped "
        f"to install, commission and service the equipment offered.",
    ])

    doc.signature(
        "S. Venkataraman", "Vice President - Projects & Tenders", d["oem"],
        d["city"], "02/09/2026", seal_text="OEM AUTHORISED SEAL")
    doc.save()


# --------------------------------------------------- 9 local content + CA
def local_content(d):
    lc = d["local_content"]
    total = 100.0
    imported = round(total - lc, 1)
    doc = Doc(p(d, "local-content"))
    doc.authority([
        d["company"].upper(),
        f"{d['addr']}, {d['city']}, {d['state_name']} - {d['pin']}",
        f"CIN: {d['cin']}  |  GSTIN: {d['gstin']}  |  PAN: {d['pan']}",
    ])
    doc.title("DECLARATION OF LOCAL CONTENT", 12.5)
    doc.fields([
        ("Tender Reference No.", TENDER_REF),
        ("Tender Title", TENDER_TITLE),
        ("Bidder", d["company"]),
        ("Local Content Declared", f"{lc}%"),
        ("Supplier Classification", "Class-I Local Supplier"),
    ], bold_values={"Local Content Declared", "Tender Reference No."})

    doc.para(
        f"We hereby declare that the goods offered against Tender {TENDER_REF} meet the "
        f"local content requirement of not less than 50% prescribed under the Public "
        f"Procurement (Preference to Make in India) Order, 2017 and its subsequent "
        f"revisions. The local content in the goods offered is {lc}%, and accordingly "
        f"{d['company']} qualifies as a Class-I Local Supplier. We are aware that a false "
        f"declaration attracts action under the said Order and under the tender conditions.")
    doc.signature(d["signatory"], d["designation"], d["company"], PLACE(d), BID_DATE,
                  seal_text=d["short"].upper() + " SEAL")

    # ---- CA certificate page ----
    doc.c.showPage(); doc._page_start()
    doc.authority([
        f"R. Krishnamoorthy & Associates",
        "Chartered Accountants",
        f"Firm Registration No. 00{k(d)}45{k(d)}S  |  {d['city']}",
    ])
    doc.title("CERTIFICATE OF LOCAL CONTENT - COST BREAKUP", 12)
    doc.para(
        f"This is to certify that we have examined the books of account, purchase records, "
        f"bills of entry and costing records of {d['company']} (PAN {d['pan']}, GSTIN "
        f"{d['gstin']}) in respect of the goods offered against Tender {TENDER_REF}, and "
        f"that the local content therein, computed in accordance with the Public "
        f"Procurement (Preference to Make in India) Order, is as set out below.")
    doc.table(
        ["Sl.", "Cost Element", "Domestic (Rs. lakh)", "Imported (Rs. lakh)", "Total (Rs. lakh)"],
        [
            ["1", "Raw material and bought-out components", f"{lc * 3.2:.2f}", f"{imported * 3.0:.2f}", f"{lc * 3.2 + imported * 3.0:.2f}"],
            ["2", "Castings, fabrication and machining",    f"{lc * 1.5:.2f}", f"{imported * 0.4:.2f}", f"{lc * 1.5 + imported * 0.4:.2f}"],
            ["3", "Electricals, instrumentation and drives", f"{lc * 1.1:.2f}", f"{imported * 1.6:.2f}", f"{lc * 1.1 + imported * 1.6:.2f}"],
            ["4", "Direct labour and factory overhead",     f"{lc * 0.9:.2f}", "0.00",                  f"{lc * 0.9:.2f}"],
            ["5", "Testing, inspection and packing",        f"{lc * 0.3:.2f}", "0.00",                  f"{lc * 0.3:.2f}"],
        ],
        [12 * mm, 66 * mm, 32 * mm, 32 * mm, 28 * mm],
    )
    dom = lc * (3.2 + 1.5 + 1.1 + 0.9 + 0.3)
    imp = imported * (3.0 + 0.4 + 1.6)
    doc.fields([
        ("Total Domestic Value Addition", f"Rs. {dom:.2f} lakh"),
        ("Total Imported Content", f"Rs. {imp:.2f} lakh"),
        ("Total Ex-works Value", f"Rs. {dom + imp:.2f} lakh"),
        ("Local Content Percentage", f"{dom / (dom + imp) * 100:.1f}%"),
        ("Declared Local Content", f"{lc}%"),
        ("Minimum Required", "50%"),
        ("Requirement Met", "YES"),
    ], bold_values={"Local Content Percentage", "Requirement Met"})
    doc.para(
        "The percentage certified above is not less than the 50% threshold prescribed for "
        "a Class-I Local Supplier. This certificate is issued at the request of the "
        "management for submission against the said tender.")
    doc.signature("R. Krishnamoorthy, FCA", f"Partner  |  Membership No. 2{k(d)}45{k(d)}8",
                  "R. Krishnamoorthy & Associates, Chartered Accountants",
                  d["city"], CA_DATE, seal_text="CHARTERED ACCOUNTANTS")
    doc.save()


# ------------------------------------------------------------- 10 turnover
def turnover(d):
    t = float(d["turnover_cr"])
    prev = float(d["prev_yr_cr"])
    doc = Doc(p(d, "turnover"))
    doc.authority([
        "R. Krishnamoorthy & Associates",
        "Chartered Accountants",
        f"Firm Registration No. 00{k(d)}45{k(d)}S  |  {d['city']}",
    ])
    doc.title("CERTIFICATE OF ANNUAL TURNOVER - FY 2024-25", 12)
    doc.fields([
        ("Name of Company", doc_name(d, "turnover")),
        ("Registered Office", doc_address(d, "turnover")),
        ("PAN", d["pan"]),
        ("GSTIN", d["gstin"]),
        ("CIN", d["cin"]),
        ("Financial Year Certified", "2024-25 (01/04/2024 to 31/03/2025)"),
        ("Tender Reference No.", TENDER_REF),
    ], bold_values={"Name of Company", "Tender Reference No."})

    doc.para(
        f"We have audited the financial statements of {d['company']} for the financial "
        f"year ended 31 March 2025 and certify, on the basis of the audited books of "
        f"account and the records produced before us, that the annual turnover of the "
        f"company for the said year is as stated below.")
    doc.table(
        ["Financial Year", "Turnover (Rs. crore)", "Profit After Tax (Rs. crore)", "Net Worth (Rs. crore)"],
        [
            ["2024-25", f"{t:.2f}", f"{t * 0.082:.2f}", f"{t * 0.41:.2f}"],
            ["2023-24", f"{prev:.2f}", f"{prev * 0.076:.2f}", f"{prev * 0.38:.2f}"],
            ["2022-23", f"{prev * 0.87:.2f}", f"{prev * 0.069:.2f}", f"{prev * 0.34:.2f}"],
        ],
        [36 * mm, 44 * mm, 50 * mm, 40 * mm],
    )
    doc.fields([
        ("Turnover Certified for FY 2024-25", f"Rs. {t:.2f} crore"),
        ("In words", f"Rupees {_words_cr(t)} crore only"),
        ("Minimum Turnover Required by Tender", "Rs. 5.00 crore"),
        ("Requirement Met", "YES"),
    ], bold_values={"Turnover Certified for FY 2024-25", "Requirement Met"})
    doc.para(
        "This certificate is issued at the request of the management of the company for "
        "the limited purpose of submission against the above tender, and is based on the "
        "audited financial statements for the year ended 31 March 2025.")
    doc.signature("R. Krishnamoorthy, FCA", f"Partner  |  Membership No. 2{k(d)}45{k(d)}8",
                  "R. Krishnamoorthy & Associates, Chartered Accountants",
                  d["city"], CA_DATE, seal_text="CHARTERED ACCOUNTANTS")
    doc.save()


def _words_cr(v):
    whole = int(v)
    frac = int(round((v - whole) * 100))
    ones = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
            "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
            "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    w = ones[whole] if whole < 20 else f"{whole}"
    return f"{w} point {frac:02d}" if frac else w


# ----------------------------------------------------------- 11 experience
def experience(d):
    yrs = d["experience_yrs"]
    start = 2026 - yrs
    doc = Doc(p(d, "experience"))
    doc.authority([
        d["company"].upper(),
        f"{d['addr']}, {d['city']}, {d['state_name']} - {d['pin']}",
        f"CIN: {d['cin']}  |  GSTIN: {d['gstin']}",
    ])
    doc.title("STATEMENT OF WORK EXPERIENCE", 12.5)
    doc.fields([
        ("Tender Reference No.", TENDER_REF),
        ("Bidder", d["company"]),
        ("Year of Commencement of Business", str(start)),
        ("Years of Relevant Experience", f"{yrs} years"),
        ("Minimum Required by Tender", "5 years"),
        ("Requirement Met", "YES"),
    ], bold_values={"Years of Relevant Experience", "Requirement Met"})
    doc.table(
        ["Sl.", "Client", "Scope of Supply", "Order Value (Rs. lakh)", "Completed"],
        [
            ["1", "Southern Refineries Limited", "Centrifugal process pumps, API 610 - 8 nos", "146.20", f"12/{start + 3}"],
            ["2", "National Fertilisers Corporation", "LT motor control centres, Form 4b - 5 sets", "212.75", f"08/{start + 5}"],
            ["3", "Coastal Power Generation Company", "VFD panels 160 kW - 12 nos", "188.40", f"03/{start + 7}"],
            ["4", "Bharat Petrochemical Works Limited", "Shell & tube heat exchangers - 6 nos", "254.90", f"11/{min(start + 9, 2025)}"],
            ["5", "Deccan Industrial Gases Limited", "Pressure transmitters, HART - 60 nos", "96.30", "05/2026"],
        ],
        [12 * mm, 44 * mm, 60 * mm, 32 * mm, 22 * mm],
    )
    doc.signature(d["signatory"], d["designation"], d["company"], PLACE(d), BID_DATE,
                  seal_text=d["short"].upper() + " SEAL")

    # ---- completion certificate page ----
    doc.c.showPage(); doc._page_start()
    doc.authority([
        "SOUTHERN REFINERIES LIMITED",
        "Projects & Maintenance Division",
        f"Refinery Complex, {d['city']}, {d['state_name']}",
    ])
    doc.title("WORK COMPLETION CERTIFICATE", 12.5)
    doc.fields([
        ("Certificate No.", f"SRL/PMD/COMP/{start + 3}/{k(d)}0{k(d)}4"),
        ("Contractor / Supplier", d["company"]),
        ("GSTIN of Supplier", d["gstin"]),
        ("Purchase Order No.", f"SRL/PO/{start + 2}/IE/{k(d)}8{k(d)}2"),
        ("Purchase Order Date", f"14/06/{start + 2}"),
        ("Scope of Work", "Design, manufacture, supply, installation and commissioning "
                          "of 8 nos centrifugal process pumps to API 610 OH2"),
        ("Order Value", "Rs. 146.20 lakh"),
        ("Date of Completion", f"22/12/{start + 3}"),
        ("Performance Rating", "Satisfactory"),
        ("Liquidated Damages Levied", "Nil"),
    ], bold_values={"Contractor / Supplier", "Performance Rating"})
    doc.para(
        f"This is to certify that {d['company']} has satisfactorily executed and completed "
        f"the work described above within the contractual schedule. The equipment supplied "
        f"met the specified performance parameters during site acceptance testing. No "
        f"liquidated damages were levied and there are no pending claims or disputes.")
    doc.signature("T. Ramanathan", "Chief Manager - Projects",
                  "Southern Refineries Limited", d["city"], f"04/01/{start + 4}",
                  seal_text="SRL PROJECTS DIVISION")
    doc.save()


# ---------------------------------------------------------- 12 bank mandate
def bank(d):
    doc = Doc(p(d, "bank-mandate"))
    doc.authority([
        d["bank"].upper(),
        f"{d['city']}, {d['state_name']}",
        "Electronic Clearing Service / NEFT Mandate",
    ])
    doc.title("BANK MANDATE FORM", 12.5)
    doc.fields([
        ("Tender Reference No.", TENDER_REF),
        ("Name of Account Holder", doc_name(d, "bank-mandate")),
        ("Bank Name and Branch", d["bank"]),
        ("Account Number", d["account"]),
        ("Account Type", "Current Account"),
        ("IFSC", d["ifsc"]),
        ("MICR Code", f"600{k(d)}0{k(d)}00{k(d)}"),
        ("PAN of Account Holder", d["pan"]),
        ("GSTIN of Account Holder", d["gstin"]),
    ], bold_values={"Name of Account Holder", "Account Number", "IFSC"})

    doc.para(
        f"We authorise {BUYER} to credit all payments due to us against Tender "
        f"{TENDER_REF} directly to the above account by electronic transfer. We undertake "
        f"to advise any change in these particulars in writing without delay.")

    doc.heading("BANK CERTIFICATION")
    doc.para(
        f"Certified that the particulars furnished above are correct as per our records, "
        f"and that {doc_name(d, 'bank-mandate')} maintains current account number "
        f"{d['account']} with this branch, which is operative and in good standing.")
    doc.signature("Branch Manager", d["bank"], d["bank"], d["city"], "05/09/2026",
                  seal_text="BANK BRANCH SEAL")

    # ---- cancelled cheque page ----
    doc.c.showPage(); doc._page_start()
    doc.title("CANCELLED CHEQUE (SPECIMEN)", 12.5)
    c = doc.c
    x0, y0, w, h = 22 * mm, doc.y - 78 * mm, 166 * mm, 72 * mm
    c.setStrokeColorRGB(0.35, 0.35, 0.40); c.setLineWidth(1.0)
    c.rect(x0, y0, w, h, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 10); c.setFillColorRGB(0, 0, 0)
    c.drawString(x0 + 6 * mm, y0 + h - 10 * mm, d["bank"])
    c.setFont("Helvetica", 8)
    c.drawString(x0 + 6 * mm, y0 + h - 16 * mm, f"{d['city']}, {d['state_name']} - {d['pin']}")
    c.drawRightString(x0 + w - 6 * mm, y0 + h - 10 * mm, "Date: D D M M Y Y Y Y")
    c.setFont("Helvetica", 8.5)
    c.drawString(x0 + 6 * mm, y0 + h - 28 * mm, "Pay ______________________________________________________________ or Bearer")
    c.drawString(x0 + 6 * mm, y0 + h - 38 * mm, "Rupees ___________________________________________________")
    c.rect(x0 + w - 56 * mm, y0 + h - 42 * mm, 50 * mm, 11 * mm, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x0 + 6 * mm, y0 + h - 50 * mm, f"A/c No.  {d['account']}")
    c.drawString(x0 + 6 * mm, y0 + h - 56 * mm, f"IFSC  {d['ifsc']}")
    c.setFont("Helvetica", 8)
    c.drawRightString(x0 + w - 6 * mm, y0 + h - 56 * mm, doc_name(d, "bank-mandate"))
    c.setFont("Courier", 11)
    c.drawString(x0 + 8 * mm, y0 + 7 * mm,
                 f"C 00{k(d)}45{k(d)} C  600{k(d)}0{k(d)}00{k(d)} C  {d['account'][:6]} C  31")
    # cancellation strokes
    c.setStrokeColorRGB(0.15, 0.15, 0.55); c.setLineWidth(1.8)
    c.line(x0 + 10 * mm, y0 + 12 * mm, x0 + w - 10 * mm, y0 + h - 14 * mm)
    c.line(x0 + 10 * mm, y0 + h - 14 * mm, x0 + w - 10 * mm, y0 + 12 * mm)
    c.setFont("Helvetica-Bold", 20); c.setFillColorRGB(0.15, 0.15, 0.55)
    c.drawCentredString(x0 + w / 2, y0 + h / 2 - 6, "CANCELLED")
    doc.y = y0 - 10 * mm
    doc.fields([
        ("Account Holder", doc_name(d, "bank-mandate")),
        ("Account Number", d["account"]),
        ("IFSC", d["ifsc"]),
    ])
    doc.save()


BUILDERS = {
    "contract": contract, "aadhaar": aadhaar, "pan": pan,
    "gst-certificate": gst, "udyam": udyam, "incorporation": incorporation,
    "epfo-esic": epfo, "oem-authorisation": oem, "local-content": local_content,
    "turnover": turnover, "experience": experience, "bank-mandate": bank,
}


def main():
    os.makedirs(OUT, exist_ok=True)
    made = []
    for d in DATASETS:
        for dt in DOC_TYPES:
            BUILDERS[dt](d)
            made.append(p(d, dt))
    print(f"generated {len(made)} PDFs")

    # ---- manifest ----
    rows = []
    for d in DATASETS:
        rows.append({
            "dataset": f"d{d['id']}",
            "company": d["company"],
            "pan": d["pan"],
            "pan_card_name": d["pan_name"],
            "gstin": d["gstin"],
            "udyam": d["udyam"],
            "cin": d["cin"],
            "signatory": d["signatory"],
            "aadhaar": d["aadhaar"],
            "turnover_fy2024_25_cr": d["turnover_cr"],
            "experience_years": d["experience_yrs"],
            "local_content_pct": d["local_content"],
            "epfo_code": d["epfo"],
            "esic_code": d["esic"],
            "defect": d["defect"] or "none",
            "defect_field": d["defect_field"] or "-",
            "cross_document_defect": d["xdoc"],
        })
    with open("manifest.json", "w") as f:
        json.dump(rows, f, indent=2)

    # CSV flattens the nested cross_document_defect into three columns.
    flat = []
    for r in rows:
        x = r.get("cross_document_defect") or {}
        fr = {k: v for k, v in r.items() if k != "cross_document_defect"}
        fr["xdoc_dimension"] = x.get("dimension", "-")
        fr["xdoc_documents"] = "|".join(x.get("documents_involved", [])) or "-"
        fr["xdoc_expected_verdict"] = x.get("expected_verdict", "CONSISTENT")
        flat.append(fr)
    with open("manifest.csv", "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        wtr.writeheader(); wtr.writerows(flat)
    print("wrote manifest.json / manifest.csv")


if __name__ == "__main__":
    main()
