"""Pydantic models for mismatch classification and risk scoring."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime


class MismatchType(str, Enum):
    VALUE_MISMATCH = "VALUE_MISMATCH"
    TAX_RATE_MISMATCH = "TAX_RATE_MISMATCH"
    MISSING_IN_GSTR2B = "MISSING_IN_GSTR2B"
    MISSING_IN_GSTR1 = "MISSING_IN_GSTR1"
    DUPLICATE = "DUPLICATE"
    ITC_OVERCLAIM = "ITC_OVERCLAIM"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    PHANTOM_INVOICE = "PHANTOM_INVOICE"
    CIRCULAR_TRADE = "CIRCULAR_TRADE"
    IRN_INVALID = "IRN_INVALID"
    EWB_MISMATCH = "EWB_MISMATCH"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskCategory(str, Enum):
    ITC_REVERSAL = "ITC_REVERSAL"
    DEMAND_NOTICE = "DEMAND_NOTICE"
    AUDIT_TRIGGER = "AUDIT_TRIGGER"
    INFORMATIONAL = "INFORMATIONAL"


class MismatchStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class FinancialImpact(BaseModel):
    """Monetary impact assessment of a mismatch."""
    itc_at_risk: float = Field(default=0.0, ge=0, description="ITC amount in jeopardy (INR)")
    potential_interest_liability: float = Field(default=0.0, ge=0, description="Interest u/s 50 (INR)")
    penalty_exposure: float = Field(default=0.0, ge=0, description="Penalty u/s 122/125 (INR)")

    @property
    def total_exposure(self) -> float:
        return self.itc_at_risk + self.potential_interest_liability + self.penalty_exposure


class RootCause(BaseModel):
    """Root cause classification for a mismatch."""
    classification: str = Field(..., description="Human-readable cause category")
    confidence: float = Field(..., ge=0, le=100, description="Confidence percentage")
    evidence_paths: List[str] = Field(default_factory=list, description="Graph traversal paths as evidence")
    alternative_explanations: List[str] = Field(default_factory=list)


class ChainHop(BaseModel):
    """A single hop in the ITC validation chain."""
    hop_number: int
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relationship: str
    status: str = Field(default="valid", description="valid | broken | warning")
    details: Optional[str] = None


class AffectedChain(BaseModel):
    """Complete ITC chain with break-point information."""
    hops: List[ChainHop] = Field(default_factory=list)
    break_point: Optional[int] = Field(None, description="Hop number where chain breaks")
    chain_completeness: float = Field(default=0.0, ge=0, le=100)


class ResolutionAction(BaseModel):
    """Recommended action to resolve a mismatch."""
    action_id: int
    description: str
    priority: str = Field(default="MEDIUM")
    deadline_days: Optional[int] = None
    regulatory_reference: Optional[str] = None


class Mismatch(BaseModel):
    """Complete mismatch record with full classification."""
    mismatch_id: str
    mismatch_type: MismatchType
    severity: Severity
    status: MismatchStatus = MismatchStatus.OPEN
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    # Financial
    financial_impact: FinancialImpact
    risk_category: RiskCategory

    # Root cause
    root_cause: RootCause
    affected_chain: Optional[AffectedChain] = None

    # Resolution
    resolution_actions: List[ResolutionAction] = Field(default_factory=list)

    # Context
    supplier_gstin: Optional[str] = None
    buyer_gstin: Optional[str] = None
    invoice_number: Optional[str] = None
    return_period: Optional[str] = None
    gstr1_value: Optional[float] = None
    gstr2b_value: Optional[float] = None

    # Composite risk score
    composite_risk_score: float = Field(default=0.0, ge=0, le=100)


class CompositeRiskScore(BaseModel):
    """
    Composite Risk Score = 0.4 × Financial Impact Score
                         + 0.3 × Probability Score
                         + 0.3 × Vendor Risk Score
    Each sub-score is 0-100.
    """
    financial_impact_score: float = Field(default=0.0, ge=0, le=100)
    probability_score: float = Field(default=0.0, ge=0, le=100)
    vendor_risk_score: float = Field(default=0.0, ge=0, le=100)

    @property
    def composite(self) -> float:
        return round(
            0.4 * self.financial_impact_score +
            0.3 * self.probability_score +
            0.3 * self.vendor_risk_score,
            2
        )


class ReconciliationSummary(BaseModel):
    """Summary statistics for a reconciliation run."""
    run_id: str
    gstin: str
    return_period: str
    run_timestamp: datetime
    total_invoices: int = 0
    matched: int = 0
    partial_matched: int = 0
    unmatched: int = 0
    mismatches_by_type: Dict[str, int] = Field(default_factory=dict)
    mismatches_by_severity: Dict[str, int] = Field(default_factory=dict)
    total_itc_claimed: float = 0.0
    itc_at_risk: float = 0.0
    itc_verified: float = 0.0
    net_exposure: float = 0.0
    mismatches: List[Mismatch] = Field(default_factory=list)
