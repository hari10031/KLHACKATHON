# Solution Approach

We built a **full-stack GST Reconciliation Engine** that combines knowledge-graph intelligence with explainable machine learning for automated fraud detection.

**Data Ingestion & Reconciliation** — GSTR-1, 2B, and 3B filings are ingested, normalized, and cross-matched at the invoice level. Mismatches in taxable value, tax amounts, and ITC claims are flagged automatically with severity scoring.

**Knowledge Graph (Neo4j)** — Every taxpayer, invoice, and filing becomes a node; relationships (FILED_BY, SOLD_TO, CLAIMED_ITC) form a directed graph with 7,400+ nodes and 10,900+ relationships. This enables multi-hop traversal to uncover circular trading rings, shell company networks, and layered entity collusion invisible to flat-table audits.

**ML-Powered Risk Scoring** — An XGBoost classifier (84.6% accuracy, 93.7% AUC-ROC) trained on 28 graph-derived and behavioral features assigns risk scores to every vendor. SHAP explainability ensures every flag has a human-readable rationale for auditors.

**Real-Time Simulation** — A live simulation engine generates synthetic multi-company transaction networks, animates knowledge graph construction, and runs fraud detection (circular trades, phantom invoices, ITC overclaims, value mismatches) in under 2 seconds — demonstrating production-readiness.

**Interactive Dashboard** — Seven React views (Dashboard, Mismatches, Knowledge Graph, Vendor Risk, Audit Trail, Performance Metrics, Live Simulation) provide drill-down visibility for auditors and policy makers.
