"""
Feature extraction from Neo4j knowledge graph for vendor risk prediction.

Features extracted per GSTIN:
  - Transaction volume metrics
  - Mismatch profile
  - Network centrality metrics
  - Filing compliance
  - Financial pattern indicators
"""

from typing import List, Dict
import numpy as np
from loguru import logger

from app.database import execute_query


FEATURE_NAMES = [
    # Transaction features
    "total_invoices_issued",
    "total_invoices_received",
    "total_value_issued",
    "total_value_received",
    "avg_invoice_value",
    "max_invoice_value",
    "distinct_counterparties",
    "invoice_frequency_stddev",

    # Mismatch features
    "total_mismatches",
    "critical_mismatches",
    "high_mismatches",
    "mismatch_rate",
    "total_itc_at_risk",
    "avg_risk_score",
    "has_circular_trade",
    "has_phantom_invoice",

    # Network features
    "pagerank",
    "degree_centrality",
    "betweenness_centrality",
    "clustering_coefficient",
    "community_id",
    "in_degree",
    "out_degree",

    # Compliance features
    "gstr1_filing_rate",
    "gstr3b_filing_rate",
    "late_filing_count",
    "avg_filing_delay_days",

    # Financial patterns
    "itc_to_output_ratio",
    "value_concentration_index",
    "month_over_month_growth",
]


