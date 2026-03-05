"""
Audit Trail API — generate and retrieve explainable audit reports.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from app.database import execute_query as eq
from typing import Optional

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/findings")
async def get_findings(
    gstin: str = Query(...),
    return_period: Optional[str] = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Retrieve audit findings for a GSTIN (period optional)."""
    findings = eq("""
        MATCH (m:Mismatch)
        WHERE (m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin)
        OPTIONAL MATCH (m)-[:INVOLVES]->(inv:Invoice)
        OPTIONAL MATCH (inv)<-[:ISSUED_INVOICE]-(seller:GSTIN)
        OPTIONAL MATCH (tp:Taxpayer)-[:HAS_GSTIN]->(seller)
        RETURN m,
               inv.invoice_number AS invoice_number,
               inv.taxable_value AS invoice_value,
               inv.invoice_date AS invoice_date,
               seller.gstin_number AS seller_gstin,
               COALESCE(tp.legal_name, seller.trade_name, 'Unknown') AS seller_name
        ORDER BY m.composite_risk_score DESC
        SKIP $skip LIMIT $limit
    """, {
        "gstin": gstin,
        "skip": (page - 1) * page_size,
        "limit": page_size,
    })

    total = eq("""
        MATCH (m:Mismatch)
        WHERE (m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin)
        RETURN count(m) AS cnt
    """, {"gstin": gstin})

    result = []
    for f in findings:
        raw = dict(f["m"]) if f["m"] else {}
        result.append({
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
            "return_period": raw.get("return_period"),
            "invoice_value": raw.get("invoice_value") or f.get("invoice_value"),
            "status": raw.get("status"),
            "invoice_number": f.get("invoice_number"),
            "invoice_date": str(f.get("invoice_date", "")) if f.get("invoice_date") else None,
            "seller_name": f.get("seller_name"),
        })

    return {
        "findings": result,
        "total": total[0]["cnt"] if total else 0,
    }


@router.get("/report", response_class=HTMLResponse)
async def generate_report(
    gstin: str = Query(...),
    return_period: str = Query(""),
):
    """Generate a full HTML audit report."""
    findings_data = eq("""
        MATCH (m:Mismatch)
        WHERE (m.gstin = $gstin OR m.buyer_gstin = $gstin OR m.seller_gstin = $gstin)
        OPTIONAL MATCH (m)-[:INVOLVES]->(inv:Invoice)
        OPTIONAL MATCH (inv)<-[:ISSUED_INVOICE]-(seller:GSTIN)
        OPTIONAL MATCH (tp:Taxpayer)-[:HAS_GSTIN]->(seller)
        RETURN m, inv, seller.gstin_number AS seller_gstin,
               COALESCE(tp.legal_name, 'Unknown') AS seller_name
        ORDER BY m.composite_risk_score DESC
    """, {"gstin": gstin})

    taxpayer = eq("""
        MATCH (g:GSTIN {gstin_number: $gstin})
        OPTIONAL MATCH (tp:Taxpayer)-[:HAS_GSTIN]->(g)
        RETURN COALESCE(tp.legal_name, 'Unknown') AS legal_name,
               tp.pan AS pan,
               g.state_code AS state,
               g.registration_type AS reg_type,
               g.risk_score AS risk_score,
               g.risk_label AS risk_label
    """, {"gstin": gstin})

    tp = dict(taxpayer[0]) if taxpayer else {}
    findings = []
    total_risk = 0.0
    sev_count = {}
    for row in findings_data:
        f = dict(row["m"]) if row["m"] else {}
        if row.get("inv"):
            f["invoice_number"] = dict(row["inv"]).get("invoice_number")
        f["seller_name"] = row.get("seller_name", "Unknown")
        total_risk += float(f.get("itc_at_risk", 0) or 0)
        s = f.get("severity", "UNKNOWN")
        sev_count[s] = sev_count.get(s, 0) + 1
        findings.append(f)

    from datetime import datetime
    now = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
    fmt = lambda v: f"₹{float(v or 0):,.2f}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>GST Audit Report — {gstin}</title>
