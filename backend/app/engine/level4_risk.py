"""
Level 4: Vendor Network Risk Propagation (graph-wide)
Propagate risk scores using PageRank-style algorithm via NetworkX.
Run community detection to identify clusters of risky entities.
"""

from typing import List, Dict, Tuple
import networkx as nx
import numpy as np
from loguru import logger

from app.database import execute_query, execute_write
from app.utils.helpers import generate_uuid
from app.models.mismatch import Mismatch, MismatchType, Severity, RiskCategory, FinancialImpact, RootCause, ResolutionAction


class Level4RiskPropagation:
    """
    Propagates risk scores from non-compliant vendors to connected buyers
    using PageRank-style algorithms. Identifies risky entity clusters.
    """

    def __init__(self, damping_factor: float = 0.85, max_iterations: int = 100):
        self.damping_factor = damping_factor
        self.max_iterations = max_iterations

    def propagate_risk(self) -> Dict:
        """
        Run full risk propagation pipeline:
        1. Build weighted transaction graph
        2. Compute PageRank for influence
        3. Compute risk-weighted PageRank
        4. Detect communities
        5. Generate per-GSTIN risk scores
        """
        logger.info("Level 4: Starting vendor network risk propagation...")

        # Build graph
        G = self._build_risk_graph()
        logger.info(f"Risk graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        if G.number_of_nodes() == 0:
            return {"scores": {}, "communities": [], "high_risk_gstins": []}

        # Compute centrality metrics
        pagerank = nx.pagerank(G, alpha=self.damping_factor, max_iter=self.max_iterations, weight="weight")
        degree_centrality = nx.degree_centrality(G)
        betweenness = nx.betweenness_centrality(G, weight="weight")

        try:
            clustering = nx.clustering(G.to_undirected())
        except Exception:
            clustering = {n: 0.0 for n in G.nodes}

        # Compute risk-weighted scores
        risk_scores = self._compute_risk_scores(G, pagerank, degree_centrality, betweenness, clustering)

        # Community detection using Louvain-style greedy modularity
        communities = self._detect_communities(G)

        # Community risk scoring
        community_risks = self._score_communities(communities, risk_scores)

        # Identify high-risk GSTINs
        high_risk = [
            {"gstin": gstin, "risk_score": score, **metrics}
            for gstin, (score, metrics) in risk_scores.items()
            if score >= 60
        ]
        high_risk.sort(key=lambda x: x["risk_score"], reverse=True)

        # Store risk scores back in Neo4j
        self._store_risk_scores(risk_scores)

        result = {
            "scores": {g: s for g, (s, _) in risk_scores.items()},
            "communities": community_risks,
            "high_risk_gstins": high_risk[:20],
            "graph_stats": {
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "density": nx.density(G),
                "avg_clustering": sum(clustering.values()) / max(len(clustering), 1),
                "num_communities": len(communities),
            },
        }

        logger.info(f"Level 4 complete: {len(high_risk)} high-risk GSTINs identified")
        return result

    def _build_risk_graph(self) -> nx.DiGraph:
        """Build weighted directed graph with risk attributes."""
        cypher = """
        MATCH (g1:GSTIN)-[r:TRANSACTS_WITH]->(g2:GSTIN)
        OPTIONAL MATCH (t1:Taxpayer)-[:HAS_GSTIN]->(g1)
        OPTIONAL MATCH (t2:Taxpayer)-[:HAS_GSTIN]->(g2)
        RETURN g1.gstin_number AS source,
               g2.gstin_number AS target,
               r.total_value AS value,
               r.total_transactions AS txn_count,
               g1.status AS source_status,
               g2.status AS target_status,
               t1.compliance_rating AS source_compliance,
               t2.compliance_rating AS target_compliance
        """
        records = execute_query(cypher)

        G = nx.DiGraph()
        for rec in records:
            src = rec["source"]
            tgt = rec["target"]
            G.add_edge(src, tgt, weight=rec.get("value") or 1.0, txn_count=rec.get("txn_count") or 0)

            # Node attributes
            if src not in G.nodes or "compliance" not in G.nodes.get(src, {}):
                G.nodes[src]["status"] = rec.get("source_status", "active")
                G.nodes[src]["compliance"] = rec.get("source_compliance") or 50.0
                G.nodes[src]["base_risk"] = self._base_risk(
                    rec.get("source_status"), rec.get("source_compliance")
                )

            if tgt not in G.nodes or "compliance" not in G.nodes.get(tgt, {}):
                G.nodes[tgt]["status"] = rec.get("target_status", "active")
                G.nodes[tgt]["compliance"] = rec.get("target_compliance") or 50.0
                G.nodes[tgt]["base_risk"] = self._base_risk(
                    rec.get("target_status"), rec.get("target_compliance")
                )

        # Add mismatch-based risk
        mismatch_cypher = """
        MATCH (i:Invoice)
        WHERE i.source = 'GSTR1'
        OPTIONAL MATCH (i)-[m:MATCHED_WITH]->()
        WITH i.supplier_gstin AS gstin,
             count(CASE WHEN m IS NULL THEN 1 END) AS unmatched,
             count(CASE WHEN m.match_score < 95 THEN 1 END) AS partial,
             count(i) AS total
        RETURN gstin, unmatched, partial, total
        """
        mismatch_records = execute_query(mismatch_cypher)
        for rec in mismatch_records:
            gstin = rec["gstin"]
            if gstin in G.nodes:
                total = max(rec["total"], 1)
                mismatch_ratio = (rec["unmatched"] + rec["partial"]) / total
                G.nodes[gstin]["mismatch_ratio"] = mismatch_ratio

        return G

    def _base_risk(self, status: str, compliance: float) -> float:
        """Calculate base risk from status and compliance rating."""
        risk = 0.0
        if status == "cancelled":
            risk = 90.0
        elif status == "suspended":
            risk = 70.0
        else:
            risk = max(0, 100 - (compliance or 50))
        return risk

    def _compute_risk_scores(
        self, G: nx.DiGraph,
        pagerank: Dict[str, float],
        degree_centrality: Dict[str, float],
        betweenness: Dict[str, float],
        clustering: Dict[str, float],
    ) -> Dict[str, Tuple[float, dict]]:
        """
        Compute composite risk scores incorporating:
        - Base risk (compliance, status)
        - Network influence (PageRank)
        - Connectivity (degree centrality)
        - Bridge position (betweenness)
        - Mismatch history
        - Neighbor risk contagion
        """
        scores = {}

        # Normalize PageRank to 0-100
        max_pr = max(pagerank.values()) if pagerank else 1
        norm_pr = {k: (v / max_pr) * 100 for k, v in pagerank.items()}

        for node in G.nodes:
            base_risk = G.nodes[node].get("base_risk", 50)
            mismatch_ratio = G.nodes[node].get("mismatch_ratio", 0)
            pr_score = norm_pr.get(node, 0)
            deg = degree_centrality.get(node, 0)
            btw = betweenness.get(node, 0)
            clust = clustering.get(node, 0)

            # Neighbor contagion: average risk of connected nodes
            neighbors = list(G.predecessors(node)) + list(G.successors(node))
            if neighbors:
                neighbor_risks = [
                    G.nodes[n].get("base_risk", 50) for n in neighbors if n in G.nodes
                ]
                avg_neighbor_risk = sum(neighbor_risks) / max(len(neighbor_risks), 1)
            else:
                avg_neighbor_risk = 0

            # Composite risk score
            composite = (
                0.30 * base_risk +
                0.20 * (mismatch_ratio * 100) +
                0.15 * avg_neighbor_risk +
                0.15 * min(pr_score * 2, 100) +  # High PageRank = high influence
                0.10 * (btw * 200) +  # Bridge nodes
                0.10 * (deg * 100)
            )
            composite = min(100, max(0, composite))

            metrics = {
                "base_risk": round(base_risk, 2),
                "mismatch_ratio": round(mismatch_ratio, 4),
                "pagerank": round(pagerank.get(node, 0), 6),
                "degree_centrality": round(deg, 4),
                "betweenness": round(btw, 4),
                "clustering_coefficient": round(clust, 4),
                "neighbor_avg_risk": round(avg_neighbor_risk, 2),
                "compliance": G.nodes[node].get("compliance", 50),
                "status": G.nodes[node].get("status", "active"),
            }

            scores[node] = (round(composite, 2), metrics)

        return scores

    def _detect_communities(self, G: nx.DiGraph) -> List[set]:
        """Detect communities using greedy modularity optimization."""
        try:
            undirected = G.to_undirected()
            communities = list(nx.community.greedy_modularity_communities(undirected))
            return [set(c) for c in communities]
        except Exception as e:
            logger.warning(f"Community detection fallback: {e}")
            # Fallback: connected components
            undirected = G.to_undirected()
            return [set(c) for c in nx.connected_components(undirected)]

    def _score_communities(
        self, communities: List[set], risk_scores: Dict[str, Tuple[float, dict]]
    ) -> List[dict]:
        """Score each community by aggregate risk."""
        community_risks = []
        for idx, community in enumerate(communities):
            member_scores = [risk_scores[m][0] for m in community if m in risk_scores]
            if not member_scores:
                continue

            avg_risk = sum(member_scores) / len(member_scores)
            max_risk = max(member_scores)
            high_risk_count = sum(1 for s in member_scores if s >= 60)

            community_risks.append({
                "community_id": idx,
                "size": len(community),
                "members": list(community)[:10],  # Limit for API response
                "avg_risk_score": round(avg_risk, 2),
                "max_risk_score": round(max_risk, 2),
                "high_risk_members": high_risk_count,
                "risk_level": "HIGH" if avg_risk >= 60 else "MEDIUM" if avg_risk >= 40 else "LOW",
            })

        community_risks.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return community_risks

    def _store_risk_scores(self, risk_scores: Dict[str, Tuple[float, dict]]):
        """Store computed risk scores back into Neo4j GSTIN nodes."""
        batch = [
            {"gstin": gstin, "risk_score": score, **metrics}
            for gstin, (score, metrics) in risk_scores.items()
        ]

        if batch:
            cypher = """
            MATCH (g:GSTIN {gstin_number: row.gstin})
            SET g.risk_score = row.risk_score,
                g.pagerank = row.pagerank,
                g.degree_centrality = row.degree_centrality,
                g.betweenness = row.betweenness,
                g.clustering_coefficient = row.clustering_coefficient
            """
            # Batch update
            for i in range(0, len(batch), 500):
                chunk = batch[i:i + 500]
                execute_write(
                    f"UNWIND $batch AS row " + cypher,
                    {"batch": chunk}
                )

        logger.info(f"Stored risk scores for {len(batch)} GSTINs")
