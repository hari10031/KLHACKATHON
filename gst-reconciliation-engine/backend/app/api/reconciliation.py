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
    return_period: str = Query(...),
    severity: Optional[str] = Query(None),
    mismatch_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Query stored mismatches with filters."""
    from app.database import execute_query as eq

    where_clauses = ["m.gstin = $gstin", "m.return_period = $period"]
    params = {"gstin": gstin, "period": return_period}

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
        RETURN m
        ORDER BY m.composite_risk_score DESC
        SKIP $skip LIMIT $limit
    """
    count_query = f"MATCH (m:Mismatch) WHERE {where} RETURN count(m) AS total"

    results = eq(query, params)
    total = eq(count_query, params)

    return {
        "mismatches": [dict(r["m"]) for r in results],
        "total": total[0]["total"] if total else 0,
        "page": page,
        "page_size": page_size,
    }
