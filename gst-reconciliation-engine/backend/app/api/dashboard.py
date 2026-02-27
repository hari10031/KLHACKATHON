"""
Dashboard API — aggregate stats, graph data, vendor scorecard.
"""

from fastapi import APIRouter, Query
from app.database import execute_query as eq

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(gstin: str = Query(...), return_period: str = Query("")):
    """Return high-level stats for a GSTIN/period."""
    summary = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})-[:ISSUED_INVOICE|RECEIVED_INVOICE]-(inv:Invoice)
        OPTIONAL MATCH (tp:Taxpayer)-[:HAS_GSTIN]->(g)
        RETURN count(DISTINCT inv) AS total_invoices,
               sum(inv.taxable_value) AS total_taxable,
               sum(inv.total_tax) AS total_tax,
               sum(inv.total_value) AS total_value,
               COALESCE(tp.legal_name, 'Unknown') AS entity_name
    """, {"gstin": gstin})

    mismatch_stats = eq("""
        MATCH (m:Mismatch)
        WHERE m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin
        RETURN m.severity AS severity, count(m) AS cnt,
               sum(m.itc_at_risk) AS itc_risk
        ORDER BY severity
    """, {"gstin": gstin})

    mismatch_types = eq("""
        MATCH (m:Mismatch)
        WHERE m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin
        RETURN m.mismatch_type AS type, count(m) AS cnt
        ORDER BY cnt DESC
    """, {"gstin": gstin})

    risk_score = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        RETURN g.risk_score AS risk_score,
               g.risk_label AS risk_label,
               g.pagerank AS pagerank,
               g.degree_centrality AS degree,
               g.betweenness_centrality AS betweenness,
               g.community_id AS community
    """, {"gstin": gstin})

    top_mismatches = eq("""
        MATCH (m:Mismatch)
        WHERE m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin
        RETURN m.mismatch_id AS id, m.mismatch_type AS type,
               m.severity AS severity, m.itc_at_risk AS itc_risk,
               m.description AS description, m.narrative AS narrative,
               m.composite_risk_score AS risk_score, m.status AS status
        ORDER BY m.composite_risk_score DESC
        LIMIT 5
    """, {"gstin": gstin})

    vendor_count = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})-[:TRANSACTS_WITH]-(v:GSTIN)
        WHERE v.gstin_number <> $gstin
        RETURN count(v) AS cnt
    """, {"gstin": gstin})

    return {
        "invoices": dict(summary[0]) if summary else {},
        "mismatches": [dict(r) for r in mismatch_stats],
        "mismatch_types": [dict(r) for r in mismatch_types],
        "risk": dict(risk_score[0]) if risk_score else {},
        "top_mismatches": [dict(r) for r in top_mismatches],
        "vendor_count": vendor_count[0]["cnt"] if vendor_count else 0,
    }


@router.get("/graph")
async def graph_data(
    gstin: str = Query(...),
    depth: int = Query(2, ge=1, le=4),
):
    """Return knowledge graph neighbourhood for vis-network rendering."""
    # Use bidirectional traversal to capture both outgoing and incoming edges
    result = eq("""
        MATCH path = (center:GSTIN {gstin_number: $gstin})-[*1..""" + str(depth) + """]-(n)
        UNWIND nodes(path) AS node
        UNWIND relationships(path) AS rel
        WITH collect(DISTINCT {
            id: elementId(node),
            label: coalesce(node.gstin_number, node.invoice_number, node.irn_number,
                   node.mismatch_id,
                   CASE WHEN labels(node)[0] = 'Return' THEN node.return_type ELSE labels(node)[0] END),
            type: CASE WHEN labels(node)[0] = 'Return' THEN
                    CASE node.return_type
                        WHEN 'GSTR1' THEN 'GSTR-1'
                        WHEN 'GSTR2B' THEN 'GSTR-2B'
                        WHEN 'GSTR3B' THEN 'GSTR-3B'
                        ELSE 'Return'
                    END
                  WHEN labels(node)[0] = 'Mismatch' THEN 'Mismatch'
                  ELSE labels(node)[0] END,
            properties: properties(node)
        }) AS nodes,
        collect(DISTINCT {
            from: elementId(startNode(rel)),
            to: elementId(endNode(rel)),
            label: type(rel)
        }) AS edges
        RETURN nodes, edges
    """, {"gstin": gstin})

    nodes = result[0]["nodes"] if result else []
    edges = result[0]["edges"] if result else []

    existing_ids = {n["id"] for n in nodes}
    existing_edges = {(e["from"], e["to"], e["label"]) for e in edges}

    # ── Ensure all Mismatch nodes for this GSTIN are included ──
    mismatch_result = eq("""
        MATCH (m:Mismatch)
        WHERE m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin
        OPTIONAL MATCH (m)-[r]->(target)
        RETURN elementId(m) AS m_id,
               COALESCE(m.mismatch_id, 'Mismatch') AS m_label,
               properties(m) AS m_props,
               elementId(target) AS target_id,
               type(r) AS rel_type
    """, {"gstin": gstin})

    # Get the center GSTIN node id
    center = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        RETURN elementId(g) AS id
    """, {"gstin": gstin})
    center_id = center[0]["id"] if center else None

    for row in mismatch_result:
        # Add mismatch node if not already present
        if row["m_id"] not in existing_ids:
            nodes.append({
                "id": row["m_id"],
                "label": row["m_label"],
                "type": "Mismatch",
                "properties": row["m_props"],
            })
            existing_ids.add(row["m_id"])
        # Add edges from mismatch to targets
        if row["target_id"] and row["target_id"] in existing_ids:
            edge_key = (row["m_id"], row["target_id"], row["rel_type"])
            if edge_key not in existing_edges:
                edges.append({
                    "from": row["m_id"],
                    "to": row["target_id"],
                    "label": row["rel_type"] or "DETECTED_FOR",
                })
                existing_edges.add(edge_key)
        # Always connect mismatch to center GSTIN if not already connected
        if center_id and row["m_id"] != center_id:
            edge_key = (row["m_id"], center_id, "DETECTED_FOR")
            if edge_key not in existing_edges:
                edges.append({
                    "from": row["m_id"],
                    "to": center_id,
                    "label": "DETECTED_FOR",
                })
                existing_edges.add(edge_key)

    # ── Detect circular trade paths using existing Mismatch data ──
    circular_edges = set()
    circular_nodes = set()
    try:
        # Find GSTIN pairs involved in CIRCULAR_TRADE mismatches
        circ_mismatches = eq("""
            MATCH (m:Mismatch {mismatch_type: 'CIRCULAR_TRADE'})
            OPTIONAL MATCH (s:GSTIN {gstin_number: m.seller_gstin})
            OPTIONAL MATCH (b:GSTIN {gstin_number: m.buyer_gstin})
            OPTIONAL MATCH (g:GSTIN {gstin_number: m.gstin})
            RETURN elementId(s) AS seller_id, elementId(b) AS buyer_id,
                   elementId(g) AS gstin_id,
                   m.seller_gstin AS seller_gstin, m.buyer_gstin AS buyer_gstin,
                   m.gstin AS main_gstin
        """, {})
        for row in circ_mismatches:
            if row.get("seller_id"):
                circular_nodes.add(row["seller_id"])
            if row.get("buyer_id"):
                circular_nodes.add(row["buyer_id"])
            if row.get("gstin_id"):
                circular_nodes.add(row["gstin_id"])
            if row.get("seller_id") and row.get("buyer_id"):
                circular_edges.add((row["seller_id"], row["buyer_id"]))
                circular_edges.add((row["buyer_id"], row["seller_id"]))
        # Also find all TRANSACTS_WITH edges between circular nodes (only if small set)
        if circular_nodes and len(circular_nodes) <= 20:
            circ_txns = eq("""
                MATCH (a:GSTIN)-[r:TRANSACTS_WITH]->(b:GSTIN)
                WHERE elementId(a) IN $cids AND elementId(b) IN $cids
                RETURN elementId(a) AS from_id, elementId(b) AS to_id
            """, {"cids": list(circular_nodes)})
            for row in circ_txns:
                circular_edges.add((row["from_id"], row["to_id"]))
    except Exception:
        pass

    # Mark edges that are part of circular trade
    for edge in edges:
        if (edge["from"], edge["to"]) in circular_edges or (edge["to"], edge["from"]) in circular_edges:
            edge["circular"] = True
        if edge.get("label") == "TRANSACTS_WITH" and (
            (edge["from"], edge["to"]) in circular_edges or
            (edge["to"], edge["from"]) in circular_edges
        ):
            edge["circular"] = True

    # Mark nodes in circular trade
    for node in nodes:
        if node["id"] in circular_nodes:
            node["in_circular_trade"] = True

    return {
        "nodes": nodes,
        "edges": edges,
        "circular_trade_count": len(circular_nodes),
    }


