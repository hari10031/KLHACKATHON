"""
Reconciliation API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.engine.reconciliation import ReconciliationEngine
from app.models.mismatch import ReconciliationSummary, Severity

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])
engine = ReconciliationEngine()


@router.post("/run", response_model=ReconciliationSummary)
async def run_reconciliation(
    gstin: str = Query(..., description="GSTIN to reconcile"),
    return_period: str = Query(..., description="Return period (MMYYYY)"),
    level: Optional[int] = Query(None, ge=1, le=4, description="Run only a specific level (1-4), or all if omitted"),
):
    """Run 4-level reconciliation for a GSTIN and period."""
    try:
        if level == 1:
            return engine.run_level1_only(gstin, return_period)
        return engine.run_full_reconciliation(gstin, return_period)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gstins")
async def list_gstins():
    """Get all active GSTINs."""
    return {"gstins": engine.get_all_gstins()}


@router.get("/periods")
async def list_periods():
    """Get all available return periods."""
    return {"periods": engine.get_return_periods()}


@router.get("/mismatches")
async def get_mismatches(
    gstin: str = Query(...),
    return_period: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    mismatch_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Query stored mismatches with filters."""
    from app.database import execute_query as eq

    where_clauses = ["(m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin)"]
    params = {"gstin": gstin}

    if return_period:
        where_clauses.append("m.return_period = $period")
        params["period"] = return_period

    if severity:
        where_clauses.append("m.severity = $severity")
        params["severity"] = severity
    if mismatch_type:
        where_clauses.append("m.mismatch_type = $mtype")
        params["mtype"] = mismatch_type

    where = " AND ".join(where_clauses)
    params["skip"] = (page - 1) * page_size
    params["limit"] = page_size

    query = f"""
        MATCH (m:Mismatch)
        WHERE {where}
        OPTIONAL MATCH (seller:GSTIN {{gstin_number: m.seller_gstin}})
        OPTIONAL MATCH (tp_s:Taxpayer)-[:HAS_GSTIN]->(seller)
        OPTIONAL MATCH (buyer:GSTIN {{gstin_number: m.buyer_gstin}})
        OPTIONAL MATCH (tp_b:Taxpayer)-[:HAS_GSTIN]->(buyer)
        RETURN m,
               COALESCE(tp_s.legal_name, seller.trade_name, null) AS seller_name,
               COALESCE(tp_b.legal_name, buyer.trade_name, null) AS buyer_name
        ORDER BY m.composite_risk_score DESC
        SKIP $skip LIMIT $limit
    """
    count_query = f"MATCH (m:Mismatch) WHERE {where} RETURN count(m) AS total"

    results = eq(query, params)
    total = eq(count_query, params)

    # Get severity counts + type list across ALL mismatches (not just current page)
    base_where_clauses = ["(m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin)"]
    base_params = {"gstin": gstin}
    if return_period:
        base_where_clauses.append("m.return_period = $period")
        base_params["period"] = return_period
    base_where = " AND ".join(base_where_clauses)

    sev_summary = eq(f"""
        MATCH (m:Mismatch) WHERE {base_where}
        RETURN m.severity AS severity, count(m) AS cnt
    """, base_params)

    type_summary = eq(f"""
        MATCH (m:Mismatch) WHERE {base_where}
        WITH m.mismatch_type AS mtype WHERE mtype IS NOT NULL
        RETURN DISTINCT mtype ORDER BY mtype
    """, base_params)

    sev_counts = {}
    for s in sev_summary:
        if s.get("severity"):
            sev_counts[s["severity"]] = s["cnt"]

    all_types = [t["mtype"] for t in type_summary if t.get("mtype")]

    mismatches = []
    for r in results:
        raw = dict(r["m"])
        mismatches.append({
            "id": raw.get("mismatch_id"),
            "type": raw.get("mismatch_type"),
            "severity": raw.get("severity"),
            "description": raw.get("description"),
            "narrative": raw.get("narrative"),
            "itc_risk": raw.get("itc_at_risk"),
            "tax_difference": raw.get("tax_difference"),
            "risk_score": raw.get("composite_risk_score"),
            "evidence_path": "\n".join(raw.get("evidence_paths") or []) if isinstance(raw.get("evidence_paths"), list) else (raw.get("evidence_paths") or ""),
            "resolution_actions": "\n".join(raw.get("resolution_actions") or []) if isinstance(raw.get("resolution_actions"), list) else (raw.get("resolution_actions") or ""),
            "regulatory_ref": "\n".join(raw.get("regulatory_references") or []) if isinstance(raw.get("regulatory_references"), list) else (raw.get("regulatory_references") or ""),
            "buyer_gstin": raw.get("buyer_gstin"),
            "seller_gstin": raw.get("seller_gstin"),
            "buyer_name": r.get("buyer_name"),
            "seller_name": r.get("seller_name"),
            "return_period": raw.get("return_period"),
            "invoice_value": raw.get("invoice_value"),
            "status": raw.get("status"),
        })

    return {
        "mismatches": mismatches,
        "total": total[0]["total"] if total else 0,
        "page": page,
        "page_size": page_size,
        "severity_counts": sev_counts,
        "all_types": all_types,
    }
