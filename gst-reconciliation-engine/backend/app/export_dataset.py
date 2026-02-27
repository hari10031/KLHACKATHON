"""
Export complete GST Reconciliation Engine dataset from Neo4j to local files.
Generates CSV + JSON files for all node types and relationships.

Usage:
    cd backend
    python -m app.export_dataset
"""

import csv
import json
import os
import sys
from datetime import datetime

# Add parent dir so app imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import execute_query
from loguru import logger


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "dataset")


def ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info(f"Dataset output directory: {os.path.abspath(OUTPUT_DIR)}")


def write_csv(filename, rows, fields=None):
    if not rows:
        logger.warning(f"No data for {filename}")
        return
    if fields is None:
        fields = list(rows[0].keys())
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Wrote {len(rows)} rows to {filename}")


def write_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Wrote {filename}")


def export_gstins():
    """Export all GSTIN nodes."""
    rows = execute_query("""
        MATCH (g:GSTIN)
        OPTIONAL MATCH (g)-[:BELONGS_TO]->(t:Taxpayer)
        RETURN g.gstin_number AS gstin,
               g.state_code AS state_code,
               g.registration_date AS registration_date,
               g.status AS status,
               g.risk_score AS risk_score,
               g.risk_label AS risk_label,
               g.pagerank AS pagerank,
               g.degree AS degree,
               g.betweenness AS betweenness,
               g.community AS community,
               t.entity_name AS entity_name,
               t.pan AS pan,
               t.address AS address
        ORDER BY g.gstin_number
    """)
    write_csv("gstins.csv", rows)
    return rows


def export_invoices():
    """Export all Invoice nodes."""
    rows = execute_query("""
        MATCH (inv:Invoice)
        OPTIONAL MATCH (seller:GSTIN)-[:ISSUED_INVOICE]->(inv)
        OPTIONAL MATCH (inv)-[:RECEIVED_BY]->(buyer:GSTIN)
        OPTIONAL MATCH (seller)-[:BELONGS_TO]->(st:Taxpayer)
        OPTIONAL MATCH (buyer)-[:BELONGS_TO]->(bt:Taxpayer)
        RETURN inv.invoice_number AS invoice_number,
               inv.invoice_date AS invoice_date,
               inv.taxable_value AS taxable_value,
               inv.cgst AS cgst,
               inv.sgst AS sgst,
               inv.igst AS igst,
               inv.total_tax AS total_tax,
               inv.total_value AS total_value,
               inv.place_of_supply AS place_of_supply,
               inv.reverse_charge AS reverse_charge,
               seller.gstin_number AS seller_gstin,
               st.entity_name AS seller_name,
               buyer.gstin_number AS buyer_gstin,
               bt.entity_name AS buyer_name
        ORDER BY inv.invoice_date DESC
        LIMIT 5000
    """)
    write_csv("invoices.csv", rows)
    return rows


def export_returns():
    """Export all Return nodes."""
    rows = execute_query("""
        MATCH (r:Return)
        OPTIONAL MATCH (g:GSTIN)-[:FILED_RETURN]->(r)
        RETURN r.return_type AS return_type,
               r.return_period AS return_period,
               r.filing_date AS filing_date,
               r.total_taxable AS total_taxable,
               r.total_tax AS total_tax,
               r.total_invoices AS total_invoices,
               r.status AS status,
               g.gstin_number AS gstin
        ORDER BY r.return_period DESC
    """)
    write_csv("returns.csv", rows)
    return rows


def export_mismatches():
    """Export all Mismatch/fraud detection nodes — THE KEY DELIVERABLE."""
    rows = execute_query("""
        MATCH (m:Mismatch)
        RETURN m.mismatch_id AS mismatch_id,
               m.type AS type,
               m.severity AS severity,
               m.description AS description,
               m.narrative AS narrative,
               m.evidence_path AS evidence_path,
               m.resolution_actions AS resolution_actions,
               m.regulatory_ref AS regulatory_ref,
               m.gstin AS gstin,
               m.buyer_gstin AS buyer_gstin,
               m.seller_gstin AS seller_gstin,
               m.return_period AS return_period,
               m.invoice_value AS invoice_value,
               m.tax_difference AS tax_difference,
               m.itc_risk AS itc_risk,
               m.risk_score AS risk_score,
               m.detected_at AS detected_at,
               m.status AS status
        ORDER BY m.severity, m.itc_risk DESC
    """)
    write_csv("mismatches.csv", rows)
    return rows


