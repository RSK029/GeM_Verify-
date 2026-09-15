"""
validators.py - Identifier validation for Indian tender documents.
SIH 2026, Problem Statement SIH26100.

Pure-stdlib. Import into your prototype's verification pipeline, or run
directly to self-test against the bundled specimen datasets.
"""

import re

# --------------------------------------------------------------------------
# Verhoeff checksum (UIDAI Aadhaar)
# --------------------------------------------------------------------------

_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_checksum(digits: str) -> int:
    """Return the Verhoeff check value of `digits`. 0 means valid."""
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c


def verhoeff_check_digit(payload: str) -> str:
    """Compute the check digit to append to an 11-digit payload."""
    c = 0
    for i, ch in enumerate(reversed(payload)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


def validate_aadhaar(value: str) -> tuple[bool, str]:
    raw = re.sub(r"[\s-]", "", value or "")
    if not re.fullmatch(r"\d{12}", raw):
        return False, "Aadhaar must be exactly 12 digits"
    if raw[0] in "01":
        # UIDAI never issues numbers beginning 0 or 1. Structurally parseable,
        # but not a live number. Specimen data uses this range by design.
        if verhoeff_checksum(raw) != 0:
            return False, "Verhoeff checksum failed"
        return True, "Verhoeff OK (reserved/non-issuable range - specimen)"
    if verhoeff_checksum(raw) != 0:
        return False, "Verhoeff checksum failed"
    return True, "Verhoeff OK"


# --------------------------------------------------------------------------
# PAN (Income Tax Department)
# --------------------------------------------------------------------------

# 4th character encodes the holder type.
PAN_HOLDER_TYPES = {
    "A": "Association of Persons (AOP)",
    "B": "Body of Individuals (BOI)",
    "C": "Company",
    "F": "Firm / LLP",
    "G": "Government Agency",
    "H": "Hindu Undivided Family (HUF)",
    "J": "Artificial Juridical Person",
    "L": "Local Authority",
    "P": "Individual",
    "T": "Trust",
}


def validate_pan(value: str, expect_holder_type: str | None = None) -> tuple[bool, str]:
    raw = (value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", raw):
        return False, "PAN must be 5 letters + 4 digits + 1 letter"
    holder = raw[3]
    if holder not in PAN_HOLDER_TYPES:
        return False, f"invalid holder-type code '{holder}' at position 4"
    if expect_holder_type and holder != expect_holder_type:
        return (
            False,
            f"holder type is {PAN_HOLDER_TYPES[holder]}, expected "
            f"{PAN_HOLDER_TYPES[expect_holder_type]}",
        )
    return True, f"format OK ({PAN_HOLDER_TYPES[holder]})"


# --------------------------------------------------------------------------
# GSTIN (GSTN) - 15 chars: 2 state + 10 PAN + 1 entity + 'Z' + 1 check char
# --------------------------------------------------------------------------

_GST_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

GST_STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli and Daman & Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar",
    "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}


def gstin_check_char(first14: str) -> str:
    """Standard GSTN mod-36 check character over the first 14 characters."""
    total = 0
    for i, ch in enumerate(first14.upper()):
        val = _GST_ALPHABET.index(ch)
        weight = 2 if (i % 2) else 1   # positions 1,3,5.. weight 1; 2,4,6.. weight 2
        prod = val * weight
        total += prod // 36 + prod % 36
    return _GST_ALPHABET[(36 - (total % 36)) % 36]


def validate_gstin(value: str, expect_pan: str | None = None) -> tuple[bool, str]:
    raw = (value or "").strip().upper()
    if not re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]", raw):
        return False, "GSTIN does not match the 15-character structure"
    state = raw[:2]
    if state not in GST_STATE_CODES:
        return False, f"unknown state code '{state}'"
    expected = gstin_check_char(raw[:14])
    if raw[14] != expected:
        return False, f"mod-36 checksum failed (expected '{expected}', found '{raw[14]}')"
    if expect_pan and raw[2:12] != expect_pan.upper():
        return False, f"embedded PAN {raw[2:12]} does not match declared PAN {expect_pan}"
    return True, f"checksum OK ({GST_STATE_CODES[state]})"


# --------------------------------------------------------------------------
# Other identifier formats
# --------------------------------------------------------------------------

def validate_udyam(value: str) -> tuple[bool, str]:
    raw = (value or "").strip().upper()
    if not re.fullmatch(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", raw):
        return False, "expected UDYAM-XX-00-0000000"
    return True, "format OK"


def validate_cin(value: str, expect_state: str | None = None) -> tuple[bool, str]:
    raw = (value or "").strip().upper()
    m = re.fullmatch(r"([UL])(\d{5})([A-Z]{2})(\d{4})([A-Z]{3})(\d{6})", raw)
    if not m:
        return False, "expected 21 characters: U/L + 5 digits + 2 letters + 4 digits + 3 letters + 6 digits"
    listing, _ind, state, year, ownership, _num = m.groups()
    if ownership not in {"PTC", "PLC", "OPC", "NPL", "FTC", "GOI", "SGC", "ULL", "ULT"}:
        return False, f"unknown ownership code '{ownership}'"
    if not (1850 <= int(year) <= 2100):
        return False, f"implausible incorporation year '{year}'"
    if expect_state and state != expect_state:
        return False, f"state code {state} does not match GSTIN state {expect_state}"
    kind = "Unlisted" if listing == "U" else "Listed"
    return True, f"format OK ({kind}, {ownership}, {year})"


def validate_name_match(a: str, b: str) -> tuple[bool, str]:
    """Compare two legal names after light normalisation."""
    def norm(s):
        s = (s or "").upper()
        s = re.sub(r"\b(PVT|PRIVATE)\b", "PRIVATE", s)
        s = re.sub(r"\b(LTD|LIMITED)\b", "LIMITED", s)
        s = re.sub(r"[^A-Z0-9]+", " ", s).strip()
        return s
    na, nb = norm(a), norm(b)
    if na == nb:
        return True, "names match"
    return False, f"name mismatch: '{a}' vs '{b}'"


# --------------------------------------------------------------------------
# Generation helpers (used to build the specimen datasets)
# --------------------------------------------------------------------------

def make_aadhaar(seed11: str) -> str:
    """Build a Verhoeff-valid 12-digit specimen number from an 11-digit seed.
    Seed must start 0 or 1 so the result can never collide with a live number."""
    assert re.fullmatch(r"[01]\d{10}", seed11), "seed must be 11 digits starting 0/1"
    return seed11 + verhoeff_check_digit(seed11)


def make_gstin(state: str, pan: str, entity: str = "1") -> str:
    body = f"{state}{pan.upper()}{entity}Z"
    return body + gstin_check_char(body)


def break_checksum(value: str) -> str:
    """Return `value` with its last character changed to a wrong one."""
    last = value[-1]
    alphabet = _GST_ALPHABET if last.isalpha() or not value[-2].isdigit() else "0123456789"
    if value[-1].isdigit() and value[:-1].isdigit():
        alphabet = "0123456789"
    nxt = alphabet[(alphabet.index(last) + 1) % len(alphabet)]
    return value[:-1] + nxt
