"""
Post-ingestion data quality validator.
Checks node counts, relationship integrity, and graph statistics.
"""

from typing import Dict, List
from loguru import logger
from app.database import execute_query


class DataValidator:
    """Validates the integrity and completeness of loaded graph data."""

    def validate_all(self) -> Dict:
        """Run all validation checks and return a comprehensive report."""
        report = {
            "node_counts": self.check_node_counts(),
            "relationship_counts": self.check_relationship_counts(),
            "orphan_check": self.check_orphan_nodes(),
            "data_quality": self.check_data_quality(),
            "graph_statistics": self.get_graph_statistics(),
            "overall_status": "PASS",
            "issues": [],
        }

        # Evaluate overall status
        for issue in report["issues"]:
            if issue.get("severity") in ("CRITICAL", "HIGH"):
                report["overall_status"] = "FAIL"
                break

        if report["overall_status"] == "PASS":
            for issue in report["issues"]:
                if issue.get("severity") == "MEDIUM":
                    report["overall_status"] = "WARNING"
                    break

        logger.info(f"Validation complete: {report['overall_status']}")
        return report

    def check_node_counts(self) -> Dict[str, int]:
        """Count all node types in the graph."""
        labels = [
            "Taxpayer", "GSTIN", "Invoice", "IRN", "Return",
            "EWayBill", "LineItem", "BankTransaction", "PurchaseRegisterEntry",
        ]
        counts = {}
        for label in labels:
            result = execute_query(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            counts[label] = result[0]["cnt"] if result else 0

        logger.info(f"Node counts: {counts}")
        return counts

    def check_relationship_counts(self) -> Dict[str, int]:
        """Count all relationship types."""
        rel_types = [
            "HAS_GSTIN", "ISSUED_INVOICE", "RECEIVED_INVOICE", "HAS_IRN",
            "REPORTED_IN", "HAS_LINE_ITEM", "COVERED_BY_EWBILL", "MATCHED_WITH",
            "FILED_RETURN", "TRANSACTS_WITH", "ITC_CLAIMED_VIA", "PAID_VIA",
            "CORRESPONDS_TO",
        ]
        counts = {}
        for rel in rel_types:
            result = execute_query(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt")
            counts[rel] = result[0]["cnt"] if result else 0

        logger.info(f"Relationship counts: {counts}")
        return counts

    def check_orphan_nodes(self) -> List[Dict]:
        """Find nodes with no relationships (potential data issues)."""
        issues = []

        # Invoices without supplier
        result = execute_query("""
            MATCH (i:Invoice)
            WHERE NOT (()-[:ISSUED_INVOICE]->(i))
            RETURN count(i) AS cnt
        """)
        cnt = result[0]["cnt"] if result else 0
        if cnt > 0:
            issues.append({
                "check": "invoices_without_supplier",
                "count": cnt,
                "severity": "MEDIUM",
                "description": f"{cnt} invoices have no ISSUED_INVOICE relationship",
            })

        # GSTINs without taxpayer
        result = execute_query("""
            MATCH (g:GSTIN) 
            WHERE NOT ((:Taxpayer)-[:HAS_GSTIN]->(g))
            RETURN count(g) AS cnt
        """)
        cnt = result[0]["cnt"] if result else 0
        if cnt > 0:
            issues.append({
                "check": "gstins_without_taxpayer",
                "count": cnt,
                "severity": "HIGH",
                "description": f"{cnt} GSTINs have no linked Taxpayer",
            })

        # Returns not filed by any GSTIN
        result = execute_query("""
            MATCH (r:Return)
            WHERE NOT ((:GSTIN)-[:FILED_RETURN]->(r))
            RETURN count(r) AS cnt
        """)
        cnt = result[0]["cnt"] if result else 0
        if cnt > 0:
            issues.append({
                "check": "orphan_returns",
                "count": cnt,
                "severity": "LOW",
                "description": f"{cnt} returns not linked to any GSTIN",
            })

        logger.info(f"Orphan check found {len(issues)} issues")
        return issues

    def check_data_quality(self) -> List[Dict]:
        """Run data quality checks on node properties."""
        issues = []

        # Invoices with zero or negative values
        result = execute_query("""
            MATCH (i:Invoice)
            WHERE i.taxable_value <= 0
            RETURN count(i) AS cnt
        """)
        cnt = result[0]["cnt"] if result else 0
        if cnt > 0:
            issues.append({
                "check": "zero_value_invoices",
                "count": cnt,
                "severity": "MEDIUM",
                "description": f"{cnt} invoices with zero or negative taxable value",
            })

        # Cancelled GSTINs with recent invoices
        result = execute_query("""
            MATCH (g:GSTIN {status: 'cancelled'})-[:ISSUED_INVOICE]->(i:Invoice)
            RETURN count(DISTINCT i) AS cnt
        """)
        cnt = result[0]["cnt"] if result else 0
        if cnt > 0:
            issues.append({
                "check": "cancelled_gstin_invoices",
                "count": cnt,
                "severity": "HIGH",
                "description": f"{cnt} invoices issued by cancelled GSTINs (potential phantoms)",
            })

        # Returns not filed
        result = execute_query("""
            MATCH (r:Return {filing_status: 'not_filed'})
            RETURN count(r) AS cnt
        """)
        cnt = result[0]["cnt"] if result else 0
        if cnt > 0:
            issues.append({
                "check": "unfiled_returns",
                "count": cnt,
                "severity": "MEDIUM",
                "description": f"{cnt} returns with status 'not_filed'",
            })

        return issues

    def get_graph_statistics(self) -> Dict:
        """Compute summary statistics about the graph."""
        stats = {}

        # Total nodes and relationships
        result = execute_query("""
            MATCH (n) RETURN count(n) AS total_nodes
        """)
        stats["total_nodes"] = result[0]["total_nodes"] if result else 0

        result = execute_query("""
            MATCH ()-[r]->() RETURN count(r) AS total_relationships
        """)
        stats["total_relationships"] = result[0]["total_relationships"] if result else 0

        # Invoice value statistics
        result = execute_query("""
            MATCH (i:Invoice)
            RETURN 
                sum(i.total_value) AS total_invoice_value,
                avg(i.total_value) AS avg_invoice_value,
                min(i.total_value) AS min_invoice_value,
                max(i.total_value) AS max_invoice_value,
                count(i) AS invoice_count
        """)
        if result:
            stats["invoice_stats"] = result[0]

        # GSTR-1 vs GSTR-2B counts
        result = execute_query("""
            MATCH (i:Invoice)
            RETURN i.source AS source, count(i) AS cnt
        """)
        stats["invoices_by_source"] = {r["source"]: r["cnt"] for r in result}

        # States distribution
        result = execute_query("""
            MATCH (g:GSTIN) 
            RETURN g.state_code AS state, count(g) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """)
        stats["top_states"] = result

        # Average relationships per GSTIN
        result = execute_query("""
            MATCH (g:GSTIN)
            OPTIONAL MATCH (g)-[r]->()
            WITH g, count(r) AS rel_count
            RETURN avg(rel_count) AS avg_rels
        """)
        if result:
            stats["avg_rels_per_gstin"] = result[0]["avg_rels"]

        logger.info(f"Graph statistics: {stats.get('total_nodes', 0)} nodes, "
                     f"{stats.get('total_relationships', 0)} relationships")
        return stats
