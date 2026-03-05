"""
Level 1: Direct Invoice Matching (1-hop)
Match GSTR-1 invoices with GSTR-2B by GSTIN pair + Invoice Number +
Invoice Date + Taxable Value within configurable tolerance.
Includes fuzzy matching for invoice numbers.
"""

from typing import List, Dict, Tuple, Optional
from fuzzywuzzy import fuzz
from loguru import logger
from dataclasses import dataclass
from datetime import datetime

from app.database import execute_query
from app.config import settings
from app.utils.gstin import normalize_invoice_number
from app.utils.helpers import values_match, generate_uuid, severity_from_amount
from app.models.mismatch import (
    Mismatch, MismatchType, Severity, RiskCategory, MismatchStatus,
    FinancialImpact, RootCause, ResolutionAction,
)


@dataclass
class MatchResult:
    """Result of matching a single invoice pair."""
    match_type: str  # "exact_match", "partial_match", "unmatched"
    match_score: float  # 0-100
    gstr1_invoice: dict
    gstr2b_invoice: Optional[dict]
    field_diffs: List[dict]
    mismatch: Optional[Mismatch] = None


class Level1Matcher:
    """
    Level 1 Direct Invoice Matching Engine.
    
    Performs 1-hop matching between GSTR-1 and GSTR-2B invoices.
    """

    def __init__(
        self,
        abs_tolerance: float = None,
        pct_tolerance: float = None,
        fuzzy_threshold: int = None,
    ):
        self.abs_tolerance = abs_tolerance or settings.MATCH_TOLERANCE_ABS
        self.pct_tolerance = pct_tolerance or settings.MATCH_TOLERANCE_PCT
        self.fuzzy_threshold = fuzzy_threshold or settings.FUZZY_MATCH_THRESHOLD

    def fetch_gstr1_invoices(self, gstin: str, return_period: str) -> List[dict]:
        """Fetch GSTR-1 invoices for a supplier GSTIN and period."""
        cypher = """
        MATCH (i:Invoice {source: 'GSTR1', supplier_gstin: $gstin})
        WHERE toString(i.invoice_date) STARTS WITH $year_month_prefix
        RETURN i {.*, uid: i.uid} AS invoice
        ORDER BY i.invoice_number
        """
        # Convert MMYYYY to YYYY-MM prefix
        month = return_period[:2]
        year = return_period[2:]
        prefix = f"{year}-{month}"

        return [r["invoice"] for r in execute_query(cypher, {
            "gstin": gstin, "year_month_prefix": prefix
        })]

    def fetch_gstr2b_invoices(self, gstin: str, return_period: str) -> List[dict]:
        """Fetch GSTR-2B invoices for a recipient GSTIN and period."""
        cypher = """
        MATCH (i:Invoice {source: 'GSTR2B', recipient_gstin: $gstin})
        WHERE toString(i.invoice_date) STARTS WITH $year_month_prefix
        RETURN i {.*, uid: i.uid} AS invoice
        ORDER BY i.invoice_number
        """
        month = return_period[:2]
        year = return_period[2:]
        prefix = f"{year}-{month}"

        return [r["invoice"] for r in execute_query(cypher, {
            "gstin": gstin, "year_month_prefix": prefix
        })]

    def match_invoices(self, gstin: str, return_period: str) -> List[MatchResult]:
        """
        Perform full Level 1 matching for a GSTIN and period.
        
        Returns list of MatchResult with match classification.
        """
        logger.info(f"Level 1 matching for GSTIN={gstin}, period={return_period}")

        gstr1_invoices = self.fetch_gstr1_invoices(gstin, return_period)
        gstr2b_invoices = self.fetch_gstr2b_invoices(gstin, return_period)

        logger.info(f"Found {len(gstr1_invoices)} GSTR-1, {len(gstr2b_invoices)} GSTR-2B invoices")

        results = []
        matched_2b_uids = set()

        # Build GSTR-2B index for quick lookup
        gstr2b_by_supplier = {}
        for inv in gstr2b_invoices:
            key = inv.get("supplier_gstin", "")
            if key not in gstr2b_by_supplier:
                gstr2b_by_supplier[key] = []
            gstr2b_by_supplier[key].append(inv)

        for gstr1_inv in gstr1_invoices:
            supplier = gstr1_inv.get("supplier_gstin", "")
            candidates = gstr2b_by_supplier.get(supplier, [])

            best_match = None
            best_score = 0
            best_diffs = []

            for gstr2b_inv in candidates:
                if gstr2b_inv["uid"] in matched_2b_uids:
                    continue
                score, diffs = self._compute_match_score(gstr1_inv, gstr2b_inv)
                if score > best_score:
                    best_score = score
                    best_match = gstr2b_inv
                    best_diffs = diffs

            if best_match and best_score >= 95:
                match_type = "exact_match"
                matched_2b_uids.add(best_match["uid"])
                results.append(MatchResult(
                    match_type=match_type,
                    match_score=best_score,
                    gstr1_invoice=gstr1_inv,
                    gstr2b_invoice=best_match,
                    field_diffs=[],
                ))
            elif best_match and best_score >= self.fuzzy_threshold:
                match_type = "partial_match"
                matched_2b_uids.add(best_match["uid"])
                mismatch = self._classify_mismatch(gstr1_inv, best_match, best_diffs)
                results.append(MatchResult(
                    match_type=match_type,
                    match_score=best_score,
                    gstr1_invoice=gstr1_inv,
                    gstr2b_invoice=best_match,
                    field_diffs=best_diffs,
                    mismatch=mismatch,
                ))
            else:
                # Unmatched — missing in GSTR-2B
                mismatch = self._create_missing_mismatch(gstr1_inv, "MISSING_IN_GSTR2B")
                results.append(MatchResult(
                    match_type="unmatched",
                    match_score=0,
                    gstr1_invoice=gstr1_inv,
                    gstr2b_invoice=None,
                    field_diffs=[],
                    mismatch=mismatch,
                ))

        # Check for unmatched GSTR-2B (missing in GSTR-1)
        for gstr2b_inv in gstr2b_invoices:
            if gstr2b_inv["uid"] not in matched_2b_uids:
                mismatch = self._create_missing_mismatch(gstr2b_inv, "MISSING_IN_GSTR1")
                results.append(MatchResult(
                    match_type="unmatched",
                    match_score=0,
                    gstr1_invoice={},
                    gstr2b_invoice=gstr2b_inv,
                    field_diffs=[],
                    mismatch=mismatch,
                ))

        logger.info(
            f"Level 1 results: "
            f"{sum(1 for r in results if r.match_type == 'exact_match')} exact, "
            f"{sum(1 for r in results if r.match_type == 'partial_match')} partial, "
            f"{sum(1 for r in results if r.match_type == 'unmatched')} unmatched"
        )

        return results

    def _compute_match_score(self, gstr1: dict, gstr2b: dict) -> Tuple[float, List[dict]]:
        """
        Compute a match score between two invoices.
        Score breakdown: invoice_number (40%), taxable_value (30%), 
        invoice_date (20%), tax_amounts (10%).
        """
        score = 0.0
        diffs = []

        # Invoice number match (40 points) — with fuzzy matching
        inv1 = normalize_invoice_number(gstr1.get("invoice_number", ""))
        inv2 = normalize_invoice_number(gstr2b.get("invoice_number", ""))

        if inv1 == inv2:
            score += 40
        else:
            fuzzy_score = fuzz.ratio(inv1, inv2)
            if fuzzy_score >= self.fuzzy_threshold:
                score += 40 * (fuzzy_score / 100)
                diffs.append({
                    "field": "invoice_number",
                    "gstr1_value": gstr1.get("invoice_number"),
                    "gstr2b_value": gstr2b.get("invoice_number"),
                    "fuzzy_score": fuzzy_score,
                })
            else:
                diffs.append({
                    "field": "invoice_number",
                    "gstr1_value": gstr1.get("invoice_number"),
                    "gstr2b_value": gstr2b.get("invoice_number"),
                    "fuzzy_score": fuzzy_score,
                })
                return score, diffs  # No point continuing if no invoice match

        # Taxable value match (30 points)
        v1 = float(gstr1.get("taxable_value", 0))
        v2 = float(gstr2b.get("taxable_value", 0))
        if values_match(v1, v2, self.abs_tolerance, self.pct_tolerance):
            score += 30
        else:
            diff_pct = abs(v1 - v2) / max(v1, 1) * 100
            score += max(0, 30 * (1 - diff_pct / 100))
            diffs.append({
                "field": "taxable_value",
                "gstr1_value": v1,
                "gstr2b_value": v2,
                "difference": round(v1 - v2, 2),
                "difference_pct": round(diff_pct, 2),
            })

        # Invoice date match (20 points)
        d1 = str(gstr1.get("invoice_date", ""))
        d2 = str(gstr2b.get("invoice_date", ""))
        if d1 == d2:
            score += 20
        else:
            diffs.append({
                "field": "invoice_date",
                "gstr1_value": d1,
                "gstr2b_value": d2,
            })
            # Partial credit for same month
            if d1[:7] == d2[:7]:
                score += 10

        # Tax amounts match (10 points)
        tax_fields = ["cgst", "sgst", "igst"]
        tax_score = 0
        for tf in tax_fields:
            t1 = float(gstr1.get(tf, 0))
            t2 = float(gstr2b.get(tf, 0))
            if values_match(t1, t2, self.abs_tolerance, self.pct_tolerance):
                tax_score += 10 / len(tax_fields)
            else:
                diffs.append({
                    "field": tf,
                    "gstr1_value": t1,
                    "gstr2b_value": t2,
                    "difference": round(t1 - t2, 2),
                })
        score += tax_score

        return round(score, 2), diffs

    def _classify_mismatch(self, gstr1: dict, gstr2b: dict, diffs: List[dict]) -> Mismatch:
        """Classify a partial match into a specific mismatch type."""
        diff_fields = {d["field"] for d in diffs}
        tax_amount = float(gstr1.get("igst", 0)) + float(gstr1.get("cgst", 0)) + float(gstr1.get("sgst", 0))

        # Determine mismatch type
        if "taxable_value" in diff_fields and ("cgst" in diff_fields or "sgst" in diff_fields or "igst" in diff_fields):
            mm_type = MismatchType.TAX_RATE_MISMATCH
            risk_cat = RiskCategory.ITC_REVERSAL
        elif "taxable_value" in diff_fields:
            mm_type = MismatchType.VALUE_MISMATCH
            risk_cat = RiskCategory.ITC_REVERSAL
        elif "invoice_date" in diff_fields and len(diff_fields) == 1:
            mm_type = MismatchType.PERIOD_MISMATCH
            risk_cat = RiskCategory.INFORMATIONAL
        else:
            mm_type = MismatchType.VALUE_MISMATCH
            risk_cat = RiskCategory.ITC_REVERSAL

        # Calculate financial impact
        value_diff = abs(
            float(gstr1.get("taxable_value", 0)) - float(gstr2b.get("taxable_value", 0))
        )
        tax_diff = abs(
            (float(gstr1.get("igst", 0)) + float(gstr1.get("cgst", 0)) + float(gstr1.get("sgst", 0))) -
            (float(gstr2b.get("igst", 0)) + float(gstr2b.get("cgst", 0)) + float(gstr2b.get("sgst", 0)))
        )

        sev = Severity(severity_from_amount(tax_diff))

        return Mismatch(
            mismatch_id=f"MM-L1-{generate_uuid()[:8]}",
            mismatch_type=mm_type,
            severity=sev,
            financial_impact=FinancialImpact(
                itc_at_risk=round(tax_diff, 2),
                potential_interest_liability=round(tax_diff * 0.18 / 12, 2),
                penalty_exposure=round(tax_diff * 0.1, 2) if sev in (Severity.CRITICAL, Severity.HIGH) else 0,
            ),
            risk_category=risk_cat,
            root_cause=RootCause(
                classification=f"{mm_type.value} between GSTR-1 and GSTR-2B",
                confidence=75.0,
                evidence_paths=[
                    f"GSTR-1 Invoice {gstr1.get('invoice_number')} -> Match attempt -> GSTR-2B Invoice {gstr2b.get('invoice_number')}"
                ],
            ),
            supplier_gstin=gstr1.get("supplier_gstin"),
            buyer_gstin=gstr1.get("recipient_gstin"),
            invoice_number=gstr1.get("invoice_number"),
            gstr1_value=float(gstr1.get("taxable_value", 0)),
            gstr2b_value=float(gstr2b.get("taxable_value", 0)),
            resolution_actions=[
                ResolutionAction(
                    action_id=1,
                    description="Verify invoice details with supplier",
                    priority="HIGH",
                    deadline_days=15,
                    regulatory_reference="Section 16(2)(aa) CGST Act",
                ),
                ResolutionAction(
                    action_id=2,
                    description="Check if amendment filed in subsequent period",
                    priority="MEDIUM",
                    deadline_days=30,
                ),
            ],
        )

    def _create_missing_mismatch(self, invoice: dict, direction: str) -> Mismatch:
        """Create mismatch for missing invoices."""
        mm_type = MismatchType.MISSING_IN_GSTR2B if direction == "MISSING_IN_GSTR2B" else MismatchType.MISSING_IN_GSTR1
        tax_amount = float(invoice.get("igst", 0)) + float(invoice.get("cgst", 0)) + float(invoice.get("sgst", 0))

        if mm_type == MismatchType.MISSING_IN_GSTR2B:
            risk_cat = RiskCategory.ITC_REVERSAL
            desc = "Invoice reported in GSTR-1 but not reflected in GSTR-2B. ITC cannot be claimed."
            actions = [
                ResolutionAction(
                    action_id=1,
                    description="Contact supplier to verify GSTR-1 filing",
                    priority="HIGH",
                    deadline_days=10,
                    regulatory_reference="Section 16(2)(aa) CGST Act",
                ),
                ResolutionAction(
                    action_id=2,
                    description="Check GSTR-2B of subsequent periods for late reflection",
                    priority="MEDIUM",
                    deadline_days=30,
                ),
            ]
        else:
            risk_cat = RiskCategory.AUDIT_TRIGGER
            desc = "Invoice appearing in GSTR-2B without corresponding GSTR-1 entry. Potential phantom invoice."
            actions = [
                ResolutionAction(
                    action_id=1,
                    description="Verify if invoice is genuine and supplier has filed GSTR-1",
                    priority="CRITICAL",
                    deadline_days=7,
                    regulatory_reference="Rule 36(4) CGST Rules",
                ),
                ResolutionAction(
                    action_id=2,
                    description="If phantom, reverse ITC and file DRC-03",
                    priority="CRITICAL",
                    deadline_days=15,
                    regulatory_reference="Section 74 CGST Act",
                ),
            ]

        return Mismatch(
            mismatch_id=f"MM-L1-{generate_uuid()[:8]}",
            mismatch_type=mm_type,
            severity=Severity(severity_from_amount(tax_amount)),
            financial_impact=FinancialImpact(
                itc_at_risk=round(tax_amount, 2),
                potential_interest_liability=round(tax_amount * 0.18 / 12, 2),
                penalty_exposure=round(tax_amount * 0.25, 2),
            ),
            risk_category=risk_cat,
            root_cause=RootCause(
                classification=desc,
                confidence=85.0,
                evidence_paths=[
                    f"Invoice {invoice.get('invoice_number')} — {direction}"
                ],
            ),
            supplier_gstin=invoice.get("supplier_gstin"),
            buyer_gstin=invoice.get("recipient_gstin"),
            invoice_number=invoice.get("invoice_number"),
            gstr1_value=float(invoice.get("taxable_value", 0)) if direction == "MISSING_IN_GSTR2B" else None,
            gstr2b_value=float(invoice.get("taxable_value", 0)) if direction == "MISSING_IN_GSTR1" else None,
            resolution_actions=actions,
        )

    def store_match_results(self, results: List[MatchResult]):
        """Persist match results as MATCHED_WITH relationships in Neo4j."""
        for r in results:
            if r.match_type in ("exact_match", "partial_match") and r.gstr2b_invoice:
                cypher = """
                MATCH (i1:Invoice {uid: $uid1})
                MATCH (i2:Invoice {uid: $uid2})
                MERGE (i1)-[rel:MATCHED_WITH]->(i2)
                SET rel.match_score = $score,
                    rel.mismatch_fields = $fields,
                    rel.match_type = $type
                """
                execute_query(cypher, {
                    "uid1": r.gstr1_invoice["uid"],
                    "uid2": r.gstr2b_invoice["uid"],
                    "score": r.match_score,
                    "fields": [d["field"] for d in r.field_diffs],
                    "type": r.match_type,
                })
