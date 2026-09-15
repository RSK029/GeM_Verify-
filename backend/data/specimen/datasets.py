"""
datasets.py - The six specimen bidder document sets.
SIH 2026, PS SIH26100. All entities fictitious.
"""

from validators import make_aadhaar, make_gstin, gstin_check_char

TENDER_REF = "GEM/2026/B/4471902"
TENDER_TITLE = "CPCL Industrial Equipment Procurement - 2026"
BUYER = "Chennai Petroleum Corporation Limited"

LINE_ITEMS = [
    ("1", "Centrifugal Process Pump, API 610 OH2, 75 kW", "6 Nos"),
    ("2", "LT Motor Control Centre, Form 4b, 415 V", "3 Sets"),
    ("3", "Heat Exchanger, Shell & Tube, SS 316L", "4 Nos"),
    ("4", "Variable Frequency Drive Panel, 160 kW", "8 Nos"),
    ("5", "Pressure Transmitter, HART, 4-20 mA", "40 Nos"),
]


def _build(
    n, company, short, signatory, designation, father, dob, gender,
    state_code, state_name, state_abbr, pan, entity_no, udyam, cin,
    epfo, esic, addr, city, pin, incorporated, turnover_cr, prev_yr_cr,
    experience_yrs, local_content, oem, bank, ifsc, account,
    aadhaar_seed, defect=None, pan_name=None,
    overrides=None, gst_directors=None, gstin_pan=None, xdoc=None,
):
    aadhaar = make_aadhaar(aadhaar_seed)
    # gstin_pan lets a dataset embed a PAN other than the declared one; the
    # check character is still computed over the GSTIN as actually written.
    gstin = make_gstin(state_code, gstin_pan or pan, entity_no)

    d = {
        "id": n,
        "company": company,
        "short": short,
        "signatory": signatory,
        "designation": designation,
        "father": father,
        "dob": dob,
        "gender": gender,
        "state_code": state_code,
        "state_name": state_name,
        "state_abbr": state_abbr,
        "pan": pan,
        "pan_name": pan_name or company,
        "gstin": gstin,
        "udyam": udyam,
        "cin": cin,
        "epfo": epfo,
        "esic": esic,
        "aadhaar": aadhaar,
        "addr": addr,
        "city": city,
        "pin": pin,
        "incorporated": incorporated,
        "turnover_cr": turnover_cr,
        "prev_yr_cr": prev_yr_cr,
        "experience_yrs": experience_yrs,
        "local_content": local_content,
        "oem": oem,
        "bank": bank,
        "ifsc": ifsc,
        "account": account,
        "defect": defect,
        "defect_field": None,
        # per-document field overrides: {doctype: {"company": ..., "addr_line": ...}}
        "overrides": overrides or {},
        # directors as listed in Annexure B of the GST certificate
        "gst_directors": gst_directors or [(signatory, designation)],
        # expected cross-document finding, or None
        "xdoc": xdoc,
    }

    # ---- inject the one deliberate irregularity -------------------------
    if defect == "gstin_checksum":
        good = d["gstin"]
        alpha = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        bad = good[:14] + alpha[(alpha.index(good[14]) + 1) % 36]
        d["gstin_correct"] = good
        d["gstin"] = bad
        d["defect_field"] = "GSTIN check character (mod-36)"

    elif defect == "pan_name_mismatch":
        d["defect_field"] = "PAN holder legal name"

    elif defect == "aadhaar_checksum":
        good = d["aadhaar"]
        bad = good[:11] + str((int(good[11]) + 1) % 10)
        d["aadhaar_correct"] = good
        d["aadhaar"] = bad
        d["defect_field"] = "Aadhaar check digit (Verhoeff)"

    return d


def doc_name(d, doctype):
    """Legal name as it is printed on one document type."""
    return d["overrides"].get(doctype, {}).get("company", d["company"])


def doc_address(d, doctype):
    """Registered address as it is printed on one document type."""
    o = d["overrides"].get(doctype, {})
    if "addr_line" in o:
        return o["addr_line"]
    return f"{d['addr']}, {d['city']}, {d['state_name']} - {d['pin']}"


