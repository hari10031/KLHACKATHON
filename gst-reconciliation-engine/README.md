# Intelligent GST Reconciliation Engine using Knowledge Graphs

A production-grade system that uses **Neo4j knowledge graphs** to perform 4-level GST reconciliation, detect circular trading, predict vendor risk via XGBoost/SHAP, and generate explainable audit trails.

---

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  React Dashboard│────▶│  FastAPI      │────▶│  Neo4j 5.15      │
│  (D3.js/vis-net)│     │  Backend      │     │  Knowledge Graph │
│  Port 5173      │     │  Port 8000    │     │  Port 7687       │
└─────────────────┘     └──────┬───────┘     └──────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │  Engine Pipeline     │
                    │  L1: Invoice Match   │
                    │  L2: ITC Chain (7-hop)│
                    │  L3: Circular Trade  │
                    │  L4: Risk Propagation│
                    │  ML: XGBoost + SHAP  │
                    └─────────────────────┘
```

## Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| D1 | Knowledge Graph Schema | 10 node types, 13 edge types, Pydantic models, Cypher constraints/indexes |
| D2 | Mock Data Ingestion | Synthetic generator (55 taxpayers, 600 invoices, 17% mismatches), Neo4j batch loader, validator |
| D3 | 4-Level Reconciliation Engine | L1 fuzzy matching, L2 ITC chain validation, L3 circular trade detection, L4 PageRank risk propagation |
| D4 | Interactive React Dashboard | 5 views: Summary, Mismatch Explorer, Graph Visualization, Vendor Scorecard, Audit Trail |
| D5 | Explainable Audit Trail | Jinja2 HTML reports with NL narrative, traversal paths, regulatory references |
| D6 | Predictive Vendor Risk Model | 30-feature extraction, XGBoost classifier, SHAP explanations |

## Tech Stack

- **Backend**: Python 3.11, FastAPI 0.109, Pydantic v2
- **Database**: Neo4j 5.15.0 Community Edition
- **Graph Analytics**: NetworkX 3.2 (PageRank, cycle detection, community detection)
- **ML**: XGBoost 2.0, SHAP 0.44, scikit-learn
- **Frontend**: React 18, vis-network, D3.js, Recharts, Tailwind CSS
- **Reports**: Jinja2, WeasyPrint (PDF)
- **Infra**: Docker Compose, Loguru

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local frontend dev)

### Run with Docker

```bash
# Clone and navigate
cd gst-reconciliation-engine

# Copy env file
cp .env.example .env

# Start all services
docker compose up --build -d

# Access
# Neo4j Browser:  http://localhost:7474
# Backend API:    http://localhost:8000
# Frontend:       http://localhost:5173
# API Docs:       http://localhost:8000/docs
```

### Seed Database & Run Reconciliation

```bash
# Seed with synthetic data
curl -X POST http://localhost:8000/api/v1/ingestion/seed

# Run full reconciliation
curl -X POST "http://localhost:8000/api/v1/reconciliation/run?gstin=27AADCB2230M1ZT&return_period=032025"

# Train ML model
curl -X POST http://localhost:8000/api/v1/risk/train

# Get vendor risk with SHAP explanation
curl http://localhost:8000/api/v1/risk/vendor/27AADCB2230M1ZT

# Generate audit report (HTML)
curl "http://localhost:8000/api/v1/audit/report?gstin=27AADCB2230M1ZT&return_period=032025"
```

### Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
cd backend
pytest tests/ -v
```

## Project Structure

