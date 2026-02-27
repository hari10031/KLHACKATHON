"""
Main reconciliation orchestrator — runs all 4 levels and aggregates results.
"""

from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

from app.database import execute_query
from app.utils.helpers import generate_uuid
from app.models.mismatch import Mismatch, ReconciliationSummary, Severity
from app.engine.level1_matching import Level1Matcher
from app.engine.level2_itc_chain import Level2ITCChainValidator
from app.engine.level3_circular import Level3CircularTradeDetector
from app.engine.level4_risk import Level4RiskPropagation
from app.engine.risk_scorer import batch_compute_risk


class ReconciliationEngine:
    """
    Orchestrates the 4-level GST reconciliation pipeline.
    
    Level 1: Direct Invoice Matching (1-hop)
    Level 2: ITC Chain Validation (2-4 hops)
    Level 3: Circular Trade Detection (variable hops)
    Level 4: Vendor Network Risk Propagation (graph-wide)
    """

    def __init__(self):
        self.level1 = Level1Matcher()
        self.level2 = Level2ITCChainValidator()
        self.level3 = Level3CircularTradeDetector()
        self.level4 = Level4RiskPropagation()

    def run_full_reconciliation(
        self, gstin: str, return_period: str
    ) -> ReconciliationSummary:
        """
        Run the complete 4-level reconciliation for a GSTIN and return period.
        """
        run_id = f"REC-{generate_uuid()[:8]}"
        logger.info(f"Starting reconciliation run {run_id} for GSTIN={gstin}, period={return_period}")
        start_time = datetime.utcnow()

        all_mismatches: List[Mismatch] = []

        # ── Level 1: Direct Invoice Matching ──
        logger.info("Running Level 1: Direct Invoice Matching...")
        l1_results = self.level1.match_invoices(gstin, return_period)
        self.level1.store_match_results(l1_results)

        l1_mismatches = [r.mismatch for r in l1_results if r.mismatch]
        all_mismatches.extend(l1_mismatches)

        matched_count = sum(1 for r in l1_results if r.match_type == "exact_match")
        partial_count = sum(1 for r in l1_results if r.match_type == "partial_match")
        unmatched_count = sum(1 for r in l1_results if r.match_type == "unmatched")

        # ── Level 2: ITC Chain Validation ──
        logger.info("Running Level 2: ITC Chain Validation...")
        l2_mismatches = self.level2.validate_itc_chains(gstin, return_period)
        all_mismatches.extend(l2_mismatches)

        # ── Level 3: Circular Trade Detection ──
        logger.info("Running Level 3: Circular Trade Detection...")
        l3_mismatches = self.level3.detect_circular_trades()
        all_mismatches.extend(l3_mismatches)

        # ── Level 4: Risk Propagation ──
        logger.info("Running Level 4: Vendor Network Risk Propagation...")
        risk_result = self.level4.propagate_risk()

        # ── Compute composite risk scores ──
        all_mismatches = batch_compute_risk(all_mismatches)

        # ── Build summary ──
        mismatches_by_type = {}
        mismatches_by_severity = {}
        total_itc_at_risk = 0.0

        for mm in all_mismatches:
            mt = mm.mismatch_type.value
            mismatches_by_type[mt] = mismatches_by_type.get(mt, 0) + 1
            sv = mm.severity.value
            mismatches_by_severity[sv] = mismatches_by_severity.get(sv, 0) + 1
            total_itc_at_risk += mm.financial_impact.itc_at_risk

        # Get total ITC claimed from GSTR-3B
        itc_claimed = self._get_total_itc_claimed(gstin, return_period)
        itc_verified = itc_claimed - total_itc_at_risk

        summary = ReconciliationSummary(
            run_id=run_id,
            gstin=gstin,
            return_period=return_period,
            run_timestamp=start_time,
            total_invoices=len(l1_results),
            matched=matched_count,
            partial_matched=partial_count,
            unmatched=unmatched_count,
            mismatches_by_type=mismatches_by_type,
            mismatches_by_severity=mismatches_by_severity,
            total_itc_claimed=round(itc_claimed, 2),
            itc_at_risk=round(total_itc_at_risk, 2),
            itc_verified=round(max(0, itc_verified), 2),
            net_exposure=round(total_itc_at_risk, 2),
            mismatches=all_mismatches,
        )

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Reconciliation {run_id} complete in {elapsed:.1f}s: "
            f"{matched_count} matched, {len(all_mismatches)} mismatches, "
            f"₹{total_itc_at_risk:,.2f} ITC at risk"
        )

        return summary

    def run_level1_only(self, gstin: str, return_period: str) -> ReconciliationSummary:
        """Run only Level 1 matching."""
        run_id = f"REC-L1-{generate_uuid()[:8]}"
        results = self.level1.match_invoices(gstin, return_period)
        self.level1.store_match_results(results)
        mismatches = [r.mismatch for r in results if r.mismatch]
        mismatches = batch_compute_risk(mismatches)

        return ReconciliationSummary(
            run_id=run_id,
            gstin=gstin,
            return_period=return_period,
            run_timestamp=datetime.utcnow(),
            total_invoices=len(results),
            matched=sum(1 for r in results if r.match_type == "exact_match"),
            partial_matched=sum(1 for r in results if r.match_type == "partial_match"),
            unmatched=sum(1 for r in results if r.match_type == "unmatched"),
            mismatches=mismatches,
        )

    def get_all_gstins(self) -> List[str]:
        """Get all active GSTINs in the system."""
        result = execute_query("MATCH (g:GSTIN {status: 'active'}) RETURN g.gstin_number AS gstin")
        return [r["gstin"] for r in result]

    def get_return_periods(self) -> List[str]:
        """Get all available return periods."""
        result = execute_query("""
            MATCH (r:Return)
            RETURN DISTINCT r.return_period AS period
            ORDER BY period
        """)
        return [r["period"] for r in result]

    def _get_total_itc_claimed(self, gstin: str, return_period: str) -> float:
        """Get total ITC claimed in GSTR-3B for a period."""
        result = execute_query("""
            MATCH (g:GSTIN {gstin_number: $gstin})-[:FILED_RETURN]->(r:Return {return_type: 'GSTR3B', return_period: $period})
            OPTIONAL MATCH (inv:Invoice)-[itc:ITC_CLAIMED_VIA]->(r)
            RETURN COALESCE(sum(itc.claimed_amount), 0) AS total_claimed
        """, {"gstin": gstin, "period": return_period})
        return float(result[0]["total_claimed"]) if result else 0.0
