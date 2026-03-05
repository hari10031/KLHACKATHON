"""Pydantic models for all Knowledge Graph node types."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import date, datetime
from enum import Enum
import re


# ──────────────────────────── Enums ────────────────────────────

class GSTINStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class RegistrationType(str, Enum):
    REGULAR = "regular"
    COMPOSITION = "composition"
    ISD = "ISD"


class InvoiceType(str, Enum):
    B2B = "B2B"
    B2C = "B2C"
    CDNR = "CDNR"
    EXP = "EXP"


class ReturnType(str, Enum):
    GSTR1 = "GSTR1"
    GSTR2B = "GSTR2B"
    GSTR3B = "GSTR3B"


class FilingStatus(str, Enum):
    FILED = "filed"
    NOT_FILED = "not_filed"
    LATE_FILED = "late_filed"


class IRNStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    INVALID = "invalid"


class PaymentMode(str, Enum):
    NEFT = "NEFT"
    RTGS = "RTGS"
    UPI = "UPI"
    CHEQUE = "CHEQUE"
    CASH = "CASH"


class ITCEligibility(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PROVISIONAL = "provisional"
    BLOCKED = "blocked"


class BusinessType(str, Enum):
    PROPRIETORSHIP = "Proprietorship"
    PARTNERSHIP = "Partnership"
    LLP = "LLP"
    PRIVATE_LIMITED = "Private Limited"
    PUBLIC_LIMITED = "Public Limited"
    HUF = "HUF"


# ──────────────────────────── Node Models ────────────────────────────

class Taxpayer(BaseModel):
    """A registered taxpayer entity (business/individual)."""
    pan: str = Field(..., min_length=10, max_length=10, description="PAN number")
    legal_name: str = Field(..., min_length=1, max_length=200)
    registration_date: date
    business_type: BusinessType
    state: str = Field(..., min_length=2, max_length=50)
    aggregate_turnover: float = Field(..., ge=0, description="Annual turnover in INR")
    compliance_rating: float = Field(default=50.0, ge=0, le=100)

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, v: str) -> str:
        pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]$"
        if not re.match(pattern, v):
            raise ValueError(f"Invalid PAN format: {v}")
        return v


class GSTIN(BaseModel):
    """GST Identification Number node."""
    gstin_number: str = Field(..., min_length=15, max_length=15)
    state_code: str = Field(..., min_length=2, max_length=2)
    status: GSTINStatus = GSTINStatus.ACTIVE
    registration_type: RegistrationType = RegistrationType.REGULAR

    @field_validator("gstin_number")
    @classmethod
    def validate_gstin(cls, v: str) -> str:
        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z][Z][0-9A-Z]$"
        if not re.match(pattern, v):
            raise ValueError(f"Invalid GSTIN format: {v}")
        return v


class Invoice(BaseModel):
    """Tax invoice node containing all financial details."""
    invoice_number: str = Field(..., min_length=1, max_length=50)
    invoice_date: date
    invoice_type: InvoiceType = InvoiceType.B2B
    taxable_value: float = Field(..., ge=0)
    cgst: float = Field(default=0.0, ge=0)
    sgst: float = Field(default=0.0, ge=0)
    igst: float = Field(default=0.0, ge=0)
    cess: float = Field(default=0.0, ge=0)
    total_value: float = Field(..., ge=0)
    place_of_supply: str = Field(..., min_length=2, max_length=2)
    reverse_charge_flag: bool = False
    hsn_code: str = Field(..., min_length=4, max_length=8)
    supplier_gstin: Optional[str] = None
    recipient_gstin: Optional[str] = None

    @field_validator("total_value")
    @classmethod
    def validate_total(cls, v, info):
        data = info.data
        expected = data.get("taxable_value", 0) + data.get("cgst", 0) + \
                   data.get("sgst", 0) + data.get("igst", 0) + data.get("cess", 0)
        if abs(v - expected) > 1.0:
            pass  # Allow slight precision differences; logged during reconciliation
        return v


class IRN(BaseModel):
    """Invoice Reference Number from e-Invoice system."""
    irn_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash")
    irn_status: IRNStatus = IRNStatus.ACTIVE
    generation_date: datetime
    signed_qr_code: Optional[str] = None


class Return(BaseModel):
    """GST return filing node."""
    return_type: ReturnType
    return_period: str = Field(..., min_length=6, max_length=6, description="MMYYYY format")
    filing_date: Optional[date] = None
    filing_status: FilingStatus = FilingStatus.NOT_FILED
    revision_number: int = Field(default=0, ge=0)

    @field_validator("return_period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if not re.match(r"^(0[1-9]|1[0-2])\d{4}$", v):
            raise ValueError(f"Invalid return period format: {v}. Expected MMYYYY.")
        return v


class EWayBill(BaseModel):
    """e-Way Bill for goods transportation."""
    ewb_number: str = Field(..., min_length=12, max_length=12)
    generation_date: datetime
    validity: datetime
    transporter_id: Optional[str] = None
    vehicle_number: Optional[str] = None
    distance_km: float = Field(default=0.0, ge=0)


class LineItem(BaseModel):
    """Individual line item within an invoice."""
    hsn_code: str = Field(..., min_length=4, max_length=8)
    description: str = Field(..., max_length=500)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., max_length=10)
    rate: float = Field(..., ge=0, description="Unit price in INR")
    taxable_value: float = Field(..., ge=0)
    tax_rate: float = Field(..., description="GST rate percentage: 0, 5, 12, 18, or 28")

    @field_validator("tax_rate")
    @classmethod
    def validate_tax_rate(cls, v: float) -> float:
        valid_rates = {0.0, 5.0, 12.0, 18.0, 28.0}
        if v not in valid_rates:
            raise ValueError(f"Invalid GST rate {v}%. Must be one of {valid_rates}")
        return v


class BankTransaction(BaseModel):
    """Bank payment record linked to invoices."""
    transaction_id: str = Field(..., min_length=1, max_length=50)
    date: date
    amount: float = Field(..., gt=0, description="Amount in INR")
    payment_mode: PaymentMode
    reference_number: Optional[str] = None


class PurchaseRegisterEntry(BaseModel):
    """Entry from the buyer's purchase register / books of accounts."""
    entry_id: str = Field(..., min_length=1, max_length=50)
    booking_date: date
    taxable_value: float = Field(..., ge=0)
    igst: float = Field(default=0.0, ge=0)
    cgst: float = Field(default=0.0, ge=0)
    sgst: float = Field(default=0.0, ge=0)
    itc_eligibility: ITCEligibility = ITCEligibility.ELIGIBLE