DATASETS = [
    _build(
        1,
        company="ABC Industrial Systems Private Limited", short="ABC Industrial Systems",
        signatory="Rajesh Kumar Sharma", designation="Managing Director",
        father="Mohan Lal Sharma", dob="14/03/1976", gender="MALE",
        state_code="33", state_name="Tamil Nadu", state_abbr="TN",
        pan="AAACA1111C", entity_no="1",
        udyam="UDYAM-TN-02-0012345", cin="U29253TN2014PTC101234",
        epfo="TNMAS0012345000", esic="33000123450000101",
        addr="Plot 14, SIDCO Industrial Estate, Ambattur", city="Chennai", pin="600098",
        incorporated="22/08/2014", turnover_cr="12.48", prev_yr_cr="10.92",
        experience_yrs=11, local_content=62,
        oem="Bharat Rotating Equipment Manufacturing Company Limited",
        bank="State Bank of India, Ambattur Branch", ifsc="SBIN0001234",
        account="30124567890",
        aadhaar_seed="01100220331",
    ),
    _build(
        2,
        company="XYZ Electromech Private Limited", short="XYZ Electromech",
        signatory="Meera Iyer", designation="Director",
        father="Subramanian Iyer", dob="09/11/1981", gender="FEMALE",
        state_code="27", state_name="Maharashtra", state_abbr="MH",
        pan="AAACX2222C", entity_no="1",
        udyam="UDYAM-MH-18-0023456", cin="U31909MH2013PTC202345",
        epfo="MHBAN0023456000", esic="27000234560000101",
        addr="B-42, MIDC Industrial Area, Bhosari", city="Pune", pin="411026",
        incorporated="05/02/2013", turnover_cr="8.76", prev_yr_cr="7.31",
        experience_yrs=12, local_content=71,
        oem="Deccan Switchgear and Controls Limited",
        bank="Bank of Baroda, Bhosari Branch", ifsc="BARB0BHOSAR",
        account="40235678901",
        aadhaar_seed="01200330442",
    ),
    _build(
        3,
        company="PQR Engineering Works Private Limited", short="PQR Engineering Works",
        signatory="Anil Prakash Deshmukh", designation="Whole-time Director",
        father="Prakash Ganesh Deshmukh", dob="27/06/1973", gender="MALE",
        state_code="29", state_name="Karnataka", state_abbr="KA",
        pan="AAACP3333C", entity_no="1",
        udyam="UDYAM-KA-03-0034567", cin="U28999KA2016PTC303456",
        epfo="KABNG0034567000", esic="29000345670000101",
        addr="Shed 7, KIADB Industrial Area, Peenya Phase II", city="Bengaluru", pin="560058",
        incorporated="18/01/2016", turnover_cr="19.32", prev_yr_cr="16.44",
        experience_yrs=9, local_content=55,
        oem="Southern Thermal Systems Private Limited",
        bank="Canara Bank, Peenya Branch", ifsc="CNRB0003456",
        account="50346789012",
        aadhaar_seed="01300440553",
    ),
    _build(
        4,
        company="LMN Power Solutions Private Limited", short="LMN Power Solutions",
        signatory="Sunita Rani Gupta", designation="Director",
        father="Ramesh Chandra Gupta", dob="02/09/1979", gender="FEMALE",
        state_code="24", state_name="Gujarat", state_abbr="GJ",
        pan="AAACL4444C", entity_no="1",
        udyam="UDYAM-GJ-07-0045678", cin="U31200GJ2015PTC404567",
        epfo="GJVAD0045678000", esic="24000456780000101",
        addr="Survey 221, GIDC Estate, Vatva Phase IV", city="Ahmedabad", pin="382445",
        incorporated="11/06/2015", turnover_cr="14.05", prev_yr_cr="12.60",
        experience_yrs=10, local_content=58,
        oem="Gujarat Drives and Automation Limited",
        bank="HDFC Bank, Vatva Branch", ifsc="HDFC0004567",
        account="60457890123",
        aadhaar_seed="01400550664",
        defect="gstin_checksum",
    ),
    _build(
        5,
        company="DEF Techno Equipments Private Limited", short="DEF Techno Equipments",
        signatory="Vikram Singh Rathore", designation="Managing Director",
        father="Devendra Singh Rathore", dob="21/12/1970", gender="MALE",
        state_code="09", state_name="Uttar Pradesh", state_abbr="UP",
        pan="AAACD5555C", entity_no="1",
        udyam="UDYAM-UP-28-0056789", cin="U29120UP2012PTC505678",
        epfo="UPKAN0056789000", esic="09000567890000101",
        addr="C-118, UPSIDC Industrial Area, Panki Site V", city="Kanpur", pin="208022",
        incorporated="30/07/2012", turnover_cr="9.87", prev_yr_cr="8.05",
        experience_yrs=13, local_content=66,
        oem="Northern Process Equipment Manufacturers Limited",
        bank="Punjab National Bank, Panki Branch", ifsc="PUNB0056700",
        account="70568901234",
        aadhaar_seed="01500660775",
        defect="pan_name_mismatch",
        # stale pre-rename entity name still printed on the PAN card
        pan_name="DEF Technocraft Private Limited",
        xdoc={
            "dimension": "legal_name",
            "documents_involved": ["pan", "gst-certificate", "incorporation",
                                   "contract"],
            "expected_verdict": "POTENTIAL_INCONSISTENCY",
        },
    ),
    _build(
        6,
        company="GHI Automation Private Limited", short="GHI Automation",
        signatory="Kavita Nair", designation="Director",
        father="Balakrishnan Nair", dob="16/04/1985", gender="FEMALE",
        state_code="06", state_name="Haryana", state_abbr="HR",
        pan="AAACG6666C", entity_no="1",
        udyam="UDYAM-HR-05-0067890", cin="U29306HR2017PTC606789",
        epfo="HRFBD0067890000", esic="06000678900000101",
        addr="Plot 39, Sector 24, HSIIDC Industrial Estate", city="Faridabad", pin="121005",
        incorporated="09/03/2017", turnover_cr="6.42", prev_yr_cr="5.58",
        experience_yrs=8, local_content=52,
        oem="Indo Instrumentation and Controls Limited",
        bank="ICICI Bank, Sector 24 Branch", ifsc="ICIC0006789",
        account="80679012345",
        aadhaar_seed="01600770886",
        defect="aadhaar_checksum",
    ),

    # ----------------------------------------------------------------------
    # d7-d10: every identifier is individually valid and every threshold is
    # met. The irregularity is a disagreement BETWEEN documents, which only a
    # cross-document reconciliation pass can see.
    # ----------------------------------------------------------------------

    _build(
        7,
        company="Sterling Hydro Systems Private Limited", short="Sterling Hydro Systems",
        signatory="Ramesh Balachandran", designation="Managing Director",
        father="Balachandran Menon", dob="08/07/1974", gender="MALE",
        state_code="32", state_name="Kerala", state_abbr="KL",
        pan="AAACS7777C", entity_no="1",
        udyam="UDYAM-KL-09-0078901", cin="U29253KL2015PTC707890",
        epfo="KLKOC0078901000", esic="32000789010000101",
        addr="Plot 8, KINFRA Industrial Park, Kalamassery", city="Kochi", pin="683104",
        incorporated="19/05/2015", turnover_cr="11.35", prev_yr_cr="9.84",
        experience_yrs=10, local_content=57,
        oem="Malabar Hydraulic Equipment Limited",
        bank="Federal Bank, Kalamassery Branch", ifsc="FDRL0007890",
        account="90178901234",
        aadhaar_seed="01700880997",
        # Udyam drops the legal-form suffix; the bank mandate abbreviates it.
        overrides={
            "udyam": {"company": "Sterling Hydro Systems"},
            "bank-mandate": {"company": "Sterling Hydro Systems Pvt. Ltd."},
        },
        xdoc={
            "dimension": "legal_name",
            "documents_involved": ["gst-certificate", "pan", "incorporation",
                                   "turnover", "udyam", "bank-mandate"],
            "expected_verdict": "VARIATION",
        },
    ),
    _build(
        8,
        company="Meridian Process Controls Private Limited", short="Meridian Process Controls",
        signatory="Nikhil Barve", designation="Director",
        father="Shrikant Barve", dob="23/02/1983", gender="MALE",
        state_code="27", state_name="Maharashtra", state_abbr="MH",
        pan="AAACM8888C", entity_no="1",
        udyam="UDYAM-MH-19-0089012", cin="U29299MH2014PTC808901",
        epfo="MHAND0089012000", esic="27000890120000101",
        addr="Plot 22, MIDC Industrial Area, Andheri East", city="Mumbai", pin="400093",
        incorporated="27/10/2014", turnover_cr="16.70", prev_yr_cr="14.12",
        experience_yrs=11, local_content=64,
        oem="Konkan Instrumentation Systems Limited",
        bank="Axis Bank, Andheri East Branch", ifsc="UTIB0008901",
        account="10289012345",
        aadhaar_seed="01800991008",
        # One address, three renderings. GST carries the canonical form.
        overrides={
            "turnover": {"addr_line":
                         "Plot 22, M.I.D.C. Indl. Area, Andheri (E), Mumbai 400093"},
            "udyam": {"addr_line":
                      "Plot 22, MIDC Area, Andheri East, Mumbai, Maharashtra"},
        },
        xdoc={
            "dimension": "registered_address",
            "documents_involved": ["gst-certificate", "turnover", "udyam"],
            "expected_verdict": "VARIATION",
        },
    ),
    _build(
        9,
        company="Orion Thermal Engineering Private Limited", short="Orion Thermal Engineering",
        signatory="Deepak Ranganathan", designation="Managing Director",
        father="Ranganathan Iyengar", dob="11/09/1977", gender="MALE",
        state_code="29", state_name="Karnataka", state_abbr="KA",
        pan="AAACO9999C", entity_no="1",
        udyam="UDYAM-KA-04-0090123", cin="U28129KA2016PTC909012",
        epfo="KABNG0090123000", esic="29000901230000101",
        addr="Unit 12, KSSIDC Industrial Estate, Rajajinagar", city="Bengaluru", pin="560044",
        incorporated="04/04/2016", turnover_cr="13.90", prev_yr_cr="11.76",
        experience_yrs=9, local_content=61,
        oem="Mysore Heat Transfer Products Limited",
        bank="Union Bank of India, Rajajinagar Branch", ifsc="UBIN0009012",
        account="20390123456",
        aadhaar_seed="01901102119",
        # The person who signs the bid does not appear on the GST director list.
        gst_directors=[("Harish Malhotra", "Director"),
                       ("Sneha Kulkarni", "Director")],
        xdoc={
            "dimension": "authorised_signatory",
            "documents_involved": ["contract", "aadhaar", "gst-certificate"],
            "expected_verdict": "INCONSISTENT",
        },
    ),
    _build(
        10,
        company="Vertex Fluid Systems Private Limited", short="Vertex Fluid Systems",
        signatory="Anand Verma", designation="Director",
        father="Krishna Kumar Verma", dob="05/01/1980", gender="MALE",
        state_code="27", state_name="Maharashtra", state_abbr="MH",
        pan="AAACV1212C", entity_no="1",
        udyam="UDYAM-MH-20-0101234", cin="U29253KA2013PTC101201",
        epfo="MHPUN0101234000", esic="27001012340000101",
        addr="Gat 145, MIDC Chakan Phase II, Khed", city="Pune", pin="410501",
        incorporated="16/09/2013", turnover_cr="7.85", prev_yr_cr="6.90",
        experience_yrs=12, local_content=53,
        oem="Western Flow Control Industries Limited",
        bank="Kotak Mahindra Bank, Chakan Branch", ifsc="KKBK0010123",
        account="30401234567",
        aadhaar_seed="01002213322",
        # GSTIN embeds a different (but well-formed) PAN, and its state code
        # disagrees with the CIN state. Both are valid read in isolation.
        gstin_pan="AAACV3434C",
        xdoc={
            "dimension": "gstin_pan_and_state_linkage",
            "documents_involved": ["gst-certificate", "pan", "incorporation"],
            "expected_verdict": "INCONSISTENT",
        },
    ),
]

DOC_TYPES = [
    "contract", "aadhaar", "pan", "gst-certificate", "udyam",
    "incorporation", "epfo-esic", "oem-authorisation", "local-content",
    "turnover", "experience", "bank-mandate",
]
