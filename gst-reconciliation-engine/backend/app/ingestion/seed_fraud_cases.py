"""
Seed realistic fraud cases as Mismatch nodes in Neo4j + update GSTIN risk profiles.

Creates 18 detailed fraud cases across all mismatch types with:
  - Natural-language narratives explaining WHY each case is fraud
  - Evidence paths from the knowledge graph
  - Regulatory references (CGST Act / Rules)
  - Financial impact breakdown
  - Resolution actions
  - Risk scores on GSTIN nodes (pagerank, centrality, community)
"""

import random
import math
from datetime import datetime, timedelta
from loguru import logger
from app.database import execute_query, execute_write


def seed_fraud_cases():
    """Main entry point — seeds fraud cases and risk profiles into Neo4j."""
    logger.info("=== Seeding Fraud Cases & Risk Profiles ===")

    # Step 1: Fetch existing GSTINs & invoices
    gstins = _fetch_gstins()
    if len(gstins) < 10:
        raise RuntimeError(f"Need at least 10 GSTINs, found {len(gstins)}")

    invoices = _fetch_invoices()
    logger.info(f"Found {len(gstins)} GSTINs, {len(invoices)} invoices")

    # Step 2: Clean existing Mismatch nodes
    execute_write("MATCH (m:Mismatch) DETACH DELETE m")
    logger.info("Cleared existing Mismatch nodes")

    # Step 3: Assign risk profiles to ALL GSTINs
    _seed_risk_profiles(gstins)

    # Step 4: Create fraud cases
    fraud_cases = _build_fraud_cases(gstins, invoices)
    _persist_fraud_cases(fraud_cases)

    # Step 5: Link Mismatch nodes to Invoices via INVOLVES relationship
    _link_mismatches_to_invoices()

    logger.info(f"=== Seeded {len(fraud_cases)} fraud cases successfully ===")
    return {
        "status": "seeded",
        "fraud_cases": len(fraud_cases),
        "gstins_with_risk": len(gstins),
    }


# ─────────────────────── Data Fetchers ───────────────────────

def _fetch_gstins():
    """Fetch all GSTINs with their trade names and states."""
    rows = execute_query("""
        MATCH (g:GSTIN)
        OPTIONAL MATCH (g)<-[:HAS_GSTIN]-(t:Taxpayer)
        RETURN g.gstin_number AS gstin,
               g.status AS status,
               g.state_code AS state_code,
               COALESCE(g.trade_name, t.legal_name, 'Unknown Entity') AS name
        ORDER BY gstin
    """)
    return [dict(r) for r in rows]


def _fetch_invoices():
    """Fetch a sample of invoices for linking to fraud cases."""
    rows = execute_query("""
        MATCH (inv:Invoice)
        RETURN inv.uid AS uid,
               inv.invoice_number AS invoice_number,
               inv.invoice_date AS invoice_date,
               inv.taxable_value AS taxable_value,
               inv.total_value AS total_value,
               inv.cgst AS cgst, inv.sgst AS sgst, inv.igst AS igst,
               inv.tax_rate AS tax_rate,
               inv.supplier_gstin AS supplier_gstin,
               inv.recipient_gstin AS recipient_gstin,
               inv.source AS source
        ORDER BY inv.taxable_value DESC
        LIMIT 200
    """)
    return [dict(r) for r in rows]


# ─────────────────────── Risk Profiles ───────────────────────

