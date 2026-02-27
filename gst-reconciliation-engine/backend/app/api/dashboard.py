"""
Dashboard API — aggregate stats, graph data, vendor scorecard.
"""

from fastapi import APIRouter, Query
from app.database import execute_query as eq

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(gstin: str = Query(...), return_period: str = Query(...)):
    """Return high-level stats for a GSTIN/period."""
    summary = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})-[:ISSUED_INVOICE]->(inv:Invoice)
        WHERE inv.invoice_date >= date($period_start)
        RETURN count(inv) AS total_invoices,
               sum(inv.taxable_value) AS total_taxable,
               sum(inv.total_tax) AS total_tax,
               sum(inv.total_value) AS total_value
    """, {"gstin": gstin, "period_start": _period_to_date(return_period)})

    mismatch_stats = eq("""
        MATCH (m:Mismatch {gstin: $gstin, return_period: $period})
        RETURN m.severity AS severity, count(m) AS cnt,
               sum(m.itc_at_risk) AS itc_risk
        ORDER BY severity
    """, {"gstin": gstin, "period": return_period})

    risk_score = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        RETURN g.risk_score AS risk_score,
               g.risk_label AS risk_label,
               g.pagerank AS pagerank
    """, {"gstin": gstin})

    return {
        "invoices": dict(summary[0]) if summary else {},
        "mismatches": [dict(r) for r in mismatch_stats],
        "risk": dict(risk_score[0]) if risk_score else {},
    }


@router.get("/graph")
async def graph_data(
    gstin: str = Query(...),
    depth: int = Query(2, ge=1, le=4),
):
    """Return knowledge graph neighbourhood for vis-network rendering."""
    result = eq("""
        MATCH path = (center:GSTIN {gstin_number: $gstin})-[*1..""" + str(depth) + """]->(n)
        UNWIND nodes(path) AS node
        UNWIND relationships(path) AS rel
        WITH collect(DISTINCT {
            id: elementId(node),
            label: coalesce(node.gstin_number, node.invoice_number, node.irn_number, labels(node)[0]),
            type: labels(node)[0],
            properties: properties(node)
        }) AS nodes,
        collect(DISTINCT {
            from: elementId(startNode(rel)),
            to: elementId(endNode(rel)),
            label: type(rel)
        }) AS edges
        RETURN nodes, edges
    """, {"gstin": gstin})

    if result:
        return {"nodes": result[0]["nodes"], "edges": result[0]["edges"]}
    return {"nodes": [], "edges": []}


@router.get("/vendor-scorecard")
async def vendor_scorecard(
    gstin: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List vendors with risk scores for a buyer GSTIN."""
    vendors = eq("""
        MATCH (buyer:GSTIN {gstin_number: $gstin})<-[:ISSUED_INVOICE]-(inv:Invoice)<-[:ISSUED_INVOICE]-(seller:GSTIN)
        WITH seller, count(inv) AS invoice_count,
             sum(inv.total_value) AS total_value,
             seller.risk_score AS risk_score,
             seller.risk_label AS risk_label
        RETURN seller.gstin_number AS gstin,
               seller.trade_name AS name,
               invoice_count, total_value,
               COALESCE(risk_score,0) AS risk_score,
               COALESCE(risk_label,'unknown') AS risk_label
        ORDER BY risk_score DESC
        SKIP $skip LIMIT $limit
    """, {"gstin": gstin, "skip": (page - 1) * page_size, "limit": page_size})

    return {"vendors": [dict(v) for v in vendors], "page": page}


@router.get("/trends")
async def mismatch_trends(gstin: str = Query(...)):
    """Monthly mismatch trends."""
    trends = eq("""
        MATCH (m:Mismatch {gstin: $gstin})
        RETURN m.return_period AS period,
               count(m) AS mismatch_count,
               sum(m.itc_at_risk) AS itc_at_risk,
               avg(m.composite_risk_score) AS avg_risk
        ORDER BY period
    """, {"gstin": gstin})
    return {"trends": [dict(t) for t in trends]}


def _period_to_date(period: str) -> str:
    """Convert MMYYYY to ISO date string."""
    month = period[:2]
    year = period[2:]
    return f"{year}-{month}-01"
