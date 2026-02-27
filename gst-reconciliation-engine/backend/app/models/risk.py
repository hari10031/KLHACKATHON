"""Pydantic models for vendor compliance risk prediction."""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class RiskLabel(str, Enum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    NON_COMPLIANT = "non_compliant"


class RiskFactor(BaseModel):
    """A contributing risk factor with SHAP-derived weight."""
    factor: str
    description: str
    contribution_weight: float = Field(..., description="SHAP value contribution")
    direction: str = Field(default="increases_risk", description="increases_risk | decreases_risk")


class VendorRiskPrediction(BaseModel):
    """Complete risk prediction output for a vendor."""
    gstin: str
    risk_score: float = Field(..., ge=0, le=100)
    risk_label: RiskLabel
    risk_factors: List[RiskFactor] = Field(default_factory=list)
    prediction_confidence: float = Field(..., ge=0, le=100)
    recommended_itc_exposure_limit: float = Field(default=0.0, ge=0, description="Recommended max ITC exposure in INR")

    # Feature values
    degree_centrality: Optional[float] = None
    betweenness_centrality: Optional[float] = None
    pagerank: Optional[float] = None
    clustering_coefficient: Optional[float] = None
    filing_delay_avg: Optional[float] = None
    mismatch_frequency: Optional[float] = None
    mismatch_value_ratio: Optional[float] = None


class ModelMetrics(BaseModel):
    """ML model evaluation metrics."""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_roc: float
    training_samples: int
    feature_importance: List[dict] = Field(default_factory=list)