```
gst-reconciliation-engine/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                      # FastAPI entry point
│   │   ├── config.py                    # Pydantic settings
│   │   ├── database.py                  # Neo4j connection manager
│   │   ├── models/
│   │   │   ├── nodes.py                 # 10 node Pydantic models
│   │   │   ├── edges.py                 # 13 edge models
│   │   │   ├── mismatch.py              # Mismatch classification
│   │   │   ├── audit.py                 # Audit finding models
│   │   │   └── risk.py                  # Risk prediction models
│   │   ├── schema/
│   │   │   └── cypher_schema.py         # Constraints, indexes, templates
│   │   ├── utils/
│   │   │   ├── gstin.py                 # GSTIN validation & normalization
│   │   │   └── helpers.py               # Financial calculations
│   │   ├── ingestion/
│   │   │   ├── generator.py             # Synthetic data generator
│   │   │   ├── neo4j_loader.py          # Batch Neo4j loader
│   │   │   └── validator.py             # Data quality validator
│   │   ├── engine/
│   │   │   ├── reconciliation.py        # Main orchestrator
│   │   │   ├── level1_matching.py       # Fuzzy invoice matching
│   │   │   ├── level2_itc_chain.py      # ITC chain validation
│   │   │   ├── level3_circular.py       # Circular trade detection
│   │   │   ├── level4_risk.py           # Network risk propagation
│   │   │   └── risk_scorer.py           # Composite risk scoring
│   │   ├── audit/
│   │   │   ├── trail_generator.py       # Jinja2 report generator
│   │   │   └── templates/
│   │   │       └── audit_report.html    # HTML report template
│   │   ├── ml/
│   │   │   ├── feature_extraction.py    # 30-feature graph extraction
│   │   │   └── model.py                 # XGBoost + SHAP pipeline
│   │   └── api/
│   │       ├── reconciliation.py        # Reconciliation endpoints
│   │       ├── dashboard.py             # Dashboard & graph data
│   │       ├── audit.py                 # Audit trail endpoints
│   │       ├── risk.py                  # Risk & ML endpoints
│   │       └── ingestion.py             # Data management endpoints
│   └── tests/
│       ├── conftest.py
│       ├── test_reconciliation.py
│       └── test_api.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                      # Router + sidebar layout
│       ├── api.js                       # Axios API client
│       ├── index.css
│       └── views/
│           ├── ReconciliationSummary.jsx # KPI cards + charts
│           ├── MismatchExplorer.jsx      # Filterable table + detail drawer
│           ├── GraphVisualization.jsx    # vis-network interactive graph
│           ├── VendorScorecard.jsx       # Risk distribution + table
│           └── AuditTrail.jsx           # Expandable findings + export
└── neo4j/
    └── init/
        └── constraints.cypher
```

## Knowledge Graph Schema

### Node Types
`Taxpayer` → `GSTIN` → `Invoice` → `LineItem`
`IRN`, `Return`, `EWayBill`, `BankTransaction`, `PurchaseRegisterEntry`

### Key Relationships
`HAS_GSTIN`, `ISSUED_INVOICE`, `RECEIVED_INVOICE`, `HAS_IRN`, `REPORTED_IN`,
`HAS_LINE_ITEM`, `COVERED_BY_EWBILL`, `MATCHED_WITH`, `FILED_RETURN`,
`TRANSACTS_WITH`, `ITC_CLAIMED_VIA`, `PAID_VIA`, `CORRESPONDS_TO`

## Reconciliation Levels

| Level | Hops | What it does |
|-------|------|-------------|
| L1 | 1 | Fuzzy invoice matching (GSTR-1 ↔ GSTR-2B) with 4-component score |
| L2 | 2-7 | ITC chain validation: PurchaseRegister → Invoice → GSTR-1 → GSTR-2B → GSTR-3B + IRN + supplier status |
| L3 | Variable | Circular trade detection via NetworkX cycle detection + Cypher pattern matching |
| L4 | Graph-wide | Risk propagation: PageRank, betweenness, community detection, neighbor contagion |

## Composite Risk Score Formula

```
Score = 0.4 × Financial_Impact + 0.3 × Probability + 0.3 × Vendor_Risk
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/reconciliation/run` | Run full 4-level reconciliation |
| GET | `/api/v1/reconciliation/gstins` | List all GSTINs |
| GET | `/api/v1/reconciliation/mismatches` | Query mismatches with filters |
| GET | `/api/v1/dashboard/summary` | Dashboard KPIs |
| GET | `/api/v1/dashboard/graph` | Graph data for vis-network |
| GET | `/api/v1/dashboard/vendor-scorecard` | Vendor risk table |
| GET | `/api/v1/audit/report` | HTML audit report |
| GET | `/api/v1/audit/traversal` | Graph traversal path |
| GET | `/api/v1/risk/vendor/{gstin}` | Vendor risk detail |
| GET | `/api/v1/risk/heatmap` | Risk heatmap data |
| POST | `/api/v1/risk/train` | Train XGBoost model |
| POST | `/api/v1/ingestion/seed` | Generate + load + validate data |

## License

MIT
