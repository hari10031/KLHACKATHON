"""GSTIN validation and utility functions."""

import re
from typing import Optional

# Indian state codes (first 2 digits of GSTIN)
STATE_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra & Nagar Haveli", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala",
    "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman & Nicobar",
    "36": "Telangana", "37": "Andhra Pradesh",
}

GSTIN_PATTERN = re.compile(r"^([0-9]{2})([A-Z]{5}[0-9]{4}[A-Z])([1-9A-Z])([Z])([0-9A-Z])$")


def validate_gstin(gstin: str) -> bool:
    """Validate GSTIN format: 2-digit state + 10-char PAN + entity + Z + check."""
    if not gstin or len(gstin) != 15:
        return False
    match = GSTIN_PATTERN.match(gstin)
    if not match:
        return False
    state_code = match.group(1)
    return state_code in STATE_CODES


def extract_pan_from_gstin(gstin: str) -> Optional[str]:
    """Extract the 10-character PAN from a GSTIN."""
    if validate_gstin(gstin):
        return gstin[2:12]
    return None


def get_state_from_gstin(gstin: str) -> Optional[str]:
    """Get state name from GSTIN's state code."""
    if validate_gstin(gstin):
        return STATE_CODES.get(gstin[:2])
    return None


def get_state_code_from_gstin(gstin: str) -> Optional[str]:
    """Extract the 2-digit state code from GSTIN."""
    if validate_gstin(gstin):
        return gstin[:2]
    return None


def generate_gstin_check_digit(gstin_without_check: str) -> str:
    """Generate the check digit for a 14-character GSTIN prefix."""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    factor = 1
    total = 0
    for ch in gstin_without_check:
        idx = chars.index(ch)
        idx *= factor
        total += (idx // 36) + (idx % 36)
        factor = 2 if factor == 1 else 1
    remainder = total % 36
    check_digit = chars[(36 - remainder) % 36]
    return check_digit


def normalize_invoice_number(inv_no: str) -> str:
    """
    Normalize invoice number for matching:
    - Strip whitespace
    - Remove common prefixes (INV-, INV/, BILL-)
    - Remove leading zeros
    - Uppercase
    - Remove special characters except alphanumerics and hyphens
    """
    if not inv_no:
        return ""
    normalized = inv_no.strip().upper()
    # Remove common prefixes
    for prefix in ["INV-", "INV/", "BILL-", "BILL/", "TAX-", "TAX/"]:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    # Remove special chars except alphanumeric and hyphen
    normalized = re.sub(r"[^A-Z0-9\-]", "", normalized)
    # Remove leading zeros
    normalized = normalized.lstrip("0") or "0"
    return normalized
