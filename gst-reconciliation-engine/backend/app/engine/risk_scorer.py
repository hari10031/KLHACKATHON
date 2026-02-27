"""
Composite Risk Scorer — combines financial impact, probability, and vendor risk.
Formula: 0.4 × Financial Impact + 0.3 × Probability + 0.3 × Vendor Risk (each 0-100)
"""

from app.models.mismatch import Mismatch, CompositeRiskScore, Severity, MismatchType
from app.database import execute_query
from loguru import logger


# Severity-based probability estimates
PROBABILITY_MAP = {
    MismatchType.VALUE_MISMATCH: 70,
    MismatchType.TAX_RATE_MISMATCH: 80,
    MismatchType.MISSING_IN_GSTR2B: 90,
    MismatchType.MISSING_IN_GSTR1: 85,
    MismatchType.DUPLICATE: 75,
    MismatchType.ITC_OVERCLAIM: 85,
    MismatchType.PERIOD_MISMATCH: 40,
    MismatchType.PHANTOM_INVOICE: 95,
    MismatchType.CIRCULAR_TRADE: 80,
    MismatchType.IRN_INVALID: 60,
    MismatchType.EWB_MISMATCH: 50,
}

# Financial impact thresholds (INR) for normalizing to 0-100
IMPACT_THRESHOLDS = [
    (5000000, 100),    # ₹50L+ → score 100
    (1000000, 85),     # ₹10L+ → score 85
    (500000, 70),      # ₹5L+  → score 70
    (100000, 55),      # ₹1L+  → score 55
    (50000, 40),       # ₹50K+ → score 40
    (10000, 25),       # ₹10K+ → score 25
    (0, 10),           # Any    → score 10
]


def compute_composite_risk(mismatch: Mismatch) -> float:
    """
    Compute the composite risk score for a mismatch.
    
    Returns a score 0-100.
    """
    # Financial Impact Score (0-100)
    total_exposure = mismatch.financial_impact.total_exposure
    fi_score = 10
    for threshold, score in IMPACT_THRESHOLDS:
        if total_exposure >= threshold:
            fi_score = score
            break

    # Probability Score (0-100)
    prob_score = PROBABILITY_MAP.get(mismatch.mismatch_type, 50)
    # Adjust by confidence
    if mismatch.root_cause and mismatch.root_cause.confidence:
        prob_score = prob_score * (mismatch.root_cause.confidence / 100)

    # Vendor Risk Score (0-100)
    vendor_risk = _get_vendor_risk(mismatch.supplier_gstin)

    composite = CompositeRiskScore(
        financial_impact_score=fi_score,
        probability_score=prob_score,
        vendor_risk_score=vendor_risk,
    )

    mismatch.composite_risk_score = composite.composite
    return composite.composite


def _get_vendor_risk(gstin: str) -> float:
    """Fetch vendor risk score from Neo4j (stored by Level 4)."""
    if not gstin:
        return 50.0

    try:
        result = execute_query("""
            MATCH (g:GSTIN {gstin_number: $gstin})
            RETURN g.risk_score AS risk, g.status AS status
        """, {"gstin": gstin})

        if result:
            risk = result[0].get("risk")
            status = result[0].get("status", "active")
            if risk is not None:
                return float(risk)
            # Fallback based on status
            if status == "cancelled":
                return 90.0
            elif status == "suspended":
                return 70.0
        return 50.0
    except Exception:
        return 50.0


def batch_compute_risk(mismatches: list) -> list:
    """Compute composite risk for a batch of mismatches."""
    for mm in mismatches:
        compute_composite_risk(mm)
    return sorted(mismatches, key=lambda m: m.composite_risk_score, reverse=True)
