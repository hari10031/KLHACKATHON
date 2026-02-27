"""
Unit tests for the reconciliation engine and utilities.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.utils.gstin import validate_gstin, extract_pan, get_state_name, normalize_invoice_number
from app.utils.helpers import (
    generate_uuid, financial_year_from_date, return_period_from_date,
    calculate_interest, severity_from_amount, values_match,
)
from app.models.mismatch import Severity, MismatchType, CompositeRiskScore


class TestGSTINUtils:
    def test_valid_gstin(self):
        # 15 chars, starts with state code, has PAN structure
        assert validate_gstin("27AADCB2230M1ZT") is True

    def test_invalid_gstin_length(self):
        assert validate_gstin("27AADCB2230M1Z") is False
        assert validate_gstin("") is False

    def test_invalid_gstin_format(self):
        assert validate_gstin("00AADCB2230M1ZT") is False  # invalid state

    def test_extract_pan(self):
        assert extract_pan("27AADCB2230M1ZT") == "AADCB2230M"

    def test_get_state_name(self):
        assert get_state_name("27") == "Maharashtra"
        assert get_state_name("29") == "Karnataka"
        assert get_state_name("99") is None

    def test_normalize_invoice(self):
        assert normalize_invoice_number("INV/2025/001") == "INV2025001"
        assert normalize_invoice_number("inv-2025-001") == "INV2025001"
        assert normalize_invoice_number("  INV 001  ") == "INV001"


class TestHelpers:
    def test_generate_uuid(self):
        uid = generate_uuid()
        assert len(uid) == 36  # UUID4 format

    def test_financial_year(self):
        from datetime import date
        assert financial_year_from_date(date(2025, 3, 15)) == "2024-25"
        assert financial_year_from_date(date(2025, 4, 1)) == "2025-26"

    def test_return_period(self):
        from datetime import date
        assert return_period_from_date(date(2025, 3, 15)) == "032025"
        assert return_period_from_date(date(2024, 12, 1)) == "122024"

    def test_interest_calculation(self):
        interest = calculate_interest(100000, 30)
        expected = 100000 * 0.18 * (30 / 365)
        assert abs(interest - expected) < 0.01

    def test_severity_from_amount(self):
        assert severity_from_amount(600000) == Severity.CRITICAL
        assert severity_from_amount(200000) == Severity.HIGH
        assert severity_from_amount(50000) == Severity.MEDIUM
        assert severity_from_amount(5000) == Severity.LOW

    def test_values_match(self):
        assert values_match(100.0, 100.0) is True
        assert values_match(100.0, 100.5) is True  # within ₹1
        assert values_match(100.0, 102.0) is False
        assert values_match(10000.0, 10005.0) is True  # within 0.1%
        assert values_match(10000.0, 10020.0) is False


class TestCompositeRiskScore:
    def test_score_calculation(self):
        score = CompositeRiskScore(
            financial_impact_score=0.8,
            probability_score=0.6,
            vendor_risk_score=0.4,
        )
        # Formula: 0.4 * 0.8 + 0.3 * 0.6 + 0.3 * 0.4 = 0.32 + 0.18 + 0.12 = 0.62
        expected = 0.4 * 0.8 + 0.3 * 0.6 + 0.3 * 0.4
        assert abs(score.composite_score - expected) < 0.01

    def test_score_bounds(self):
        score = CompositeRiskScore(
            financial_impact_score=1.0,
            probability_score=1.0,
            vendor_risk_score=1.0,
        )
        assert score.composite_score <= 1.0

        score_low = CompositeRiskScore(
            financial_impact_score=0.0,
            probability_score=0.0,
            vendor_risk_score=0.0,
        )
        assert score_low.composite_score >= 0.0


class TestMismatchModels:
    def test_mismatch_types_exist(self):
        assert MismatchType.INVOICE_MISSING.value == "INVOICE_MISSING"
        assert MismatchType.CIRCULAR_TRADE.value == "CIRCULAR_TRADE"
        assert len(MismatchType) == 11

    def test_severity_ordering(self):
        assert Severity.CRITICAL.value == "CRITICAL"
        assert Severity.LOW.value == "LOW"


class TestReconciliationEngine:
    @patch("app.database.execute_query")
    def test_engine_init(self, mock_eq):
        from app.engine.reconciliation import ReconciliationEngine
        engine = ReconciliationEngine()
        assert engine.level1 is not None
        assert engine.level2 is not None
        assert engine.level3 is not None
        assert engine.level4 is not None

    @patch("app.database.execute_query")
    def test_get_all_gstins(self, mock_eq):
        mock_eq.return_value = [
            {"gstin": "27AADCB2230M1ZT"},
            {"gstin": "29AAGCR4375J1ZU"},
        ]
        from app.engine.reconciliation import ReconciliationEngine
        engine = ReconciliationEngine()
        gstins = engine.get_all_gstins()
        assert len(gstins) == 2
        assert "27AADCB2230M1ZT" in gstins


class TestDataGenerator:
    def test_generator_creates_data(self):
        from app.ingestion.generator import SyntheticDataGenerator
        gen = SyntheticDataGenerator(num_taxpayers=5, num_invoices=10, mismatch_rate=0.2)
        data = gen.generate_all()
        assert "taxpayers" in data
        assert "invoices" in data
        assert len(data["taxpayers"]) == 5
        assert len(data["invoices"]) >= 5  # may be slightly different due to randomness

    def test_generated_gstin_format(self):
        from app.ingestion.generator import SyntheticDataGenerator
        gen = SyntheticDataGenerator(num_taxpayers=3, num_invoices=5)
        data = gen.generate_all()
        for tp in data["taxpayers"]:
            gstin = tp["gstin_number"]
            assert len(gstin) == 15
            assert gstin[:2].isdigit()