@router.get("/vendor-scorecard")
async def vendor_scorecard(
    gstin: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List vendors with risk scores for a buyer GSTIN."""
    vendors = eq("""
        MATCH (buyer:GSTIN {gstin_number: $gstin})-[:TRANSACTS_WITH]-(seller:GSTIN)
        WHERE seller.gstin_number <> $gstin
        OPTIONAL MATCH (tp:Taxpayer)-[:HAS_GSTIN]->(seller)
        OPTIONAL MATCH (seller)-[:ISSUED_INVOICE]->(inv:Invoice)
        WITH seller, tp, count(inv) AS invoice_count,
             sum(inv.total_value) AS total_value,
             seller.risk_score AS risk_score,
             seller.risk_label AS risk_label
        RETURN seller.gstin_number AS gstin,
               COALESCE(tp.legal_name, tp.trade_name, seller.trade_name, 'Unknown') AS name,
               invoice_count, total_value,
               COALESCE(risk_score,0) AS risk_score,
               COALESCE(risk_label,'unknown') AS risk_label,
               seller.pagerank AS pagerank,
               seller.degree_centrality AS degree,
               seller.betweenness_centrality AS betweenness,
               seller.community_id AS community
        ORDER BY risk_score DESC
        SKIP $skip LIMIT $limit
    """, {"gstin": gstin, "skip": (page - 1) * page_size, "limit": page_size})

    total = eq("""
        MATCH (buyer:GSTIN {gstin_number: $gstin})-[:TRANSACTS_WITH]-(seller:GSTIN)
        WHERE seller.gstin_number <> $gstin
        RETURN count(seller) AS cnt
    """, {"gstin": gstin})

    return {
        "vendors": [dict(v) for v in vendors],
        "total": total[0]["cnt"] if total else 0,
        "page": page,
    }


@router.get("/trends")
async def mismatch_trends(gstin: str = Query(...)):
    """Monthly mismatch trends."""
    trends = eq("""
        MATCH (m:Mismatch)
        WHERE m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin
        RETURN m.return_period AS period,
               count(m) AS mismatch_count,
               sum(m.itc_at_risk) AS itc_at_risk,
               avg(m.composite_risk_score) AS avg_risk
        ORDER BY period
    """, {"gstin": gstin})
    return {"trends": [dict(t) for t in trends]}