<style>
body{{font-family:Inter,system-ui,sans-serif;margin:0;padding:40px;background:#f8fafc;color:#1e293b}}
.header{{background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff;padding:32px;border-radius:12px;margin-bottom:24px}}
.header h1{{margin:0;font-size:24px}} .header p{{margin:4px 0;opacity:.8;font-size:14px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.card h3{{margin-top:0;font-size:16px;color:#334155}} .badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700}}
.critical{{background:#fecaca;color:#991b1b}} .high{{background:#fed7aa;color:#c2410c}} .medium{{background:#fef08a;color:#a16207}} .low{{background:#bbf7d0;color:#166534}}
table{{width:100%;border-collapse:collapse;font-size:13px}} th{{text-align:left;padding:10px 12px;background:#f1f5f9;border-bottom:2px solid #e2e8f0;color:#64748b;text-transform:uppercase;font-size:11px}}
td{{padding:10px 12px;border-bottom:1px solid #f1f5f9}} tr:hover{{background:#f8fafc}}
.narrative{{background:#fef2f2;padding:12px 16px;border-radius:8px;font-size:13px;line-height:1.6;margin:8px 0;border-left:4px solid #ef4444}}
.kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}}
.kpi{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px;text-align:center}}
.kpi .value{{font-size:28px;font-weight:800;color:#1e293b}} .kpi .label{{font-size:12px;color:#64748b;text-transform:uppercase;margin-top:4px}}
.footer{{text-align:center;color:#94a3b8;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #e2e8f0}}
</style></head><body>
<div class='header'><h1>GST Compliance Audit Report</h1><p>GSTIN: {gstin} | Entity: {tp.get('legal_name','N/A')} | State: {tp.get('state','N/A')}</p>
<p>Risk Score: {float(tp.get('risk_score',0) or 0):.0f}% ({tp.get('risk_label','N/A').upper()}) | Generated: {now}</p></div>
<div class='kpi-row'>
<div class='kpi'><div class='value'>{len(findings)}</div><div class='label'>Total Findings</div></div>
<div class='kpi'><div class='value' style='color:#991b1b'>{sev_count.get('CRITICAL',0)+sev_count.get('HIGH',0)}</div><div class='label'>Critical/High</div></div>
<div class='kpi'><div class='value' style='color:#f59e0b'>{fmt(total_risk)}</div><div class='label'>ITC at Risk</div></div>
<div class='kpi'><div class='value'>{tp.get('reg_type','N/A')}</div><div class='label'>Registration</div></div>
</div>"""

    for i, f in enumerate(findings, 1):
        sev = f.get('severity', 'MEDIUM')
        html += f"""<div class='card'>
<h3>Finding #{i}: {f.get('mismatch_type','').replace('_',' ')} <span class='badge {sev.lower()}'>{sev}</span></h3>
<table><tr><td><strong>Mismatch ID:</strong> {f.get('mismatch_id','N/A')}</td><td><strong>Invoice:</strong> {f.get('invoice_number','N/A')}</td></tr>
<tr><td><strong>Buyer GSTIN:</strong> {f.get('buyer_gstin','N/A')}</td><td><strong>Seller:</strong> {f.get('seller_name','N/A')}</td></tr>
<tr><td><strong>ITC at Risk:</strong> {fmt(f.get('itc_at_risk',0))}</td><td><strong>Risk Score:</strong> {float(f.get('composite_risk_score',0) or 0):.0f}%</td></tr></table>"""
        if f.get('narrative'):
            html += f"<div class='narrative'>{f['narrative']}</div>"
        evidence = f.get('evidence_paths', [])
        if evidence and isinstance(evidence, list):
            html += "<p><strong>Evidence:</strong></p><ul>" + "".join(f"<li style='font-size:13px'>{e}</li>" for e in evidence) + "</ul>"
        actions = f.get('resolution_actions', [])
        if actions and isinstance(actions, list):
            html += "<p><strong>Resolution Actions:</strong></p><ul>" + "".join(f"<li style='font-size:13px'>{a}</li>" for a in actions) + "</ul>"
        refs = f.get('regulatory_references', [])
        if refs and isinstance(refs, list):
            html += "<p><strong>Regulatory References:</strong></p><ul>" + "".join(f"<li style='font-size:13px'>{r}</li>" for r in refs) + "</ul>"
        html += "</div>"

    html += f"<div class='footer'>GST Reconciliation Engine — Auto-generated Audit Report | {now}</div></body></html>"
    return HTMLResponse(content=html)


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
        OPTIONAL MATCH (tps:Taxpayer)-[:HAS_GSTIN]->(seller)
        OPTIONAL MATCH (tpb:Taxpayer)-[:HAS_GSTIN]->(buyer)
        RETURN m, inv, seller, buyer, irn, ret,
               COALESCE(tps.legal_name, 'Unknown') AS seller_name,
               COALESCE(tpb.legal_name, 'Unknown') AS buyer_name
    """, {"mid": mismatch_id})

    if not path:
        raise HTTPException(status_code=404, detail="Mismatch not found")

    row = path[0]
    return {
        "mismatch": dict(row["m"]) if row["m"] else None,
        "invoice": dict(row["inv"]) if row["inv"] else None,
        "seller": {**(dict(row["seller"]) if row["seller"] else {}), "name": row.get("seller_name")},
        "buyer": {**(dict(row["buyer"]) if row["buyer"] else {}), "name": row.get("buyer_name")},
        "irn": dict(row["irn"]) if row["irn"] else None,
        "return_filed": dict(row["ret"]) if row["ret"] else None,
    }
