"""Shared helper utilities."""

import uuid
import hashlib
from datetime import date, datetime
from typing import Optional


def generate_uid(*parts: str) -> str:
    """Generate a deterministic UID from parts (used as graph node keys)."""
    combined = "|".join(str(p) for p in parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def generate_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def generate_irn_hash(gstin: str, invoice_number: str, fy: str) -> str:
    """Generate a deterministic 64-char IRN hash."""
    data = f"{gstin}|{invoice_number}|{fy}"
    return hashlib.sha256(data.encode()).hexdigest()


def financial_year_from_date(d: date) -> str:
    """Get financial year string (e.g., '2024-25') from a date."""
    if d.month >= 4:
        return f"{d.year}-{str(d.year + 1)[-2:]}"
    return f"{d.year - 1}-{str(d.year)[-2:]}"


def return_period_from_date(d: date) -> str:
    """Convert a date to MMYYYY return period format."""
    return d.strftime("%m%Y")


def date_from_return_period(period: str) -> date:
    """Convert MMYYYY to the last day of that month."""
    month = int(period[:2])
    year = int(period[2:])
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def calculate_interest(principal: float, rate_pct: float = 18.0, days: int = 30) -> float:
    """Calculate simple interest liability u/s 50 CGST Act. Default 18% p.a."""
    return round(principal * (rate_pct / 100) * (days / 365), 2)


def severity_from_amount(amount: float) -> str:
    """Determine severity based on financial impact."""
    if amount >= 500000:
        return "CRITICAL"
    elif amount >= 100000:
        return "HIGH"
    elif amount >= 10000:
        return "MEDIUM"
    return "LOW"


def values_match(v1: float, v2: float, abs_tol: float = 1.0, pct_tol: float = 0.001) -> bool:
    """Check if two monetary values match within tolerance."""
    if abs(v1 - v2) <= abs_tol:
        return True
    if v1 != 0 and abs(v1 - v2) / abs(v1) <= pct_tol:
        return True
    if v2 != 0 and abs(v1 - v2) / abs(v2) <= pct_tol:
        return True
    return False


def paginate_results(items: list, page: int = 1, page_size: int = 50) -> dict:
    """Apply pagination to a list of items."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
