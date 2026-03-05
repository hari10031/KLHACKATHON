"""Pydantic models for audit trail and reporting."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from app.models.mismatch import Severity, MismatchType, FinancialImpact, ChainHop


class AuditFinding(BaseModel):
    """A single audit finding with full narrative and evidence."""
    finding_id: str
    finding_date: datetime = Field(default_factory=datetime.utcnow)
    severity: Severity
    mismatch_type: MismatchType
    itc_at_risk: float = Field(default=0.0, ge=0)

    # Narrative
    narrative: str = Field(..., description="Natural-language description of the finding")

    # Graph traversal path
    traversal_path: List[ChainHop] = Field(default_factory=list)

    # Root cause
    root_cause_classification: str
    root_cause_confidence: float = Field(..., ge=0, le=100)
    supporting_evidence: List[str] = Field(default_factory=list)
    alternative_explanations: List[str] = Field(default_factory=list)

    # Financial breakdown
    financial_breakdown: Dict[str, float] = Field(default_factory=dict)

    # Actions
    recommended_actions: List[str] = Field(default_factory=list)

    # Regulatory
    regulatory_references: List[str] = Field(default_factory=list)

    # Context
    invoice_number: Optional[str] = None
    supplier_gstin: Optional[str] = None
    buyer_gstin: Optional[str] = None
    return_period: Optional[str] = None


class AuditReport(BaseModel):
    """Complete audit report for a GSTIN and return period."""
    report_id: str
    gstin: str
    return_period: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_findings: int = 0
    critical_findings: int = 0
    total_itc_at_risk: float = 0.0
    findings: List[AuditFinding] = Field(default_factory=list)
    summary_narrative: Optional[str] = None
