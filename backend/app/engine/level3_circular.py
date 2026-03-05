"""
Level 3: Circular Trade Detection (variable hops)
Detects cycles in the transaction graph using DFS-based cycle detection
via Cypher shortest-path queries and NetworkX.
"""

from typing import List, Dict, Set, Tuple
import networkx as nx
from loguru import logger

from app.database import execute_query
from app.utils.helpers import generate_uuid, severity_from_amount
from app.models.mismatch import (
    Mismatch, MismatchType, Severity, RiskCategory,
    FinancialImpact, RootCause, AffectedChain, ChainHop, ResolutionAction,
)


class Level3CircularTradeDetector:
    """
    Detects circular trading patterns (A → B → C → A) in the
    GSTIN transaction graph. Flags chains where cumulative value
    inflates artificially.
    """

    def __init__(self, min_cycle_length: int = 3, max_cycle_length: int = 8):
        self.min_cycle_length = min_cycle_length
        self.max_cycle_length = max_cycle_length

    def detect_circular_trades(self) -> List[Mismatch]:
        """
        Run circular trade detection across the entire transaction graph.
        Uses both Cypher and NetworkX for comprehensive detection.
        """
        logger.info("Level 3: Detecting circular trading patterns...")

        # Step 1: Build transaction graph from Neo4j
        graph = self._build_transaction_graph()
        logger.info(f"Transaction graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

        # Step 2: Detect cycles using NetworkX DFS
        cycles = self._detect_cycles_networkx(graph)
        logger.info(f"Found {len(cycles)} cycles via NetworkX")

        # Step 3: Also check via Cypher for short cycles
        cypher_cycles = self._detect_cycles_cypher()
        logger.info(f"Found {len(cypher_cycles)} cycles via Cypher")

        # Merge and deduplicate
        all_cycles = self._merge_cycles(cycles, cypher_cycles)
        logger.info(f"Total unique cycles: {len(all_cycles)}")

        # Step 4: Analyze each cycle for value inflation
        mismatches = []
        for cycle in all_cycles:
            mismatch = self._analyze_cycle(cycle, graph)
            if mismatch:
                mismatches.append(mismatch)

        logger.info(f"Level 3 found {len(mismatches)} suspicious circular trades")
        return mismatches

    def _build_transaction_graph(self) -> nx.DiGraph:
        """Build a NetworkX directed graph from TRANSACTS_WITH relationships."""
        cypher = """
        MATCH (g1:GSTIN)-[r:TRANSACTS_WITH]->(g2:GSTIN)
        RETURN g1.gstin_number AS source,
               g2.gstin_number AS target,
               r.total_transactions AS txn_count,
               r.total_value AS total_value
        """
        records = execute_query(cypher)

        G = nx.DiGraph()
        for rec in records:
            G.add_edge(
                rec["source"], rec["target"],
                weight=rec["total_value"] or 0,
                txn_count=rec["txn_count"] or 0,
            )

        # Add node attributes (GSTIN status, compliance rating)
        node_cypher = """
        MATCH (t:Taxpayer)-[:HAS_GSTIN]->(g:GSTIN)
        RETURN g.gstin_number AS gstin,
               g.status AS status,
               t.compliance_rating AS compliance
        """
        node_records = execute_query(node_cypher)
        for rec in node_records:
            gstin = rec["gstin"]
            if gstin in G:
                G.nodes[gstin]["status"] = rec.get("status", "active")
                G.nodes[gstin]["compliance"] = rec.get("compliance", 50)

        return G

    def _detect_cycles_networkx(self, G: nx.DiGraph) -> List[List[str]]:
        """Detect simple cycles using NetworkX with length bound for performance."""
        try:
            from itertools import islice
            # Use length_bound to avoid exponential blowup on dense graphs
            filtered = []
            max_cycles = 200  # Safety cap
            for cycle in islice(
                nx.simple_cycles(G, length_bound=self.max_cycle_length), max_cycles
            ):
                if len(cycle) >= self.min_cycle_length:
                    filtered.append(cycle)
            return filtered
        except TypeError:
            # Fallback for older NetworkX without length_bound
            try:
                from itertools import islice
                filtered = []
                for cycle in islice(nx.simple_cycles(G), 200):
                    if self.min_cycle_length <= len(cycle) <= self.max_cycle_length:
                        filtered.append(cycle)
                return filtered
            except Exception as e:
                logger.error(f"NetworkX cycle detection error: {e}")
                return []
        except Exception as e:
            logger.error(f"NetworkX cycle detection error: {e}")
            return []

    def _detect_cycles_cypher(self) -> List[List[str]]:
        """Detect short cycles using Cypher pattern matching."""
        cycles = []

        # Detect 3-node cycles (A->B->C->A)
        cypher_3 = """
        MATCH (a:GSTIN)-[:TRANSACTS_WITH]->(b:GSTIN)-[:TRANSACTS_WITH]->(c:GSTIN)-[:TRANSACTS_WITH]->(a)
        WHERE a.gstin_number < b.gstin_number AND b.gstin_number < c.gstin_number
        RETURN a.gstin_number AS n1, b.gstin_number AS n2, c.gstin_number AS n3
        LIMIT 100
        """
        results = execute_query(cypher_3)
        for r in results:
            cycles.append([r["n1"], r["n2"], r["n3"]])

        # Detect 4-node cycles
        cypher_4 = """
        MATCH (a:GSTIN)-[:TRANSACTS_WITH]->(b:GSTIN)-[:TRANSACTS_WITH]->(c:GSTIN)
              -[:TRANSACTS_WITH]->(d:GSTIN)-[:TRANSACTS_WITH]->(a)
        WHERE a.gstin_number < b.gstin_number 
          AND b.gstin_number < c.gstin_number
          AND c.gstin_number < d.gstin_number
        RETURN a.gstin_number AS n1, b.gstin_number AS n2, 
               c.gstin_number AS n3, d.gstin_number AS n4
        LIMIT 100
        """
        results = execute_query(cypher_4)
        for r in results:
            cycles.append([r["n1"], r["n2"], r["n3"], r["n4"]])

        return cycles

    def _merge_cycles(self, nx_cycles: List[List[str]], cypher_cycles: List[List[str]]) -> List[List[str]]:
        """Deduplicate cycles from both detection methods."""
        seen = set()
        merged = []

        for cycle in nx_cycles + cypher_cycles:
            # Normalize: rotate to start with smallest element
            min_idx = cycle.index(min(cycle))
            normalized = tuple(cycle[min_idx:] + cycle[:min_idx])
            if normalized not in seen:
                seen.add(normalized)
                merged.append(list(normalized))

        return merged

    def _analyze_cycle(self, cycle: List[str], G: nx.DiGraph) -> Mismatch:
        """Analyze a cycle for value inflation and risk indicators."""
        # Get edge values in the cycle
        edge_values = []
        total_value = 0
        for i in range(len(cycle)):
            src = cycle[i]
            tgt = cycle[(i + 1) % len(cycle)]
            edge_data = G.get_edge_data(src, tgt) or {}
            value = edge_data.get("weight", 0)
            edge_values.append({"from": src, "to": tgt, "value": value})
            total_value += value

        # Check for value inflation: values should be roughly similar in genuine trade
        if edge_values:
            values = [e["value"] for e in edge_values if e["value"] > 0]
            if values:
                min_val = min(values)
                max_val = max(values)
                inflation_ratio = max_val / max(min_val, 1)
            else:
                inflation_ratio = 1.0
        else:
            inflation_ratio = 1.0

        # Risk scoring
        is_suspicious = inflation_ratio > 1.2 or len(cycle) == 3

        # Check compliance of participants
        low_compliance_count = 0
        for gstin in cycle:
            if gstin in G.nodes:
                compliance = G.nodes[gstin].get("compliance", 50)
                if compliance < 40:
                    low_compliance_count += 1

        avg_edge_value = total_value / max(len(cycle), 1)
        estimated_tax = avg_edge_value * 0.18  # Assume 18% GST

        if inflation_ratio > 2.0 or low_compliance_count >= 2:
            severity = Severity.CRITICAL
        elif inflation_ratio > 1.5:
            severity = Severity.HIGH
        elif is_suspicious:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        # Build chain hops
        hops = []
        for i, edge in enumerate(edge_values):
            hops.append(ChainHop(
                hop_number=i + 1,
                source_type="GSTIN",
                source_id=edge["from"],
                target_type="GSTIN",
                target_id=edge["to"],
                relationship="TRANSACTS_WITH",
                status="warning" if inflation_ratio > 1.2 else "valid",
                details=f"Transaction value: ₹{edge['value']:,.2f}",
            ))

        return Mismatch(
            mismatch_id=f"MM-L3-{generate_uuid()[:8]}",
            mismatch_type=MismatchType.CIRCULAR_TRADE,
            severity=severity,
            financial_impact=FinancialImpact(
                itc_at_risk=round(estimated_tax, 2),
                potential_interest_liability=round(estimated_tax * 0.18 / 12, 2),
                penalty_exposure=round(estimated_tax * 1.0, 2),  # 100% penalty for fraud
            ),
            risk_category=RiskCategory.DEMAND_NOTICE if severity in (Severity.CRITICAL, Severity.HIGH) else RiskCategory.AUDIT_TRIGGER,
            root_cause=RootCause(
                classification=f"Circular trade detected: {' → '.join(cycle)} → {cycle[0]}",
                confidence=min(95, 50 + inflation_ratio * 15 + low_compliance_count * 10),
                evidence_paths=[
                    f"{e['from']} → {e['to']}: ₹{e['value']:,.2f}" for e in edge_values
                ],
                alternative_explanations=[
                    "Legitimate supply chain with circular dependencies",
                    "Group company transactions (related party)",
                ],
            ),
            affected_chain=AffectedChain(
                hops=hops,
                chain_completeness=100.0,
            ),
            resolution_actions=[
                ResolutionAction(
                    action_id=1,
                    description=f"Investigate circular chain: {' → '.join(cycle[:3])}...",
                    priority="CRITICAL" if severity == Severity.CRITICAL else "HIGH",
                    deadline_days=7,
                    regulatory_reference="Section 67 CGST Act — Inspection & Search",
                ),
                ResolutionAction(
                    action_id=2,
                    description="Check if entities are related parties under Section 15",
                    priority="HIGH",
                    deadline_days=15,
                    regulatory_reference="Section 15(5) CGST Act — Valuation of related party transactions",
                ),
                ResolutionAction(
                    action_id=3,
                    description="Verify genuineness of goods/services movement",
                    priority="HIGH",
                    deadline_days=15,
                    regulatory_reference="Section 16(2)(b) CGST Act",
                ),
            ],
        )