def export_relationships():
    """Export relationship summary."""
    rows = execute_query("""
        MATCH ()-[r]->()
        WITH type(r) AS rel_type, count(r) AS count
        RETURN rel_type, count
        ORDER BY count DESC
    """)
    write_csv("relationship_summary.csv", rows)

    # Sample relationships (first 2000)
    detail = execute_query("""
        MATCH (a)-[r]->(b)
        RETURN labels(a)[0] AS from_type,
               coalesce(a.gstin_number, a.invoice_number, a.mismatch_id, a.return_type, labels(a)[0]) AS from_id,
               type(r) AS relationship,
               labels(b)[0] AS to_type,
               coalesce(b.gstin_number, b.invoice_number, b.mismatch_id, b.return_type, labels(b)[0]) AS to_id
        LIMIT 2000
    """)
    write_csv("relationships_detail.csv", detail)
    return rows


def export_risk_scores():
    """Export risk analysis data."""
    rows = execute_query("""
        MATCH (g:GSTIN)
        WHERE g.risk_score IS NOT NULL
        OPTIONAL MATCH (g)-[:BELONGS_TO]->(t:Taxpayer)
        RETURN g.gstin_number AS gstin,
               t.entity_name AS entity_name,
               g.risk_score AS risk_score,
               g.risk_label AS risk_label,
               g.pagerank AS pagerank,
               g.degree AS degree,
               g.betweenness AS betweenness,
               g.community AS community
        ORDER BY g.risk_score DESC
    """)
    write_csv("risk_scores.csv", rows)
    return rows


def build_summary(gstins, invoices, returns, mismatches, risk_scores):
    """Build comprehensive summary JSON."""
    sev_counts = {}
    type_counts = {}
    total_itc = 0
    for m in mismatches:
        sev = m.get("severity", "UNKNOWN")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        t = m.get("type", "UNKNOWN")
        type_counts[t] = type_counts.get(t, 0) + 1
        total_itc += m.get("itc_risk") or 0

    high_risk = [r for r in risk_scores if (r.get("risk_score") or 0) > 0.5]

    summary = {
        "export_timestamp": datetime.now().isoformat(),
        "database_stats": {
            "total_gstins": len(gstins),
            "total_invoices": len(invoices),
            "total_returns": len(returns),
            "total_mismatches": len(mismatches),
            "gstins_with_risk_scores": len(risk_scores),
        },
        "fraud_analysis": {
            "severity_distribution": sev_counts,
            "mismatch_types": type_counts,
            "total_itc_at_risk": total_itc,
            "high_risk_entities": len(high_risk),
        },
        "top_fraud_cases": mismatches[:10],
        "high_risk_vendors": [
            {
                "gstin": r["gstin"],
                "entity_name": r.get("entity_name"),
                "risk_score": r.get("risk_score"),
                "risk_label": r.get("risk_label"),
            }
            for r in high_risk[:20]
        ],
    }
    return summary


def main():
    logger.info("=" * 60)
    logger.info("GST Reconciliation Engine — Dataset Export")
    logger.info("=" * 60)

    ensure_dir()

    gstins = export_gstins()
    invoices = export_invoices()
    returns = export_returns()
    mismatches = export_mismatches()
    export_relationships()
    risk_scores = export_risk_scores()

    summary = build_summary(gstins, invoices, returns, mismatches, risk_scores)
    write_json("fraud_analysis_summary.json", summary)

    # Also write full mismatches as JSON for easier parsing
    write_json("mismatches_full.json", mismatches)

    logger.info("=" * 60)
    logger.info(f"Export complete! Files saved to: {os.path.abspath(OUTPUT_DIR)}")
    logger.info(f"  - gstins.csv ({len(gstins)} records)")
    logger.info(f"  - invoices.csv ({len(invoices)} records)")
    logger.info(f"  - returns.csv ({len(returns)} records)")
    logger.info(f"  - mismatches.csv ({len(mismatches)} records)")
    logger.info(f"  - risk_scores.csv ({len(risk_scores)} records)")
    logger.info(f"  - relationship_summary.csv")
    logger.info(f"  - relationships_detail.csv")
    logger.info(f"  - fraud_analysis_summary.json")
    logger.info(f"  - mismatches_full.json")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