def extract_features(gstin: str) -> Dict[str, float]:
    """Extract all features for a single GSTIN."""
    features = {}

    # Transaction features
    tx = execute_query("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        OPTIONAL MATCH (g)-[:ISSUED_INVOICE]->(issued:Invoice)
        OPTIONAL MATCH (g)<-[:ISSUED_INVOICE]-(received:Invoice)
        WITH g,
             collect(DISTINCT issued) AS issued_list,
             collect(DISTINCT received) AS received_list
        RETURN
            size(issued_list) AS total_issued,
            size(received_list) AS total_received,
            COALESCE(reduce(s=0.0, i IN issued_list | s + i.total_value), 0) AS val_issued,
            COALESCE(reduce(s=0.0, i IN received_list | s + i.total_value), 0) AS val_received
    """, {"gstin": gstin})

    if tx:
        r = tx[0]
        features["total_invoices_issued"] = float(r["total_issued"])
        features["total_invoices_received"] = float(r["total_received"])
        features["total_value_issued"] = float(r["val_issued"])
        features["total_value_received"] = float(r["val_received"])
        total = r["total_issued"] + r["total_received"]
        features["avg_invoice_value"] = (r["val_issued"] + r["val_received"]) / max(total, 1)
    else:
        for k in ["total_invoices_issued", "total_invoices_received",
                   "total_value_issued", "total_value_received", "avg_invoice_value"]:
            features[k] = 0.0

    # Max invoice value & counterparties
    mx = execute_query("""
        MATCH (g:GSTIN {gstin_number: $gstin})-[:ISSUED_INVOICE]->(inv:Invoice)
        RETURN max(inv.total_value) AS max_val,
               count(DISTINCT inv.buyer_gstin) AS counterparties,
               stDev(inv.total_value) AS stddev
    """, {"gstin": gstin})
    if mx:
        features["max_invoice_value"] = float(mx[0]["max_val"] or 0)
        features["distinct_counterparties"] = float(mx[0]["counterparties"] or 0)
        features["invoice_frequency_stddev"] = float(mx[0]["stddev"] or 0)
    else:
        features["max_invoice_value"] = 0.0
        features["distinct_counterparties"] = 0.0
        features["invoice_frequency_stddev"] = 0.0

    # Mismatch features
    mm = execute_query("""
        MATCH (m:Mismatch)
        WHERE m.seller_gstin = $gstin OR m.buyer_gstin = $gstin
        RETURN count(m) AS total,
               sum(CASE WHEN m.severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
               sum(CASE WHEN m.severity = 'HIGH' THEN 1 ELSE 0 END) AS high,
               sum(COALESCE(m.itc_at_risk, 0)) AS itc_risk,
               avg(COALESCE(m.composite_risk_score, 0)) AS avg_risk,
               sum(CASE WHEN m.mismatch_type = 'CIRCULAR_TRADE' THEN 1 ELSE 0 END) AS circular,
               sum(CASE WHEN m.mismatch_type = 'PHANTOM_INVOICE' THEN 1 ELSE 0 END) AS phantom
    """, {"gstin": gstin})
    if mm:
        r = mm[0]
        features["total_mismatches"] = float(r["total"])
        features["critical_mismatches"] = float(r["critical"])
        features["high_mismatches"] = float(r["high"])
        total_inv = features["total_invoices_issued"] + features["total_invoices_received"]
        features["mismatch_rate"] = float(r["total"]) / max(total_inv, 1)
        features["total_itc_at_risk"] = float(r["itc_risk"])
        features["avg_risk_score"] = float(r["avg_risk"] or 0)
        features["has_circular_trade"] = 1.0 if r["circular"] > 0 else 0.0
        features["has_phantom_invoice"] = 1.0 if r["phantom"] > 0 else 0.0
    else:
        for k in ["total_mismatches", "critical_mismatches", "high_mismatches",
                   "mismatch_rate", "total_itc_at_risk", "avg_risk_score",
                   "has_circular_trade", "has_phantom_invoice"]:
            features[k] = 0.0

    # Network features from stored properties
    net = execute_query("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        RETURN COALESCE(g.pagerank, 0) AS pagerank,
               COALESCE(g.degree_centrality, 0) AS degree,
               COALESCE(g.betweenness_centrality, 0) AS betweenness,
               COALESCE(g.clustering_coefficient, 0) AS clustering,
               COALESCE(g.community_id, -1) AS community
    """, {"gstin": gstin})
    if net:
        r = net[0]
        features["pagerank"] = float(r["pagerank"])
        features["degree_centrality"] = float(r["degree"])
        features["betweenness_centrality"] = float(r["betweenness"])
        features["clustering_coefficient"] = float(r["clustering"])
        features["community_id"] = float(r["community"])
    else:
        for k in ["pagerank", "degree_centrality", "betweenness_centrality",
                   "clustering_coefficient"]:
            features[k] = 0.0
        features["community_id"] = -1.0

    # In/out degree
    deg = execute_query("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        OPTIONAL MATCH (g)-[out:TRANSACTS_WITH]->()
        OPTIONAL MATCH ()-[inc:TRANSACTS_WITH]->(g)
        RETURN count(DISTINCT out) AS out_deg, count(DISTINCT inc) AS in_deg
    """, {"gstin": gstin})
    if deg:
        features["in_degree"] = float(deg[0]["in_deg"])
        features["out_degree"] = float(deg[0]["out_deg"])
    else:
        features["in_degree"] = 0.0
        features["out_degree"] = 0.0

    # Filing compliance
    filing = execute_query("""
        MATCH (g:GSTIN {gstin_number: $gstin})-[:FILED_RETURN]->(r:Return)
        WITH r.return_type AS rtype,
             count(r) AS filed,
             sum(CASE WHEN r.filing_status = 'filed_late' THEN 1 ELSE 0 END) AS late
        RETURN rtype, filed, late
    """, {"gstin": gstin})
    gstr1_filed = 0
    gstr3b_filed = 0
    total_late = 0
    for r in filing:
        if r["rtype"] == "GSTR1":
            gstr1_filed = r["filed"]
        elif r["rtype"] == "GSTR3B":
            gstr3b_filed = r["filed"]
        total_late += r["late"]

    features["gstr1_filing_rate"] = min(gstr1_filed / 12.0, 1.0)
    features["gstr3b_filing_rate"] = min(gstr3b_filed / 12.0, 1.0)
    features["late_filing_count"] = float(total_late)
    features["avg_filing_delay_days"] = 0.0  # Would need actual dates

    # Financial patterns
    itc_ratio = features["total_value_received"] / max(features["total_value_issued"], 1)
    features["itc_to_output_ratio"] = min(itc_ratio, 5.0)
    features["value_concentration_index"] = (
        features["max_invoice_value"] / max(features["total_value_issued"], 1)
    )
    features["month_over_month_growth"] = 0.0  # Simplified

    return features


def extract_all_features() -> tuple:
    """Extract features for ALL GSTINs. Returns (gstin_list, feature_matrix, feature_names)."""
    gstins_result = execute_query("MATCH (g:GSTIN {status: 'active'}) RETURN g.gstin_number AS gstin")
    gstins = [r["gstin"] for r in gstins_result]

    logger.info(f"Extracting features for {len(gstins)} GSTINs...")
    feature_matrix = []
    valid_gstins = []

    for gstin in gstins:
        try:
            features = extract_features(gstin)
            row = [features.get(name, 0.0) for name in FEATURE_NAMES]
            feature_matrix.append(row)
            valid_gstins.append(gstin)
        except Exception as e:
            logger.warning(f"Feature extraction failed for {gstin}: {e}")

    return valid_gstins, np.array(feature_matrix), FEATURE_NAMES
