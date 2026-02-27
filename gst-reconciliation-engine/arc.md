# Architecture Prompt

Design a production-grade architecture for a GST Reconciliation & Fraud Detection Engine with the following components:

**Data Layer** — Neo4j Aura graph database storing taxpayers, invoices, and GST filings as nodes with directed relationships (FILED_BY, SOLD_TO, CLAIMED_ITC, PART_OF_RETURN). Support 10K+ nodes and 15K+ relationships with Cypher-optimized queries for multi-hop traversal (circular trade detection via DFS up to depth 5).

**Backend** — Python FastAPI service with six API routers: reconciliation (invoice-level GSTR-1/2B/3B cross-matching), dashboard (aggregate analytics + graph queries), audit trail (immutable action log), risk scoring (XGBoost inference + SHAP explanations), data ingestion (bulk CSV/JSON upload with Neo4j batch writes), and model metrics (performance dashboards + live simulation engine). Use async endpoints, connection pooling for Neo4j, and structured logging via Loguru.

**ML Pipeline** — XGBoost binary classifier trained on 28 graph-derived features (in-degree, out-degree, PageRank, clustering coefficient, transaction velocity, ITC claim ratios, filing gaps). Serve predictions via REST with SHAP-based feature attribution. Include a real-time simulation module that generates synthetic multi-company transaction networks, builds an in-memory graph, and runs four fraud detectors (circular trade DFS, phantom invoice detection, ITC overclaim analysis, value mismatch flagging) in under 2 seconds.

**Frontend** — React 18 SPA with Vite, Tailwind CSS, Recharts, and Canvas API. Seven views: Dashboard (KPIs + trend charts), Mismatches (filterable table with severity badges), Knowledge Graph (interactive vis-network visualization), Vendor Risk (scored vendor cards with SHAP waterfall), Audit Trail (timestamped action log), Performance Metrics (ROC curve, confusion matrix, feature importance, threshold trade-offs), Live Simulation (animated graph construction, fraud detection walkthrough, CSV upload). Vite proxy to backend API.

**Infrastructure** — Containerized with Docker Compose (frontend, backend, Neo4j). CI/CD via GitHub Actions. Environment-based config for Neo4j Aura connection strings. CORS middleware for cross-origin frontend requests. Production deployment target: Azure App Service or AWS ECS with Neo4j Aura managed database.
