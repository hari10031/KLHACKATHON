"""
Level 2: ITC Chain Validation (2-4 hops)
Traverse: PurchaseRegister -> Invoice -> GSTR-1 -> GSTR-2B -> GSTR-3B ITC claim.
Validate each hop exists and values are consistent.
"""

from typing import List, Dict, Optional
from loguru import logger

from app.database import execute_query
from app.utils.helpers import values_match, generate_uuid, severity_from_amount, calculate_interest
from app.models.mismatch import (
    Mismatch, MismatchType, Severity, RiskCategory,
    FinancialImpact, RootCause, AffectedChain, ChainHop, ResolutionAction,
)


class Level2ITCChainValidator:
    """
    Validates the complete ITC claim chain for each invoice.
    
    Chain: PurchaseRegister → Invoice → GSTR-1 (supplier) → 
           GSTR-2B (buyer) → GSTR-3B (ITC claim)
    
    Each hop is validated for existence and value consistency.
    """

    def __init__(self, abs_tolerance: float = 1.0, pct_tolerance: float = 0.001):
        self.abs_tolerance = abs_tolerance
        self.pct_tolerance = pct_tolerance

    def validate_itc_chains(self, gstin: str, return_period: str) -> List[Mismatch]:
        """Validate all ITC chains for a buyer GSTIN in a return period."""
        logger.info(f"Level 2 ITC chain validation for GSTIN={gstin}, period={return_period}")

        chains = self._fetch_itc_chains(gstin, return_period)
        logger.info(f"Found {len(chains)} ITC chains to validate")

        mismatches = []
        for chain in chains:
            chain_result = self._validate_single_chain(chain)
            if chain_result:
                mismatches.append(chain_result)

        logger.info(f"Level 2 found {len(mismatches)} broken ITC chains")
        return mismatches

    def _fetch_itc_chains(self, gstin: str, return_period: str) -> List[dict]:
        """
        Fetch all potential ITC chains for a buyer GSTIN.
        Uses multi-hop Cypher query to traverse the full chain.
        """
        cypher = """
        // Start from GSTR-2B invoices received by this buyer
        MATCH (buyer:GSTIN {gstin_number: $gstin})-[:RECEIVED_INVOICE]->(inv_2b:Invoice {source: 'GSTR2B'})
        
        // Hop 1: Check if purchase register entry exists
        OPTIONAL MATCH (pr:PurchaseRegisterEntry)-[:CORRESPONDS_TO]->(inv_2b)
        
        // Hop 2: Find matching GSTR-1 invoice from supplier
        OPTIONAL MATCH (supplier:GSTIN {gstin_number: inv_2b.supplier_gstin})-[:ISSUED_INVOICE]->(inv_1:Invoice {source: 'GSTR1'})
        WHERE inv_1.invoice_number = inv_2b.invoice_number
        
        // Hop 3: Check GSTR-1 reported in a return
        OPTIONAL MATCH (inv_1)-[:REPORTED_IN]->(ret_1:Return {return_type: 'GSTR1'})
        
        // Hop 4: Check GSTR-2B reported in a return
        OPTIONAL MATCH (inv_2b)-[:REPORTED_IN]->(ret_2b:Return {return_type: 'GSTR2B'})
        
        // Hop 5: Check ITC claimed in GSTR-3B
        OPTIONAL MATCH (inv_2b)-[itc:ITC_CLAIMED_VIA]->(ret_3b:Return {return_type: 'GSTR3B'})
        
        // Hop 6: Check supplier GSTIN status
        OPTIONAL MATCH (supplier_node:GSTIN {gstin_number: inv_2b.supplier_gstin})
        
        // Hop 7: Check IRN
        OPTIONAL MATCH (inv_1)-[:HAS_IRN]->(irn:IRN)
        
        RETURN 
            inv_2b {.*, uid: inv_2b.uid} AS gstr2b_invoice,
            inv_1 {.*, uid: inv_1.uid} AS gstr1_invoice,
            pr {.*} AS purchase_entry,
            ret_1 {.*} AS gstr1_return,
            ret_2b {.*} AS gstr2b_return,
            ret_3b {.*} AS gstr3b_return,
            itc {.*} AS itc_claim,
            supplier_node.status AS supplier_status,
            irn {.*} AS irn_data
        """
        month = return_period[:2]
        year = return_period[2:]

        results = execute_query(cypher, {"gstin": gstin})
        return results

    def _validate_single_chain(self, chain: dict) -> Optional[Mismatch]:
        """Validate a single ITC chain and return mismatch if broken."""
        inv_2b = chain.get("gstr2b_invoice") or {}
        inv_1 = chain.get("gstr1_invoice") or {}
        pr = chain.get("purchase_entry") or {}
        gstr1_return = chain.get("gstr1_return")
        gstr2b_return = chain.get("gstr2b_return")
        gstr3b_return = chain.get("gstr3b_return")
        itc_claim = chain.get("itc_claim") or {}
        supplier_status = chain.get("supplier_status")
        irn_data = chain.get("irn_data") or {}

        hops = []
        break_point = None
        issues = []

        # Hop 1: Purchase Register → Invoice
        hop1_status = "valid" if pr else "broken"
        hops.append(ChainHop(
            hop_number=1,
            source_type="PurchaseRegisterEntry",
            source_id=pr.get("entry_id", "N/A"),
            target_type="Invoice (GSTR-2B)",
            target_id=inv_2b.get("uid", ""),
            relationship="CORRESPONDS_TO",
            status=hop1_status,
            details="Purchase register entry found" if pr else "No purchase register entry",
        ))
        if hop1_status == "broken" and break_point is None:
            break_point = 1
            issues.append("Missing purchase register entry")

        # Hop 2: Invoice (GSTR-2B) → Invoice (GSTR-1) — supplier filed?
        hop2_status = "valid"
        if not inv_1:
            hop2_status = "broken"
            if break_point is None:
                break_point = 2
            issues.append("No matching GSTR-1 invoice found from supplier")
        elif not values_match(
            float(inv_2b.get("taxable_value", 0)),
            float(inv_1.get("taxable_value", 0)),
            self.abs_tolerance, self.pct_tolerance
        ):
            hop2_status = "warning"
            issues.append(
                f"Value mismatch: GSTR-2B={inv_2b.get('taxable_value')}, "
                f"GSTR-1={inv_1.get('taxable_value')}"
            )

        hops.append(ChainHop(
            hop_number=2,
            source_type="Invoice (GSTR-2B)",
            source_id=inv_2b.get("uid", ""),
            target_type="Invoice (GSTR-1)",
            target_id=inv_1.get("uid", "N/A"),
            relationship="MATCHED_WITH",
            status=hop2_status,
            details=issues[-1] if issues else "GSTR-1 invoice matched",
        ))

        # Hop 3: GSTR-1 → Return filing
        hop3_status = "valid" if gstr1_return else "broken"
        hops.append(ChainHop(
            hop_number=3,
            source_type="Invoice (GSTR-1)",
            source_id=inv_1.get("uid", "N/A"),
            target_type="Return (GSTR-1)",
            target_id="",
            relationship="REPORTED_IN",
            status=hop3_status,
            details="GSTR-1 return filed" if gstr1_return else "GSTR-1 not filed by supplier",
        ))
        if hop3_status == "broken" and break_point is None:
            break_point = 3
            issues.append("Supplier has not filed GSTR-1 for this period")

        # Hop 4: GSTR-3B ITC Claim
        hop4_status = "valid"
        if not gstr3b_return:
            hop4_status = "broken"
            if break_point is None:
                break_point = 4
            issues.append("ITC not claimed in GSTR-3B")
        elif itc_claim:
            claimed = float(itc_claim.get("claimed_amount", 0))
            eligible = float(itc_claim.get("eligible_amount", 0))
            if claimed > eligible * 1.05:  # Allow 5% tolerance
                hop4_status = "warning"
                issues.append(f"ITC overclaim: claimed={claimed}, eligible={eligible}")

        hops.append(ChainHop(
            hop_number=4,
            source_type="Invoice (GSTR-2B)",
            source_id=inv_2b.get("uid", ""),
            target_type="Return (GSTR-3B)",
            target_id="",
            relationship="ITC_CLAIMED_VIA",
            status=hop4_status,
            details=issues[-1] if issues and len(issues) > len(hops) - 1 else "ITC claimed in GSTR-3B",
        ))

        # Check supplier status
        if supplier_status in ("cancelled", "suspended"):
            issues.append(f"Supplier GSTIN status is {supplier_status}")
            # Override severity
            break_point = break_point or 2

        # Check IRN validity
        if irn_data and irn_data.get("irn_status") in ("cancelled", "invalid"):
            issues.append(f"IRN status is {irn_data.get('irn_status')}")

        # If no issues, chain is valid
        if not issues:
            return None

        # Determine mismatch type and severity
        tax_amount = float(inv_2b.get("igst", 0)) + float(inv_2b.get("cgst", 0)) + float(inv_2b.get("sgst", 0))

        # Choose primary mismatch type
        if supplier_status in ("cancelled", "suspended"):
            mm_type = MismatchType.PHANTOM_INVOICE
            risk_cat = RiskCategory.DEMAND_NOTICE
        elif "ITC overclaim" in str(issues):
            mm_type = MismatchType.ITC_OVERCLAIM
            risk_cat = RiskCategory.ITC_REVERSAL
        elif "No matching GSTR-1" in str(issues):
            mm_type = MismatchType.MISSING_IN_GSTR1
            risk_cat = RiskCategory.ITC_REVERSAL
        elif "GSTR-1 not filed" in str(issues):
            mm_type = MismatchType.MISSING_IN_GSTR1
            risk_cat = RiskCategory.ITC_REVERSAL
        elif irn_data and irn_data.get("irn_status") in ("cancelled", "invalid"):
            mm_type = MismatchType.IRN_INVALID
            risk_cat = RiskCategory.AUDIT_TRIGGER
        else:
            mm_type = MismatchType.VALUE_MISMATCH
            risk_cat = RiskCategory.ITC_REVERSAL

        chain_completeness = sum(1 for h in hops if h.status == "valid") / len(hops) * 100

        return Mismatch(
            mismatch_id=f"MM-L2-{generate_uuid()[:8]}",
            mismatch_type=mm_type,
            severity=Severity(severity_from_amount(tax_amount)),
            financial_impact=FinancialImpact(
                itc_at_risk=round(tax_amount, 2),
                potential_interest_liability=round(calculate_interest(tax_amount), 2),
                penalty_exposure=round(tax_amount * 0.1, 2),
            ),
            risk_category=risk_cat,
            root_cause=RootCause(
                classification="; ".join(issues),
                confidence=80.0,
                evidence_paths=[
                    f"Hop {h.hop_number}: {h.source_type} → {h.target_type} [{h.status}]"
                    for h in hops
                ],
            ),
            affected_chain=AffectedChain(
                hops=hops,
                break_point=break_point,
                chain_completeness=round(chain_completeness, 1),
            ),
            supplier_gstin=inv_2b.get("supplier_gstin"),
            buyer_gstin=inv_2b.get("recipient_gstin"),
            invoice_number=inv_2b.get("invoice_number"),
            resolution_actions=[
                ResolutionAction(
                    action_id=1,
                    description="Verify ITC chain completeness with supplier",
                    priority="HIGH",
                    deadline_days=15,
                    regulatory_reference="Section 16(2) CGST Act",
                ),
                ResolutionAction(
                    action_id=2,
                    description=f"Chain breaks at hop {break_point}: {issues[0] if issues else 'unknown'}",
                    priority="CRITICAL",
                    deadline_days=7,
                ),
            ],
        )
