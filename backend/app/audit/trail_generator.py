"""
Explainable Audit Trail Generator.

Generates human-readable audit reports with:
  - Natural-language narrative per finding
  - Knowledge-graph traversal path
  - Financial impact breakdown
  - Regulatory references
  - Resolution actions
"""

from typing import List, Dict
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from loguru import logger

from app.database import execute_query


TEMPLATE_DIR = Path(__file__).parent / "templates"


class AuditTrailGenerator:
    """Produces HTML/text audit reports for a GSTIN and period."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        self.env.filters["inr"] = lambda v: f"₹{v:,.2f}" if v else "₹0.00"
        self.env.filters["pct"] = lambda v: f"{(v or 0) * 100:.1f}%"

    def generate_report(self, gstin: str, return_period: str) -> str:
        """Generate a full HTML audit report."""
        findings = self._fetch_findings(gstin, return_period)
        taxpayer = self._fetch_taxpayer(gstin)
        summary = self._compute_summary(findings)

        template = self.env.get_template("audit_report.html")
        html = template.render(
            gstin=gstin,
            return_period=return_period,
            taxpayer=taxpayer,
            findings=findings,
            summary=summary,
            generated_at=datetime.utcnow().strftime("%d %b %Y %H:%M UTC"),
        )
        return html

    def generate_finding_narrative(self, finding: Dict) -> str:
        """Generate a natural-language explanation for a single finding."""
        mtype = finding.get("mismatch_type", "")
        narratives = {
            "INVOICE_MISSING": (
                f"Invoice {finding.get('invoice_number', 'N/A')} reported by "
                f"{finding.get('seller_gstin', 'seller')} in GSTR-1 was NOT found in "
                f"the buyer's GSTR-2B / purchase register. This suggests the invoice may be "
                f"phantom or the buyer has not yet recorded it. "
                f"ITC of {self._fmt_inr(finding.get('itc_at_risk', 0))} is at risk."
            ),
            "VALUE_MISMATCH": (
                f"Invoice {finding.get('invoice_number', 'N/A')} shows a taxable value "
                f"difference between seller's GSTR-1 ({self._fmt_inr(finding.get('seller_value', 0))}) "
                f"and buyer's records ({self._fmt_inr(finding.get('buyer_value', 0))}). "
                f"Difference: {self._fmt_inr(abs((finding.get('seller_value', 0) or 0) - (finding.get('buyer_value', 0) or 0)))}."
            ),
            "TAX_RATE_MISMATCH": (
                f"Invoice {finding.get('invoice_number', 'N/A')} has conflicting tax rates: "
                f"seller applied {finding.get('seller_rate', 'N/A')}% while buyer recorded "
                f"{finding.get('buyer_rate', 'N/A')}%. This may indicate HSN misclassification."
            ),
            "CIRCULAR_TRADE": (
                f"A circular trading pattern has been detected involving "
                f"{finding.get('participants', 'multiple entities')}. "
                f"Total value circulated: {self._fmt_inr(finding.get('total_value', 0))} "
                f"with a value inflation ratio of {finding.get('inflation_ratio', 'N/A')}x. "
                f"This warrants immediate investigation for potential GST fraud."
            ),
            "PHANTOM_INVOICE": (
                f"Invoice {finding.get('invoice_number', 'N/A')} appears to be a phantom invoice — "
                f"no corresponding e-Way Bill, IRN, or bank transaction was found in the knowledge graph. "
                f"ITC claimed: {self._fmt_inr(finding.get('itc_at_risk', 0))}."
            ),
            "ITC_OVERCLAIM": (
                f"ITC overclaim detected for {finding.get('buyer_gstin', 'buyer')}: "
                f"claimed {self._fmt_inr(finding.get('claimed_amount', 0))} but eligible amount "
                f"is {self._fmt_inr(finding.get('eligible_amount', 0))}. "
                f"Excess: {self._fmt_inr(finding.get('itc_at_risk', 0))}."
            ),
        }
        return narratives.get(mtype, f"Mismatch of type {mtype} detected. Review required.")

    def _fetch_findings(self, gstin: str, return_period: str) -> List[Dict]:
        """Fetch all mismatches with traversal data."""
        results = execute_query("""
            MATCH (m:Mismatch {gstin: $gstin, return_period: $period})
            OPTIONAL MATCH (m)-[:INVOLVES]->(inv:Invoice)
            OPTIONAL MATCH (inv)<-[:ISSUED_INVOICE]-(seller:GSTIN)
            RETURN m, inv, seller
            ORDER BY m.composite_risk_score DESC
        """, {"gstin": gstin, "period": return_period})

        findings = []
        for row in results:
            f = dict(row["m"]) if row["m"] else {}
            if row["inv"]:
                f["invoice_number"] = row["inv"].get("invoice_number")
                f["invoice_date"] = str(row["inv"].get("invoice_date", ""))
            if row["seller"]:
                f["seller_gstin"] = row["seller"].get("gstin_number")
                f["seller_name"] = row["seller"].get("trade_name")
            f["narrative"] = self.generate_finding_narrative(f)
            findings.append(f)
        return findings

    def _fetch_taxpayer(self, gstin: str) -> Dict:
        result = execute_query("""
            MATCH (g:GSTIN {gstin_number: $gstin})<-[:HAS_GSTIN]-(t:Taxpayer)
            RETURN t.legal_name AS legal_name, t.pan AS pan,
                   g.trade_name AS trade_name, g.state AS state,
                   g.registration_type AS reg_type
        """, {"gstin": gstin})
        return dict(result[0]) if result else {}

    def _compute_summary(self, findings: List[Dict]) -> Dict:
        total = len(findings)
        by_severity = {}
        by_type = {}
        total_risk = 0.0

        for f in findings:
            sev = f.get("severity", "UNKNOWN")
            by_severity[sev] = by_severity.get(sev, 0) + 1
            mt = f.get("mismatch_type", "UNKNOWN")
            by_type[mt] = by_type.get(mt, 0) + 1
            total_risk += float(f.get("itc_at_risk", 0) or 0)

        return {
            "total_findings": total,
            "by_severity": by_severity,
            "by_type": by_type,
            "total_itc_at_risk": total_risk,
            "critical_count": by_severity.get("CRITICAL", 0),
            "high_count": by_severity.get("HIGH", 0),
        }

    @staticmethod
    def _fmt_inr(value) -> str:
        try:
            return f"₹{float(value):,.2f}"
        except (TypeError, ValueError):
            return "₹0.00"
