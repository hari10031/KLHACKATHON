"""
Risk & ML prediction API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from app.database import execute_query as eq

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/vendor/{gstin}")
async def vendor_risk(gstin: str):
    """Get risk prediction for a single vendor GSTIN."""
    result = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        OPTIONAL MATCH (g)-[:ISSUED_INVOICE]->(inv:Invoice)
        WITH g, count(inv) AS invoice_count,
             sum(inv.total_value) AS total_value
        RETURN g.gstin_number AS gstin,
               g.trade_name AS name,
               g.risk_score AS risk_score,
               g.risk_label AS risk_label,
               g.pagerank AS pagerank,
               g.degree_centrality AS degree,
               g.betweenness_centrality AS betweenness,
               g.community_id AS community,
               invoice_count, total_value
    """, {"gstin": gstin})

    if not result:
        raise HTTPException(status_code=404, detail="GSTIN not found")
    return dict(result[0])


@router.get("/heatmap")
async def risk_heatmap():
    """Risk distribution across all GSTINs for heatmap visualisation."""
    data = eq("""
        MATCH (g:GSTIN)
        WHERE g.risk_score IS NOT NULL
        RETURN g.gstin_number AS gstin,
               g.trade_name AS name,
               g.state AS state,
               g.risk_score AS risk_score,
               g.risk_label AS label,
               g.community_id AS community
        ORDER BY risk_score DESC
    """)
    return {"vendors": [dict(d) for d in data]}


@router.get("/communities")
async def risk_communities():
    """Group GSTINs by detected communities."""
    data = eq("""
        MATCH (g:GSTIN)
        WHERE g.community_id IS NOT NULL
        RETURN g.community_id AS community,
               collect({
                   gstin: g.gstin_number,
                   name: g.trade_name,
                   risk_score: g.risk_score
               }) AS members,
               avg(g.risk_score) AS avg_risk
        ORDER BY avg_risk DESC
    """)
    return {"communities": [dict(d) for d in data]}


@router.post("/predict")
async def predict_risk(gstin: str = Query(...)):
    """Run ML model prediction for a vendor."""
    try:
        from app.ml.model import VendorRiskModel
        model = VendorRiskModel()
        prediction = model.predict_single(gstin)
        return prediction
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Model not trained yet. Run /risk/train first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def train_model():
    """Train the XGBoost vendor risk model."""
    from app.ml.model import VendorRiskModel
    model = VendorRiskModel()
    metrics = model.train()
    return {"status": "trained", "metrics": metrics}
