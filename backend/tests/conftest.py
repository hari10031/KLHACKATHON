"""
Pytest configuration and shared fixtures.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j execute_query to return empty results."""
    with patch("app.database.execute_query", return_value=[]) as mock:
        yield mock


@pytest.fixture
def sample_gstin():
    return "27AADCB2230M1ZT"


@pytest.fixture
def sample_period():
    return "032025"


@pytest.fixture
def sample_invoice_data():
    return {
        "invoice_number": "INV-2025-001",
        "invoice_date": "2025-03-15",
        "seller_gstin": "27AADCB2230M1ZT",
        "buyer_gstin": "29AAGCR4375J1ZU",
        "taxable_value": 100000.0,
        "cgst": 9000.0,
        "sgst": 9000.0,
        "igst": 0.0,
        "total_tax": 18000.0,
        "total_value": 118000.0,
        "tax_rate": 18,
    }


@pytest.fixture
def sample_mismatch_data():
    return {
        "mismatch_id": "MM-TEST-001",
        "mismatch_type": "VALUE_MISMATCH",
        "severity": "HIGH",
        "gstin": "27AADCB2230M1ZT",
        "return_period": "032025",
        "seller_gstin": "29AAGCR4375J1ZU",
        "buyer_gstin": "27AADCB2230M1ZT",
        "invoice_number": "INV-2025-001",
        "seller_value": 100000.0,
        "buyer_value": 95000.0,
        "itc_at_risk": 900.0,
        "composite_risk_score": 0.65,
        "description": "Taxable value mismatch of ₹5,000",
    }
