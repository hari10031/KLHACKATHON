"""
Audit Trail API — generate and retrieve explainable audit reports.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from app.database import execute_query as eq

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/findings")
async def get_findings(
    gstin: str = Query(...),
    return_period: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Retrieve audit findings for a GSTIN/period."""
    findings = eq("""
        MATCH (m:Mismatch {gstin: $gstin, return_period: $period})
        RETURN m
        ORDER BY m.composite_risk_score DESC
        SKIP $skip LIMIT $limit
    """, {
        "gstin": gstin,
        "period": return_period,
        "skip": (page - 1) * page_size,
        "limit": page_size,
    })
    return {"findings": [dict(f["m"]) for f in findings]}


@router.get("/report", response_class=HTMLResponse)
async def generate_report(
    gstin: str = Query(...),
    return_period: str = Query(...),
):
    """Generate a full HTML audit report."""
    from app.audit.trail_generator import AuditTrailGenerator

    generator = AuditTrailGenerator()
    report = generator.generate_report(gstin, return_period)
    return HTMLResponse(content=report)


@router.get("/traversal")
async def traversal_path(mismatch_id: str = Query(...)):
    """Return the knowledge-graph traversal path that led to a finding."""
    path = eq("""
        MATCH (m:Mismatch {mismatch_id: $mid})
        OPTIONAL MATCH (m)-[:INVOLVES]->(inv:Invoice)
        OPTIONAL MATCH (inv)<-[:ISSUED_INVOICE]-(seller:GSTIN)
        OPTIONAL MATCH (inv)-[:RECEIVED_INVOICE]->(buyer:GSTIN)
        OPTIONAL MATCH (inv)-[:HAS_IRN]->(irn:IRN)
        OPTIONAL MATCH (inv)-[:REPORTED_IN]->(ret:Return)
        RETURN m, inv, seller, buyer, irn, ret
    """, {"mid": mismatch_id})

    if not path:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    row = path[0]
    return {
        "mismatch": dict(row["m"]) if row["m"] else None,
        "invoice": dict(row["inv"]) if row["inv"] else None,
        "seller": dict(row["seller"]) if row["seller"] else None,
        "buyer": dict(row["buyer"]) if row["buyer"] else None,
        "irn": dict(row["irn"]) if row["irn"] else None,
        "return_filed": dict(row["ret"]) if row["ret"] else None,
    }