def _seed_risk_profiles(gstins):
    """Assign realistic risk scores, pagerank, centrality to ALL GSTINs."""
    random.seed(42)

    # Pick ~25% as high-risk
    high_risk_count = max(4, len(gstins) // 4)
    high_risk_indices = set(random.sample(range(len(gstins)), high_risk_count))

    for i, g in enumerate(gstins):
        gstin = g["gstin"]
        is_high_risk = i in high_risk_indices

        if is_high_risk:
            risk_score = round(random.uniform(0.55, 0.92), 4)
            pagerank = round(random.uniform(0.015, 0.045), 6)
            degree = round(random.uniform(0.15, 0.45), 4)
            betweenness = round(random.uniform(0.05, 0.25), 4)
            community = random.choice([0, 1, 2])
        else:
            risk_score = round(random.uniform(0.05, 0.40), 4)
            pagerank = round(random.uniform(0.005, 0.020), 6)
            degree = round(random.uniform(0.03, 0.15), 4)
            betweenness = round(random.uniform(0.001, 0.05), 4)
            community = random.choice([3, 4, 5, 6])

        if risk_score > 0.7:
            risk_label = "critical"
        elif risk_score > 0.5:
            risk_label = "high"
        elif risk_score > 0.3:
            risk_label = "medium"
        else:
            risk_label = "low"

        execute_write("""
            MATCH (g:GSTIN {gstin_number: $gstin})
            SET g.risk_score = $risk_score,
                g.risk_label = $risk_label,
                g.pagerank = $pagerank,
                g.degree_centrality = $degree,
                g.betweenness_centrality = $betweenness,
                g.community_id = $community,
                g.clustering_coefficient = $clustering
        """, {
            "gstin": gstin,
            "risk_score": risk_score,
            "risk_label": risk_label,
            "pagerank": pagerank,
            "degree": degree,
            "betweenness": betweenness,
            "community": community,
            "clustering": round(random.uniform(0.1, 0.6), 4),
        })

    logger.info(f"Updated risk profiles for {len(gstins)} GSTINs ({high_risk_count} high-risk)")


# ─────────────────────── Fraud Case Builder ───────────────────────

def _build_fraud_cases(gstins, invoices):
    """Build 18 detailed, realistic fraud cases."""
    random.seed(123)
    cases = []

    active = [g for g in gstins if g.get("status") == "active"]
    if len(active) < 15:
        active = gstins[:15]

    # Group invoices by supplier
    inv_by_supplier = {}
    for inv in invoices:
        s = inv.get("supplier_gstin", "")
        if s not in inv_by_supplier:
            inv_by_supplier[s] = []
        inv_by_supplier[s].append(inv)

    periods = ["042024", "052024", "062024", "072024", "082024", "092024",
               "102024", "112024", "122024", "012025", "022025", "032025"]

    # ═══════════════════════════════════════════════════════════════
    # CASE 1-3: CIRCULAR TRADE (high-value fraud rings)
    # ═══════════════════════════════════════════════════════════════

    # Case 1: 3-entity circular ring — classic carousel fraud
    ring3 = active[:3]
    cases.append(_circular_trade_case(
        case_num=1,
        participants=ring3,
        period="112024",
        values=[9382451.0, 7254832.0, 5683210.0],
        inflation=1.31,
        narrative=(
            "CRITICAL ALERT: Classic carousel fraud detected involving a 3-entity circular "
            f"trading ring. {ring3[0]['name']} issued invoices worth ₹93.82L to "
            f"{ring3[1]['name']}, who then billed ₹72.55L to {ring3[2]['name']}, "
            f"who completed the loop by invoicing ₹56.83L back to {ring3[0]['name']}. "
            "The value inflation ratio of 1.31x across the cycle indicates artificial "
            "value padding to maximise ITC claims. None of the transactions have "
            "corresponding bank payments or e-Way Bills, strongly suggesting these are "
            "paper transactions designed to generate fraudulent ITC credits. "
            "Total ITC at risk: ₹40.18L. This pattern matches known GST carousel fraud "
            "typology documented by the DGGI (Directorate General of GST Intelligence)."
        ),
    ))

    # Case 2: 4-entity ring with cancelled entity
    ring4 = active[3:7]
    cases.append(_circular_trade_case(
        case_num=2,
        participants=ring4,
        period="012025",
        values=[12450000.0, 10875000.0, 8932000.0, 6250000.0],
        inflation=1.44,
        narrative=(
            f"HIGH-RISK circular trade identified across 4 entities. Starting from "
            f"{ring4[0]['name']} → {ring4[1]['name']} → {ring4[2]['name']} → "
            f"{ring4[3]['name']} → back to {ring4[0]['name']}. The total circulated "
            "value exceeds ₹3.85 Cr with a progressive value inflation of 1.44x per hop. "
            f"Notably, {ring4[2]['name']} has a compliance rating below 30 and "
            "has 3 late-filed returns in the last 6 months. The pattern shows invoices "
            "raised within 48 hours of each other — an impossibility for genuine "
            "manufacturing/trading operations. The goods described (Steel Structures, "
            "HSN 7308) show no corresponding raw material purchases by any participant."
        ),
    ))

    # Case 3: 5-entity ring — complex web
    ring5 = active[7:12]
    cases.append(_circular_trade_case(
        case_num=3,
        participants=ring5,
        period="022025",
        values=[15670000.0, 13205000.0, 11480000.0, 9835000.0, 7120000.0],
        inflation=1.22,
        narrative=(
            f"Complex 5-entity circular trading network uncovered. The chain spans "
            f"across 3 different states: {ring5[0]['name']} (State {ring5[0].get('state_code','XX')}) "
            f"→ {ring5[1]['name']} → {ring5[2]['name']} → {ring5[3]['name']} → "
            f"{ring5[4]['name']} → back to {ring5[0]['name']}. Total value: ₹5.73 Cr. "
            "Cross-verification with bank statements reveals no actual fund transfers "
            "between 3 of the 5 entities. IGST has been exploited for inter-state "
            "transactions to claim refunds. Two entities share the same registered "
            "address, indicating possible shell company involvement. "
            "ML model confidence: 94.2%."
        ),
    ))

    # ═══════════════════════════════════════════════════════════════
    # CASE 4-5: PHANTOM INVOICE (no real supply)
    # ═══════════════════════════════════════════════════════════════

    # Case 4: Invoice from cancelled GSTIN
    phantom1_seller = active[12]
    phantom1_buyer = active[0]
    inv4 = _pick_invoice(inv_by_supplier, phantom1_seller["gstin"], invoices)
    cases.append({
        "mismatch_id": "FRAUD-004-PHANTOM",
        "mismatch_type": "PHANTOM_INVOICE",
        "severity": "CRITICAL",
        "status": "OPEN",
        "detected_at": "2026-02-27T09:15:22",
        "gstin": phantom1_buyer["gstin"],
        "return_period": "102024",
        "composite_risk_score": 0.91,
        "itc_at_risk": 843250.0,
        "description": f"Phantom invoice detected — {phantom1_seller['name']} issued invoice with no supporting documents",
        "narrative": (
            f"CRITICAL: Invoice {inv4.get('invoice_number','INV/2425/000187')} worth ₹46.85L "
            f"from {phantom1_seller['name']} ({phantom1_seller['gstin']}) has been identified "
            "as a phantom invoice. The knowledge graph traversal reveals: (1) No IRN "
            "(e-Invoice Reference Number) was generated — mandatory for B2B transactions "
            "above ₹5 Cr turnover since Oct 2020 and ₹5L since Aug 2023. "
            "(2) No e-Way Bill exists despite the invoice value exceeding ₹50,000 threshold. "
            "(3) No bank transaction was found matching this invoice amount (±5%). "
            "(4) The supplier's GSTR-1 filing for Oct 2024 was filed 47 days late, "
            "raising questions about the genuineness of the filing. "
            "The ML model assigns a 91% fraud probability based on the absence of all "
            "3 corroborating documents (IRN + EWB + Bank Txn)."
        ),
        "seller_gstin": phantom1_seller["gstin"],
        "buyer_gstin": phantom1_buyer["gstin"],
        "invoice_number": inv4.get("invoice_number", "INV/2425/000187"),
        "gstr1_value": 4685000.0,
        "gstr2b_value": 4685000.0,
        "classification": "Phantom Invoice — No IRN, No E-Way Bill, No Bank Payment",
        "confidence": 91.0,
        "evidence_paths": [
            f"GSTIN({phantom1_seller['gstin']}) -[ISSUED_INVOICE]-> Invoice({inv4.get('invoice_number','INV/2425/000187')}) — NO HAS_IRN edge found",
            f"Invoice({inv4.get('invoice_number','INV/2425/000187')}) — NO COVERED_BY_EWBILL edge found",
            f"Invoice({inv4.get('invoice_number','INV/2425/000187')}) — NO PAID_VIA edge found",
            f"GSTIN({phantom1_seller['gstin']}) filed GSTR-1 47 days late for period 102024",
        ],
        "resolution_actions": [
            "Immediately reverse ITC of ₹8,43,250 claimed against this invoice",
            "Issue SCN (Show Cause Notice) under Section 74 CGST Act for extended period",
            "Refer to DGGI for investigation of the supplier entity",
            "Verify physical existence of supplier at registered address",
        ],
        "regulatory_references": [
            "Section 16(2)(aa) CGST Act — ITC only if invoice reflected in GSTR-2B",
            "Section 16(2)(c) CGST Act — Tax must have been actually paid to Government",
            "Rule 36(4) CGST Rules — ITC restricted to invoices furnished by supplier",
            "Section 132(1)(b) CGST Act — Issuing invoice without supply of goods (cognizable offence)",
        ],
        "risk_category": "DEMAND_NOTICE",
        "seller_value": 4685000.0,
        "buyer_value": 4685000.0,
    })

    # Case 5: Invoice from non-existent supplier
    phantom2_buyer = active[2]
    cases.append({
        "mismatch_id": "FRAUD-005-PHANTOM",
        "mismatch_type": "PHANTOM_INVOICE",
        "severity": "CRITICAL",
        "status": "ESCALATED",
        "detected_at": "2026-02-27T09:18:05",
        "gstin": phantom2_buyer["gstin"],
        "return_period": "122024",
        "composite_risk_score": 0.88,
        "itc_at_risk": 1256800.0,
        "description": "Invoices claimed from a supplier with suspended GST registration",
        "narrative": (
            f"Two invoices totalling ₹69.82L claimed by {phantom2_buyer['name']} "
            "from a supplier whose GST registration was suspended effective 15-Sep-2024 "
            "(suo moto cancellation proceedings initiated). Despite the suspension, "
            "invoices dated 08-Dec-2024 and 19-Dec-2024 appear in the claimant's GSTR-2B. "
            "The supplier's GSTR-1 for Dec 2024 shows 47 outward invoices filed in a "
            "bulk upload on 31-Dec-2024 — 23 of which were raised AFTER suspension date. "
            "No e-Way Bills were generated for any of these invoices. "
            "Purchase register analysis shows these invoices were booked under "
            "'Capital Goods' category to claim 100% ITC immediately instead of "
            "spreading over 5 years. This is a classic bill trading pattern."
        ),
        "seller_gstin": active[13]["gstin"] if len(active) > 13 else active[5]["gstin"],
        "buyer_gstin": phantom2_buyer["gstin"],
        "invoice_number": "B2B2425000412",
        "gstr1_value": 6982000.0,
        "gstr2b_value": 6982000.0,
        "classification": "Phantom Invoice — Supplier registration suspended",
        "confidence": 88.0,
        "evidence_paths": [
            "Supplier GSTIN status = 'suspended' since 15-Sep-2024",
            "Invoice date (08-Dec-2024) is AFTER suspension date",
            "47 invoices bulk-uploaded on 31-Dec-2024 — suspicious filing pattern",
            "No COVERED_BY_EWBILL edges for any Dec 2024 invoices from this supplier",
        ],
        "resolution_actions": [
            "Reverse ITC of ₹12,56,800 immediately under Rule 42/43",
            "File DRC-03 for voluntary payment of tax + interest",
            "Lodge complaint with jurisdictional officer under Section 122",
        ],
        "regulatory_references": [
            "Section 16(2)(b) CGST Act — Goods/services must have been received",
            "Section 29 CGST Act — Cancellation of registration",
            "Section 122(1)(ii) CGST Act — Penalty for issuing invoice without supply",
        ],
        "risk_category": "DEMAND_NOTICE",
    })

    # ═══════════════════════════════════════════════════════════════
    # CASE 6-8: VALUE MISMATCH (amount discrepancies)
    # ═══════════════════════════════════════════════════════════════

    vm_seller = active[1]
    vm_buyer = active[3]
    inv6 = _pick_invoice(inv_by_supplier, vm_seller["gstin"], invoices)
    cases.append({
        "mismatch_id": "FRAUD-006-VALMIS",
        "mismatch_type": "VALUE_MISMATCH",
        "severity": "HIGH",
        "status": "UNDER_REVIEW",
        "detected_at": "2026-02-27T10:02:33",
        "gstin": vm_buyer["gstin"],
        "return_period": "082024",
        "composite_risk_score": 0.72,
        "itc_at_risk": 387450.0,
        "description": f"Taxable value inflated by ₹21.53L in buyer's GSTR-2B vs supplier's GSTR-1",
        "narrative": (
            f"Significant value mismatch detected on invoice {inv6.get('invoice_number','SI2425000142')}. "
            f"Supplier {vm_seller['name']} reported taxable value of ₹18,92,300 in GSTR-1, "
            f"but buyer {vm_buyer['name']} has recorded ₹40,45,750 in GSTR-2B — a difference "
            "of ₹21,53,450 (113.8% inflation). The CGST/SGST claimed by the buyer "
            "(₹3,64,117.50 each at 18%) is based on the inflated amount, resulting in "
            "excess ITC of ₹3,87,450. Cross-referencing with the bank transaction shows "
            "payment of ₹22,32,914 — which aligns with the supplier's value, not the buyer's. "
            "This is a textbook ITC inflation scheme where the buyer modifies the invoice "
            "value in their books before filing."
        ),
        "seller_gstin": vm_seller["gstin"],
        "buyer_gstin": vm_buyer["gstin"],
        "invoice_number": inv6.get("invoice_number", "SI2425000142"),
        "gstr1_value": 1892300.0,
        "gstr2b_value": 4045750.0,
        "classification": "Value Mismatch — Buyer inflated taxable value by 113.8%",
        "confidence": 87.5,
        "evidence_paths": [
            f"GSTR-1 Invoice {inv6.get('invoice_number','SI2425000142')}: taxable_value = ₹18,92,300",
            "GSTR-2B same invoice: taxable_value = ₹40,45,750 (Δ = ₹21,53,450)",
            "Bank Txn REF-8847291: amount = ₹22,32,914 → matches GSTR-1 value (not GSTR-2B)",
            "Tax difference: CGST ₹1,93,725 + SGST ₹1,93,725 = ₹3,87,450 excess ITC",
        ],
        "resolution_actions": [
            "Issue demand notice for ₹3,87,450 excess ITC + 18% interest",
            "Cross-verify with supplier's books under Section 65 (Audit)",
            "Check if buyer has made similar inflations in other periods",
        ],
        "regulatory_references": [
            "Section 16(2)(aa) CGST Act — ITC based on details in GSTR-2B",
            "Section 42 CGST Act — Matching, reversal and reclaim of ITC",
            "Section 73/74 CGST Act — Determination of tax not paid or short paid",
        ],
        "risk_category": "ITC_REVERSAL",
        "seller_value": 1892300.0,
        "buyer_value": 4045750.0,
    })

    # Case 7: Seller under-reported
    vm2_seller = active[5]
    vm2_buyer = active[8]
    cases.append({
        "mismatch_id": "FRAUD-007-VALMIS",
        "mismatch_type": "VALUE_MISMATCH",
        "severity": "HIGH",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:05:17",
        "gstin": vm2_seller["gstin"],
        "return_period": "092024",
        "composite_risk_score": 0.65,
        "itc_at_risk": 215680.0,
        "description": "Supplier under-reported taxable value by ₹11.98L to reduce output tax liability",
        "narrative": (
            f"Reverse value mismatch: {vm2_seller['name']} reported only ₹14,23,500 "
            f"in GSTR-1 for an invoice, while {vm2_buyer['name']}'s purchase register "
            "and GSTR-2B both show ₹26,21,800 — a shortfall of ₹11,98,300. "
            "The supplier appears to have intentionally reduced their output tax "
            "liability by ₹2,15,694 (IGST @ 18%). The e-Way Bill generated for this "
            "consignment shows a value of ₹26,21,800, corroborating the buyer's "
            "figures. The supplier has shown a pattern of under-reporting in 4 out of "
            "the last 6 months, with cumulative under-reporting of ₹47.3L."
        ),
        "seller_gstin": vm2_seller["gstin"],
        "buyer_gstin": vm2_buyer["gstin"],
        "invoice_number": "INV/2425/000298",
        "gstr1_value": 1423500.0,
        "gstr2b_value": 2621800.0,
        "classification": "Value Mismatch — Supplier under-reported by 45.7%",
        "confidence": 82.0,
        "evidence_paths": [
            "GSTR-1 value: ₹14,23,500 vs GSTR-2B value: ₹26,21,800",
            "E-Way Bill EWB-2024-09-4471: total_value = ₹26,21,800 → matches buyer",
            "Purchase Register Entry PR-SEP-0298: booked at ₹26,21,800",
            "Pattern: Under-reporting found in 4 of last 6 months (cumulative ₹47.3L)",
        ],
        "resolution_actions": [
            "Issue notice under Section 73 for short payment of output tax",
            "Direct supplier to file GSTR-1 amendment for correct values",
            "Initiate special audit under Section 66 for extended period review",
        ],
        "regulatory_references": [
            "Section 37 CGST Act — Furnishing details of outward supplies (GSTR-1)",
            "Section 73 CGST Act — Determination of tax not paid (non-fraud cases)",
            "Section 66 CGST Act — Special audit by Chartered Accountant",
        ],
        "risk_category": "AUDIT_TRIGGER",
        "seller_value": 1423500.0,
        "buyer_value": 2621800.0,
    })

    # Case 8: Inter-state vs intra-state confusion
    vm3_seller = active[9]
    vm3_buyer = active[10]
    cases.append({
        "mismatch_id": "FRAUD-008-VALMIS",
        "mismatch_type": "VALUE_MISMATCH",
        "severity": "MEDIUM",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:08:44",
        "gstin": vm3_buyer["gstin"],
        "return_period": "072024",
        "composite_risk_score": 0.48,
        "itc_at_risk": 134500.0,
        "description": "IGST charged on intra-state supply — should be CGST + SGST",
        "narrative": (
            f"Tax type mismatch: {vm3_seller['name']} charged IGST of ₹2,69,000 on "
            f"a supply to {vm3_buyer['name']}, but both entities are registered in the "
            f"same state (State Code: {vm3_seller.get('state_code','XX')}). As per Section 7(1) of the "
            "IGST Act, this should be an intra-state supply attracting CGST + SGST. "
            "The place of supply determination appears incorrect. While the monetary "
            "impact on the buyer's ITC is neutral (same total tax), the supplier has "
            "incorrectly deposited IGST instead of CGST+SGST, leading to a revenue "
            "loss for the State Government. This requires correction via amendment."
        ),
        "seller_gstin": vm3_seller["gstin"],
        "buyer_gstin": vm3_buyer["gstin"],
        "invoice_number": "INV/2425/000203",
        "gstr1_value": 1494444.0,
        "gstr2b_value": 1494444.0,
        "classification": "Tax Type Error — IGST on intra-state supply",
        "confidence": 95.0,
        "evidence_paths": [
            f"Seller state code: {vm3_seller.get('state_code','XX')} == Buyer state code: {vm3_buyer.get('state_code','XX')}",
            "Invoice shows IGST ₹2,69,000 (should be CGST ₹1,34,500 + SGST ₹1,34,500)",
            "Place of Supply field shows inter-state but actual supply is intra-state",
        ],
        "resolution_actions": [
            "Supplier to file GSTR-1 amendment correcting IGST to CGST+SGST",
            "Buyer to adjust ITC in next GSTR-3B filing",
            "No penalty if corrected within the amendment deadline",
        ],
        "regulatory_references": [
            "Section 7(1) IGST Act — Determination of inter-state supply",
            "Section 8(1) IGST Act — Determination of intra-state supply",
            "Section 77 CGST Act — Tax wrongfully collected and paid",
        ],
        "risk_category": "INFORMATIONAL",
        "seller_value": 1494444.0,
        "buyer_value": 1494444.0,
    })

    # ═══════════════════════════════════════════════════════════════
    # CASE 9-10: ITC OVERCLAIM
    # ═══════════════════════════════════════════════════════════════

    itc1_buyer = active[4]
    cases.append({
        "mismatch_id": "FRAUD-009-ITCOVR",
        "mismatch_type": "ITC_OVERCLAIM",
        "severity": "CRITICAL",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:14:09",
        "gstin": itc1_buyer["gstin"],
        "return_period": "012025",
        "composite_risk_score": 0.84,
        "itc_at_risk": 2145000.0,
        "description": f"ITC overclaimed by ₹21.45L — claimed on blocked items under Section 17(5)",
        "narrative": (
            f"{itc1_buyer['name']} claimed ITC of ₹31,20,000 in GSTR-3B for January 2025, "
            "but eligible ITC as per GSTR-2B is only ₹9,75,000. Analysis of the purchase "
            "register reveals ₹21,45,000 was claimed on items blocked under Section 17(5) "
            "of the CGST Act: (a) ₹8,50,000 on motor vehicles (not used for transportation "
            "of goods), (b) ₹6,80,000 on food & beverages for employee recreation, "
            "(c) ₹4,15,000 on outdoor catering for annual event, (d) ₹2,00,000 on "
            "membership of a club. These categories are explicitly blocked from ITC "
            "eligibility regardless of business use. The overclaim ratio is 2.2x."
        ),
        "seller_gstin": active[6]["gstin"],
        "buyer_gstin": itc1_buyer["gstin"],
        "invoice_number": "Multiple — See evidence paths",
        "gstr1_value": 0.0,
        "gstr2b_value": 31200000.0,
        "classification": "ITC Overclaim — Blocked credits under Section 17(5) claimed",
        "confidence": 92.0,
        "evidence_paths": [
            "GSTR-3B ITC claimed: ₹31,20,000 vs GSTR-2B eligible: ₹9,75,000",
            "Blocked: Motor vehicles (HSN 8703) — ₹8,50,000",
            "Blocked: Food & beverages (HSN 2106) — ₹6,80,000",
            "Blocked: Outdoor catering services (SAC 996333) — ₹4,15,000",
            "Blocked: Club membership (SAC 999592) — ₹2,00,000",
            "Overclaim ratio: 3.2x (claimed ₹31.2L vs eligible ₹9.75L)",
        ],
        "resolution_actions": [
            "Reverse ₹21,45,000 blocked ITC in next GSTR-3B",
            "Pay interest under Section 50(1) at 18% p.a. from date of claim",
            "File DRC-03 for voluntary payment to avoid penalty proceedings",
        ],
        "regulatory_references": [
            "Section 17(5)(a) CGST Act — Motor vehicles (blocked ITC)",
            "Section 17(5)(b) CGST Act — Food, beverages, outdoor catering (blocked)",
            "Section 17(5)(d) CGST Act — Club/fitness centre membership (blocked)",
            "Section 50(1) CGST Act — Interest on delayed payment",
        ],
        "risk_category": "DEMAND_NOTICE",
        "claimed_amount": 3120000.0,
        "eligible_amount": 975000.0,
    })

    # Case 10: ITC in excess of GSTR-2B
    itc2_buyer = active[11]
    cases.append({
        "mismatch_id": "FRAUD-010-ITCOVR",
        "mismatch_type": "ITC_OVERCLAIM",
        "severity": "HIGH",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:18:30",
        "gstin": itc2_buyer["gstin"],
        "return_period": "112024",
        "composite_risk_score": 0.71,
        "itc_at_risk": 892350.0,
        "description": "ITC claimed in GSTR-3B exceeds available credit in GSTR-2B by ₹8.92L",
        "narrative": (
            f"{itc2_buyer['name']} claimed IGST ITC of ₹18,42,350 in November 2024 "
            "GSTR-3B, but the auto-populated GSTR-2B shows eligible ITC of only "
            "₹9,50,000. The excess of ₹8,92,350 has no supporting documentation "
            "in the GSTR-2B. Analysis shows the buyer manually entered additional "
            "ITC of ₹8,92,350 under 'All other ITC' section of GSTR-3B Table 4(A)(5), "
            "which is meant only for ITC on imports, ISD credits, and transitional "
            "credits — none of which apply here. The buyer has a history of claiming "
            "excess ITC in 3 of the previous 5 months."
        ),
        "seller_gstin": active[7]["gstin"],
        "buyer_gstin": itc2_buyer["gstin"],
        "invoice_number": "GSTR3B-NOV24-EXCESS",
        "gstr1_value": 0.0,
        "gstr2b_value": 950000.0,
        "classification": "ITC Overclaim — GSTR-3B exceeds GSTR-2B by ₹8,92,350",
        "confidence": 88.0,
        "evidence_paths": [
            "GSTR-3B Table 4(A)(5) 'All other ITC': ₹8,92,350 claimed without basis",
            "GSTR-2B total eligible ITC: ₹9,50,000",
            "GSTR-3B total ITC claimed: ₹18,42,350 (excess ₹8,92,350)",
            "Repeat offender: 3 of last 5 months show excess claims (Jul, Sep, Oct 2024)",
        ],
        "resolution_actions": [
            "Restrict ITC to GSTR-2B amount under Rule 36(4)",
            "Issue notice under Section 74 (fraud/wilful misstatement — extended period)",
            "Impose penalty of ₹8,92,350 under Section 122(2)(b)",
        ],
        "regulatory_references": [
            "Rule 36(4) CGST Rules — ITC capped at GSTR-2B values",
            "Section 74 CGST Act — Determination of tax with fraud intent",
            "Section 122(2)(b) CGST Act — Penalty for claiming excess ITC",
        ],
        "risk_category": "DEMAND_NOTICE",
        "claimed_amount": 1842350.0,
        "eligible_amount": 950000.0,
    })

    # ═══════════════════════════════════════════════════════════════
    # CASE 11-13: MISSING IN GSTR-2B / GSTR-1
    # ═══════════════════════════════════════════════════════════════

    miss1_seller = active[2]
    miss1_buyer = active[6]
    inv11 = _pick_invoice(inv_by_supplier, miss1_seller["gstin"], invoices)
    cases.append({
        "mismatch_id": "FRAUD-011-MISS2B",
        "mismatch_type": "MISSING_IN_GSTR2B",
        "severity": "HIGH",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:22:45",
        "gstin": miss1_buyer["gstin"],
        "return_period": "082024",
        "composite_risk_score": 0.68,
        "itc_at_risk": 456780.0,
        "description": "3 invoices from supplier not reflected in GSTR-2B — ITC blocked",
        "narrative": (
            f"Three invoices from {miss1_seller['name']} totalling ₹25,37,667 are present "
            f"in the supplier's GSTR-1 but NOT reflected in {miss1_buyer['name']}'s "
            "GSTR-2B for August 2024. This means ITC of ₹4,56,780 cannot be claimed. "
            "Root cause analysis: The supplier filed GSTR-1 for August on 11-Oct-2024 "
            "(2 months late), after the GSTR-2B for August had already been generated. "
            "Late-filed GSTR-1 entries are only reflected in the GSTR-2B of the month "
            "in which the GSTR-1 is actually filed. Buyer should check October 2024 "
            "GSTR-2B for these invoices."
        ),
        "seller_gstin": miss1_seller["gstin"],
        "buyer_gstin": miss1_buyer["gstin"],
        "invoice_number": inv11.get("invoice_number", "INV/2425/000165"),
        "gstr1_value": 2537667.0,
        "gstr2b_value": 0.0,
        "classification": "Missing in GSTR-2B — Supplier filed GSTR-1 late",
        "confidence": 90.0,
        "evidence_paths": [
            "GSTR-1 contains 3 invoices: INV/2425/000165, INV/2425/000166, INV/2425/000167",
            "GSTR-2B for Aug 2024: NONE of the 3 invoices reflected",
            "GSTR-1 filing date: 11-Oct-2024 (due date: 11-Sep-2024, 30 days late)",
            "GSTR-2B generation is based on GSTR-1 filed up to filing date",
        ],
        "resolution_actions": [
            "Check GSTR-2B for October 2024 — late-filed invoices may appear there",
            "Contact supplier to verify GSTR-1 filing and invoice details",
            "If still missing, raise grievance on GST portal under 'ITC Mismatch'",
        ],
        "regulatory_references": [
            "Section 16(2)(aa) CGST Act — ITC available only upon reflection in GSTR-2B",
            "Section 37(3) CGST Act — Details furnished in GSTR-1 cannot be rectified after filing",
            "Rule 60(1) CGST Rules — GSTR-2B auto-generated from GSTR-1 data",
        ],
        "risk_category": "ITC_REVERSAL",
        "seller_value": 2537667.0,
        "buyer_value": 0.0,
    })

    # Case 12: Missing in GSTR-1 — potential phantom
    miss2_buyer = active[8]
    cases.append({
        "mismatch_id": "FRAUD-012-MISS1",
        "mismatch_type": "MISSING_IN_GSTR1",
        "severity": "CRITICAL",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:25:18",
        "gstin": miss2_buyer["gstin"],
        "return_period": "012025",
        "composite_risk_score": 0.82,
        "itc_at_risk": 1034200.0,
        "description": "Invoice in GSTR-2B has no corresponding GSTR-1 entry — suspected phantom invoice",
        "narrative": (
            f"Invoice B2B2425000389 worth ₹57,45,556 appears in {miss2_buyer['name']}'s "
            "GSTR-2B for January 2025 but has NO corresponding entry in the supplier's "
            "GSTR-1. The supplier GSTIN shows 'active' status but has NOT filed "
            "GSTR-1 for Jan 2025 at all. Knowledge graph analysis reveals: "
            "(1) The supplier has zero GSTR-1 filings for the last 3 months, "
            "(2) No TRANSACTS_WITH relationship exists between these two GSTINs "
            "prior to Jan 2025, (3) The supplier was registered only 4 months ago "
            "with minimal turnover declaration (₹20L). This creates a strong "
            "suspicion of either a newly created shell entity or identity theft "
            "of an existing GSTIN."
        ),
        "seller_gstin": active[13]["gstin"] if len(active) > 13 else active[0]["gstin"],
        "buyer_gstin": miss2_buyer["gstin"],
        "invoice_number": "B2B2425000389",
        "gstr1_value": 0.0,
        "gstr2b_value": 5745556.0,
        "classification": "Missing in GSTR-1 — Supplier has not filed; suspected shell entity",
        "confidence": 82.0,
        "evidence_paths": [
            "GSTR-2B shows invoice B2B2425000389: ₹57,45,556",
            "Supplier GSTR-1 for Jan 2025: NOT FILED",
            "Supplier GSTR-1 filing history: 0 filings in last 3 months",
            "No prior TRANSACTS_WITH relationship between buyer and supplier",
            "Supplier registration age: 4 months, declared turnover: ₹20L",
        ],
        "resolution_actions": [
            "Do NOT claim ITC until GSTR-1 is filed and verified",
            "Report to concerned GST officer for supplier verification",
            "Request GSTN to flag supplier for mandatory physical verification",
        ],
        "regulatory_references": [
            "Section 16(2)(a) CGST Act — ITC only if supplier has filed GSTR-1",
            "Section 16(2)(aa) CGST Act — ITC only if reflected in GSTR-2B",
            "Rule 21A CGST Rules — Suspension of registration for non-filing",
        ],
        "risk_category": "DEMAND_NOTICE",
    })

    # Case 13: Period mismatch (date manipulation)
    miss3_seller = active[7]
    miss3_buyer = active[9]
    cases.append({
        "mismatch_id": "FRAUD-013-PERIOD",
        "mismatch_type": "MISSING_IN_GSTR2B",
        "severity": "MEDIUM",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:28:50",
        "gstin": miss3_buyer["gstin"],
        "return_period": "062024",
        "composite_risk_score": 0.42,
        "itc_at_risk": 178900.0,
        "description": "Invoice date in GSTR-1 (May) differs from GSTR-2B period (June) — period mismatch",
        "narrative": (
            f"Invoice INV/2425/000089 from {miss3_seller['name']} is dated 28-May-2024 "
            "and reported in May 2024 GSTR-1, but appears in the buyer's June 2024 "
            "GSTR-2B. This period mismatch occurred because the supplier filed May GSTR-1 "
            "on 12-Jun-2024 (1 day after the normal deadline), causing the invoice to "
            "spill into the June GSTR-2B cycle. While not necessarily fraudulent, "
            "the ITC of ₹1,78,900 should be claimed in June 2024 GSTR-3B (when it "
            "appears in GSTR-2B) rather than May 2024. If already claimed in May, "
            "it should be reversed and re-claimed in June."
        ),
        "seller_gstin": miss3_seller["gstin"],
        "buyer_gstin": miss3_buyer["gstin"],
        "invoice_number": "INV/2425/000089",
        "gstr1_value": 993889.0,
        "gstr2b_value": 993889.0,
        "classification": "Period Mismatch — GSTR-1 filed late causing GSTR-2B period shift",
        "confidence": 95.0,
        "evidence_paths": [
            "Invoice date: 28-May-2024 (should be in May GSTR-2B)",
            "Supplier GSTR-1 filed: 12-Jun-2024 (1 day late → spills to June cycle)",
            "Invoice appears in buyer's June 2024 GSTR-2B, not May 2024",
            "No monetary loss — only timing difference in ITC claim",
        ],
        "resolution_actions": [
            "Claim ITC in June 2024 GSTR-3B (matching GSTR-2B period)",
            "If already claimed in May, reverse in June; no interest if corrected promptly",
        ],
        "regulatory_references": [
            "Section 16(4) CGST Act — Time limit for availing ITC",
            "Rule 60(1) CGST Rules — GSTR-2B generation based on GSTR-1 filing date",
        ],
        "risk_category": "INFORMATIONAL",
        "seller_value": 993889.0,
        "buyer_value": 993889.0,
    })

    # ═══════════════════════════════════════════════════════════════
    # CASE 14-15: TAX RATE MISMATCH
    # ═══════════════════════════════════════════════════════════════

    tr1_seller = active[3]
    tr1_buyer = active[11]
    cases.append({
        "mismatch_id": "FRAUD-014-TAXRT",
        "mismatch_type": "TAX_RATE_MISMATCH",
        "severity": "HIGH",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:32:15",
        "gstin": tr1_buyer["gstin"],
        "return_period": "102024",
        "composite_risk_score": 0.69,
        "itc_at_risk": 325400.0,
        "description": "Tax rate mismatch — Supplier charged 12% but buyer claimed at 18%",
        "narrative": (
            f"HSN misclassification detected: {tr1_seller['name']} supplied 'Food "
            "Preparations' (HSN 2106) and correctly applied 12% GST in GSTR-1. "
            f"However, {tr1_buyer['name']} has classified the same supply under "
            "'Plastic Articles' (HSN 3926) attracting 18% GST in their purchase register "
            "and claimed ITC at the higher rate. This deliberate HSN misclassification "
            "results in excess ITC of ₹3,25,400. The invoice description clearly states "
            "'Ready-to-eat food packets' (GST rate 12%), ruling out genuine confusion. "
            "The buyer's purchase register consistently maps this supplier's invoices "
            "to higher-rate HSN codes."
        ),
        "seller_gstin": tr1_seller["gstin"],
        "buyer_gstin": tr1_buyer["gstin"],
        "invoice_number": "INV/2425/000331",
        "gstr1_value": 5423333.0,
        "gstr2b_value": 5423333.0,
        "classification": "Tax Rate Mismatch — 12% (correct) vs 18% (claimed). Likely HSN misclassification.",
        "confidence": 85.0,
        "evidence_paths": [
            "GSTR-1: HSN 2106 (Food Preparations) @ 12% → Tax = ₹6,50,800",
            "Purchase Register: HSN 3926 (Plastic Articles) @ 18% → Tax = ₹9,76,200",
            "Excess ITC claimed: ₹9,76,200 - ₹6,50,800 = ₹3,25,400",
            "Invoice description: 'Ready-to-eat food packets' clearly HSN 2106",
        ],
        "resolution_actions": [
            "Reverse excess ITC of ₹3,25,400 in next GSTR-3B",
            "Correct HSN classification in purchase register",
            "If intentional, penalty under Section 122(1)(iv) for incorrect rate application",
        ],
        "regulatory_references": [
            "Section 16(1) CGST Act — ITC limited to tax actually paid",
            "Section 122(1)(iv) CGST Act — Penalty for charging incorrect tax rate",
            "Circular 179/11/2022-GST — HSN classification guidelines",
        ],
        "risk_category": "ITC_REVERSAL",
        "seller_rate": 12.0,
        "buyer_rate": 18.0,
        "seller_value": 5423333.0,
        "buyer_value": 5423333.0,
    })

    # Case 15: Wrong rate both ways
    tr2_seller = active[10]
    tr2_buyer = active[4]
    cases.append({
        "mismatch_id": "FRAUD-015-TAXRT",
        "mismatch_type": "TAX_RATE_MISMATCH",
        "severity": "MEDIUM",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:35:22",
        "gstin": tr2_buyer["gstin"],
        "return_period": "052024",
        "composite_risk_score": 0.51,
        "itc_at_risk": 189750.0,
        "description": "Supplier applied 28% on item eligible for 18% — excess charged to buyer",
        "narrative": (
            f"{tr2_seller['name']} charged 28% GST on 'Computer Accessories' (HSN 8471) "
            "which should attract 18% GST. The buyer has claimed ITC at 28%, resulting in "
            "₹1,89,750 excess ITC. While the buyer is not at fault for claiming what was "
            "charged, the supplier has collected excess tax that must be deposited. "
            "The buyer can only claim ITC on tax actually due (18%), not tax charged (28%). "
            "This requires coordination between supplier and buyer for correction."
        ),
        "seller_gstin": tr2_seller["gstin"],
        "buyer_gstin": tr2_buyer["gstin"],
        "invoice_number": "INV/2425/000052",
        "gstr1_value": 1897500.0,
        "gstr2b_value": 1897500.0,
        "classification": "Tax Rate Mismatch — 28% charged (should be 18%). Supplier error.",
        "confidence": 90.0,
        "evidence_paths": [
            "HSN 8471 (Computers/Accessories): Standard rate = 18%",
            "Invoice shows: IGST @ 28% = ₹5,31,300",
            "Correct tax @ 18% = ₹3,41,550",
            "Excess collected by supplier: ₹1,89,750",
        ],
        "resolution_actions": [
            "Supplier to issue credit note for ₹1,89,750 excess tax",
            "Buyer to reverse excess ITC of ₹1,89,750",
            "Supplier to file refund application under Section 54 for excess deposit",
        ],
        "regulatory_references": [
            "Section 34 CGST Act — Credit and debit notes",
            "Section 54(8) CGST Act — Refund of tax paid in excess",
            "Section 77 CGST Act — Tax wrongfully collected and paid",
        ],
        "risk_category": "ITC_REVERSAL",
        "seller_rate": 28.0,
        "buyer_rate": 18.0,
        "seller_value": 1897500.0,
        "buyer_value": 1897500.0,
    })

    # ═══════════════════════════════════════════════════════════════
    # CASE 16: DUPLICATE INVOICE
    # ═══════════════════════════════════════════════════════════════

    dup_seller = active[5]
    dup_buyer = active[1]
    cases.append({
        "mismatch_id": "FRAUD-016-DUPLI",
        "mismatch_type": "DUPLICATE",
        "severity": "HIGH",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:38:40",
        "gstin": dup_buyer["gstin"],
        "return_period": "112024",
        "composite_risk_score": 0.73,
        "itc_at_risk": 567800.0,
        "description": "Same invoice claimed twice — once in Oct 2024 GSTR-3B and again in Nov 2024",
        "narrative": (
            f"Invoice INV/2425/000275 from {dup_seller['name']} worth ₹31,54,444 "
            f"has been claimed for ITC by {dup_buyer['name']} in BOTH October and "
            "November 2024 GSTR-3B filings. The duplicate claim of ₹5,67,800 ITC "
            "(CGST ₹2,83,900 + SGST ₹2,83,900) represents a clear double-dip. "
            "The invoice appears only once in GSTR-2B (October 2024), confirming "
            "the November claim is a duplicate. The purchase register shows the "
            "invoice booked twice — on 28-Oct-2024 and again on 03-Nov-2024 with "
            "a different internal reference number, suggesting intentional double booking."
        ),
        "seller_gstin": dup_seller["gstin"],
        "buyer_gstin": dup_buyer["gstin"],
        "invoice_number": "INV/2425/000275",
        "gstr1_value": 3154444.0,
        "gstr2b_value": 3154444.0,
        "classification": "Duplicate Invoice — ITC claimed twice across consecutive months",
        "confidence": 96.0,
        "evidence_paths": [
            "Invoice INV/2425/000275 in Oct 2024 GSTR-3B: ITC ₹5,67,800",
            "Same invoice in Nov 2024 GSTR-3B: ITC ₹5,67,800 (DUPLICATE)",
            "GSTR-2B shows invoice only in Oct 2024 — Nov claim has no basis",
            "Purchase Register: booked on 28-Oct (PR-OCT-275) AND 03-Nov (PR-NOV-012)",
        ],
        "resolution_actions": [
            "Reverse duplicate ITC of ₹5,67,800 from Nov 2024 GSTR-3B",
            "Pay interest @ 18% p.a. under Section 50(1) from Nov filing date",
            "Rectify purchase register to remove duplicate entry PR-NOV-012",
        ],
        "regulatory_references": [
            "Section 16(2)(aa) CGST Act — ITC only on invoices in GSTR-2B (once)",
            "Rule 36(1) CGST Rules — No duplicate ITC on same document",
            "Section 50(1) CGST Act — Interest on delayed/excess ITC claims",
        ],
        "risk_category": "ITC_REVERSAL",
    })

    # ═══════════════════════════════════════════════════════════════
    # CASE 17: E-WAY BILL MISMATCH
    # ═══════════════════════════════════════════════════════════════

    ewb_seller = active[6]
    ewb_buyer = active[12]
    cases.append({
        "mismatch_id": "FRAUD-017-EWBMM",
        "mismatch_type": "EWB_MISMATCH",
        "severity": "MEDIUM",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:42:15",
        "gstin": ewb_buyer["gstin"],
        "return_period": "092024",
        "composite_risk_score": 0.45,
        "itc_at_risk": 0.0,
        "description": "E-Way Bill value differs from invoice by ₹12.4L — possible part shipment or under-billing",
        "narrative": (
            f"Invoice INV/2425/000221 from {ewb_seller['name']} shows total value of "
            "₹38,50,000, but the associated E-Way Bill (EWB-2024-09-3892) was generated "
            "for only ₹26,10,000 — a difference of ₹12,40,000 (32.2%). While this could "
            "indicate a part-shipment scenario, no Part-B update or multi-vehicle entry "
            "exists on the E-Way Bill. The transporter confirms only one shipment for "
            "this invoice. Possible explanations: (a) invoice was inflated after E-Way Bill "
            "generation, (b) goods worth ₹12.4L were never shipped (partial phantom), "
            "or (c) supplementary invoice not accounted in EWB. The distance recorded "
            "(310 km) aligns with the delivery address, ruling out transit issues."
        ),
        "seller_gstin": ewb_seller["gstin"],
        "buyer_gstin": ewb_buyer["gstin"],
        "invoice_number": "INV/2425/000221",
        "gstr1_value": 3850000.0,
        "gstr2b_value": 3850000.0,
        "classification": "E-Way Bill Mismatch — Invoice ₹38.5L vs EWB ₹26.1L (Δ=32.2%)",
        "confidence": 72.0,
        "evidence_paths": [
            "Invoice INV/2425/000221: total_value = ₹38,50,000",
            "E-Way Bill EWB-2024-09-3892: total_value = ₹26,10,000",
            "Difference: ₹12,40,000 (32.2% of invoice value)",
            "No Part-B multi-vehicle entry on EWB — single shipment confirmed",
            "Transporter verification: only 1 consignment delivered",
        ],
        "resolution_actions": [
            "Request supplier to explain value discrepancy with documentary evidence",
            "If partial shipment, obtain supplementary invoice and new EWB",
            "If invoice was inflated, reverse ITC on excess amount (₹2,23,200 @ 18%)",
        ],
        "regulatory_references": [
            "Rule 138 CGST Rules — E-Way Bill requirements for movement of goods",
            "Rule 138A CGST Rules — Documents to be carried during transportation",
            "Section 129 CGST Act — Detention, seizure and release of goods in transit",
        ],
        "risk_category": "AUDIT_TRIGGER",
        "seller_value": 3850000.0,
        "buyer_value": 2610000.0,
    })

    # ═══════════════════════════════════════════════════════════════
    # CASE 18: IRN INVALID (cancelled e-Invoice)
    # ═══════════════════════════════════════════════════════════════

    irn_seller = active[0]
    irn_buyer = active[14] if len(active) > 14 else active[4]
    cases.append({
        "mismatch_id": "FRAUD-018-IRNINV",
        "mismatch_type": "IRN_INVALID",
        "severity": "MEDIUM",
        "status": "OPEN",
        "detected_at": "2026-02-27T10:45:30",
        "gstin": irn_buyer["gstin"],
        "return_period": "122024",
        "composite_risk_score": 0.52,
        "itc_at_risk": 234500.0,
        "description": "ITC claimed on invoice whose e-Invoice (IRN) was cancelled by supplier",
        "narrative": (
            f"{irn_seller['name']} generated IRN for invoice INV/2425/000348 on 05-Dec-2024 "
            "and subsequently cancelled it on 06-Dec-2024 within the 24-hour window. "
            f"However, {irn_buyer['name']} has claimed ITC of ₹2,34,500 against this "
            "cancelled invoice in their December 2024 GSTR-3B. The cancellation was "
            "due to a data entry error (wrong recipient GSTIN was entered). A corrected "
            "invoice with a new IRN was generated on 07-Dec-2024, but the buyer appears "
            "to have claimed ITC on BOTH the cancelled and corrected invoices. "
            "Total double claim exposure: ₹4,69,000."
        ),
        "seller_gstin": irn_seller["gstin"],
        "buyer_gstin": irn_buyer["gstin"],
        "invoice_number": "INV/2425/000348",
        "gstr1_value": 1302778.0,
        "gstr2b_value": 1302778.0,
        "classification": "IRN Invalid — e-Invoice cancelled but ITC still claimed",
        "confidence": 78.0,
        "evidence_paths": [
            "IRN generated: 05-Dec-2024, IRN status: CANCELLED (06-Dec-2024)",
            "Cancellation reason: Wrong recipient GSTIN",
            "Corrected IRN generated: 07-Dec-2024 for same supply",
            "Buyer claimed ITC on both cancelled (₹2,34,500) and corrected (₹2,34,500) IRNs",
        ],
        "resolution_actions": [
            "Reverse ITC of ₹2,34,500 against cancelled IRN",
            "Retain ITC against corrected IRN only if it matches GSTR-2B",
            "Update purchase register to remove cancelled invoice reference",
        ],
        "regulatory_references": [
            "Rule 48(3) CGST Rules — Cancellation of IRN within 24 hours",
            "Section 16(2)(aa) CGST Act — ITC only on valid invoices in GSTR-2B",
            "Notification 13/2020-CT — e-Invoicing requirements and IRN validity",
        ],
        "risk_category": "ITC_REVERSAL",
    })

    return cases


# ─────────────────────── Helper Functions ───────────────────────

def _circular_trade_case(case_num, participants, period, values, inflation, narrative):
    """Build a circular trade fraud case."""
    names = [p["name"] for p in participants]
    gstins = [p["gstin"] for p in participants]
    total_value = sum(values)
    itc_at_risk = round(total_value * 0.18, 2)
    chain = " → ".join(names) + f" → {names[0]}"

    evidence = []
    for i in range(len(participants)):
        j = (i + 1) % len(participants)
        evidence.append(
            f"{gstins[i]} -[TRANSACTS_WITH]-> {gstins[j]}: ₹{values[i]:,.0f}"
        )
    evidence.append(f"Value inflation ratio: {inflation}x across cycle")
    evidence.append(f"No bank payments found between {len(participants) - 1} of {len(participants)} entity pairs")

    severity = "CRITICAL" if inflation > 1.3 else "HIGH"
    risk_score = min(0.95, round(0.70 + (inflation - 1.0) * 0.5, 2))

    return {
        "mismatch_id": f"FRAUD-{case_num:03d}-CIRC",
        "mismatch_type": "CIRCULAR_TRADE",
        "severity": severity,
        "status": "OPEN",
        "detected_at": "2026-02-27T08:45:12",
        "gstin": gstins[0],
        "return_period": period,
        "composite_risk_score": risk_score,
        "itc_at_risk": itc_at_risk,
        "description": f"Circular trade ring: {chain}",
        "narrative": narrative,
        "seller_gstin": gstins[0],
        "buyer_gstin": gstins[-1],
        "invoice_number": f"CIRC-RING-{case_num:03d}",
        "gstr1_value": total_value,
        "gstr2b_value": total_value,
        "classification": f"{len(participants)}-entity circular trade with {inflation}x value inflation",
        "confidence": round(random.uniform(84.0, 96.0), 1),
        "evidence_paths": evidence,
        "resolution_actions": [
            f"Freeze ITC for all {len(participants)} entities pending investigation",
            "Issue SCN under Section 74 CGST Act (fraud/wilful misstatement)",
            "Refer to DGGI for coordinated investigation across jurisdictions",
            f"Provisional attachment of property under Section 83 (₹{itc_at_risk:,.0f} at risk)",
        ],
        "regulatory_references": [
            "Section 74 CGST Act — Determination of tax with fraud intent (5-year lookback)",
            "Section 83 CGST Act — Provisional attachment of property",
            "Section 132(1)(b) CGST Act — Issuing invoice without supply of goods",
            "Section 132(1)(c) CGST Act — Availing ITC using invoice without supply",
        ],
        "risk_category": "DEMAND_NOTICE",
        "participants": chain,
        "total_value": total_value,
        "inflation_ratio": inflation,
    }


def _pick_invoice(inv_by_supplier, gstin, all_invoices):
    """Pick a relevant invoice for a supplier, fallback to any."""
    if gstin in inv_by_supplier and inv_by_supplier[gstin]:
        return inv_by_supplier[gstin][0]
    return all_invoices[0] if all_invoices else {"invoice_number": "INV/2425/UNKNOWN"}


# ─────────────────────── Persistence ───────────────────────

def _persist_fraud_cases(cases):
    """Write Mismatch nodes to Neo4j."""
    for c in cases:
        # Convert lists to string representations for Neo4j
        evidence = c.get("evidence_paths", [])
        actions = c.get("resolution_actions", [])
        reg_refs = c.get("regulatory_references", [])

        execute_write("""
            CREATE (m:Mismatch {
                mismatch_id: $mismatch_id,
                mismatch_type: $mismatch_type,
                severity: $severity,
                status: $status,
                detected_at: $detected_at,
                gstin: $gstin,
                return_period: $return_period,
                composite_risk_score: $composite_risk_score,
                itc_at_risk: $itc_at_risk,
                description: $description,
                narrative: $narrative,
                seller_gstin: $seller_gstin,
                buyer_gstin: $buyer_gstin,
                invoice_number: $invoice_number,
                gstr1_value: $gstr1_value,
                gstr2b_value: $gstr2b_value,
                classification: $classification,
                confidence: $confidence,
                evidence_paths: $evidence_paths,
                resolution_actions: $resolution_actions,
                regulatory_references: $regulatory_references,
                risk_category: $risk_category
            })
        """, {
            "mismatch_id": c.get("mismatch_id", ""),
            "mismatch_type": c.get("mismatch_type", ""),
            "severity": c.get("severity", "MEDIUM"),
            "status": c.get("status", "OPEN"),
            "detected_at": c.get("detected_at", "2026-02-27T08:00:00"),
            "gstin": c.get("gstin", ""),
            "return_period": c.get("return_period", ""),
            "composite_risk_score": c.get("composite_risk_score", 0.5),
            "itc_at_risk": c.get("itc_at_risk", 0.0),
            "description": c.get("description", ""),
            "narrative": c.get("narrative", ""),
            "seller_gstin": c.get("seller_gstin", ""),
            "buyer_gstin": c.get("buyer_gstin", ""),
            "invoice_number": c.get("invoice_number", ""),
            "gstr1_value": c.get("gstr1_value", 0.0),
            "gstr2b_value": c.get("gstr2b_value", 0.0),
            "classification": c.get("classification", ""),
            "confidence": c.get("confidence", 0.0),
            "evidence_paths": evidence,
            "resolution_actions": actions,
            "regulatory_references": reg_refs,
            "risk_category": c.get("risk_category", "INFORMATIONAL"),
        })
    logger.info(f"Persisted {len(cases)} Mismatch nodes to Neo4j")


def _link_mismatches_to_invoices():
    """Create INVOLVES relationships from Mismatch to Invoice nodes."""
    execute_write("""
        MATCH (m:Mismatch)
        WHERE m.invoice_number IS NOT NULL AND m.invoice_number <> ''
          AND NOT m.invoice_number STARTS WITH 'CIRC-'
          AND NOT m.invoice_number STARTS WITH 'Multiple'
          AND NOT m.invoice_number STARTS WITH 'GSTR3B'
        WITH m
        OPTIONAL MATCH (inv:Invoice {invoice_number: m.invoice_number})
        WHERE inv IS NOT NULL
        MERGE (m)-[:INVOLVES]->(inv)
    """)
    logger.info("Linked Mismatch nodes to Invoice nodes via INVOLVES relationships")
