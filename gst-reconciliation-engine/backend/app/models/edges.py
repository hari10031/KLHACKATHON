"""Pydantic models for all Knowledge Graph edge/relationship types."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class HasGSTIN(BaseModel):
    """Taxpayer -[HAS_GSTIN]-> GSTIN"""
    primary: bool = Field(default=True, description="Whether this is the primary GSTIN")


class IssuedInvoice(BaseModel):
    """GSTIN -[ISSUED_INVOICE]-> Invoice (supplier side)"""
    financial_year: str = Field(..., description="e.g. 2024-25")


class ReceivedInvoice(BaseModel):
    """GSTIN -[RECEIVED_INVOICE]-> Invoice (buyer side)"""
    financial_year: str = Field(..., description="e.g. 2024-25")


class HasIRN(BaseModel):
    """Invoice -[HAS_IRN]-> IRN"""
    generated_at: Optional[str] = None


class ReportedIn(BaseModel):
    """Invoice -[REPORTED_IN]-> Return"""
    section: str = Field(..., description="e.g. B2B, B2C, CDNR, AT, HSN")
    reported_value: Optional[float] = None
    reported_tax: Optional[float] = None


class HasLineItem(BaseModel):
    """Invoice -[HAS_LINE_ITEM]-> LineItem"""
    line_number: int = Field(..., ge=1)


class CoveredByEWBill(BaseModel):
    """Invoice -[COVERED_BY_EWBILL]-> EWayBill"""
    pass


class MatchedWith(BaseModel):
    """Invoice -[MATCHED_WITH]-> Invoice (cross-return matching)"""
    match_score: float = Field(..., ge=0, le=100)
    mismatch_fields: List[str] = Field(default_factory=list)
    match_type: str = Field(default="exact", description="exact | partial | fuzzy")


class FiledReturn(BaseModel):
    """GSTIN -[FILED_RETURN]-> Return"""
    arn: Optional[str] = Field(None, description="Acknowledgement Reference Number")
    filing_delay_days: int = Field(default=0, ge=0)


class TransactsWith(BaseModel):
    """GSTIN -[TRANSACTS_WITH]-> GSTIN (aggregated relationship)"""
    total_transactions: int = Field(default=0, ge=0)
    total_value: float = Field(default=0.0, ge=0)
    first_transaction_date: Optional[date] = None
    last_transaction_date: Optional[date] = None


class ITCClaimedVia(BaseModel):
    """Invoice -[ITC_CLAIMED_VIA]-> Return (GSTR-3B claim)"""
    claimed_amount: float = Field(..., ge=0)
    eligible_amount: float = Field(..., ge=0)
    claim_period: str = Field(..., description="MMYYYY")


class PaidVia(BaseModel):
    """Invoice -[PAID_VIA]-> BankTransaction"""
    payment_date: Optional[date] = None
    partial: bool = False


class CorrespondsTo(BaseModel):
    """PurchaseRegisterEntry -[CORRESPONDS_TO]-> Invoice"""
    matched_on: str = Field(default="invoice_number", description="Field used for matching")
    confidence: float = Field(default=1.0, ge=0, le=1)
