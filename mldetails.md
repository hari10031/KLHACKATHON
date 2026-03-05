# ML Model Details — GST Reconciliation Engine

## 1. Overview

The GST Reconciliation Engine uses a **Machine Learning pipeline** built on top of a **Neo4j Knowledge Graph** to detect fraudulent GST transactions, circular trading networks, phantom invoices, and ITC (Input Tax Credit) fraud. The ML system combines **graph-based feature engineering**, **XGBoost classification**, and **SHAP explainability** to provide transparent, auditable fraud predictions.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    ML PIPELINE ARCHITECTURE                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐  │
│  │  Neo4j       │────│  Feature          │────│  XGBoost       │  │
│  │  Knowledge   │    │  Extraction       │    │  Classifier    │  │
│  │  Graph       │    │  (28 Features)    │    │  (Binary)      │  │
│  └─────────────┘    └──────────────────┘    └────────────────┘  │
│        │                                           │             │
│        │            ┌──────────────────┐           │             │
│        └────────────│  SHAP            │───────────┘             │
│                     │  Explainability  │                         │
│                     └──────────────────┘                         │
│                                                                  │
│  Labels: Unsupervised → Supervised Bootstrap                     │
│  Output: Risk Score (0-1), Risk Label, Top 8 Contributing Factors│
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Feature Engineering

### 3.1 Feature Categories (28 Total Features)

The model extracts **28 features** per GSTIN from the Neo4j knowledge graph, organized into 5 categories:

#### A. Transaction Features (8 features)
| # | Feature Name | Description | Source Query |
|---|-------------|-------------|-------------|
| 1 | `total_invoices_issued` | Number of invoices issued by this GSTIN | `(g)-[:ISSUED_INVOICE]->(inv)` |
| 2 | `total_invoices_received` | Number of invoices received | `(g)<-[:ISSUED_INVOICE]-(inv)` |
| 3 | `total_value_issued` | Sum of all issued invoice values (₹) | `sum(inv.total_value)` |
| 4 | `total_value_received` | Sum of all received invoice values (₹) | `sum(inv.total_value)` |
| 5 | `avg_invoice_value` | Average invoice value across all transactions | Derived |
| 6 | `max_invoice_value` | Maximum single invoice value | `max(inv.total_value)` |
| 7 | `distinct_counterparties` | Number of unique buyer GSTINs | `count(DISTINCT inv.buyer_gstin)` |
| 8 | `invoice_frequency_stddev` | Standard deviation of invoice values (regularity) | `stDev(inv.total_value)` |

#### B. Mismatch Features (8 features)
| # | Feature Name | Description | Source Query |
|---|-------------|-------------|-------------|
| 9 | `total_mismatches` | Total mismatches detected for this GSTIN | Count of Mismatch nodes |
| 10 | `critical_mismatches` | Number of CRITICAL severity mismatches | Filtered count |
| 11 | `high_mismatches` | Number of HIGH severity mismatches | Filtered count |
| 12 | `mismatch_rate` | Ratio of mismatches to total invoices | `total_mismatches / total_invoices` |
| 13 | `total_itc_at_risk` | Sum of ITC at risk across all mismatches (₹) | `sum(m.itc_at_risk)` |
| 14 | `avg_risk_score` | Average composite risk score of mismatches | `avg(m.composite_risk_score)` |
| 15 | `has_circular_trade` | Binary: whether circular trade detected (0/1) | Mismatch type check |
| 16 | `has_phantom_invoice` | Binary: whether phantom invoice detected (0/1) | Mismatch type check |

#### C. Network/Graph Features (7 features)
| # | Feature Name | Description | Source |
|---|-------------|-------------|--------|
| 17 | `pagerank` | PageRank centrality score | Pre-computed via GDS |
| 18 | `degree_centrality` | Normalized degree centrality | Pre-computed via GDS |
| 19 | `betweenness_centrality` | Betweenness centrality (bridge nodes) | Pre-computed via GDS |
| 20 | `clustering_coefficient` | Local clustering coefficient | Pre-computed via GDS |
| 21 | `community_id` | Community detection cluster ID (Louvain) | Pre-computed via GDS |
| 22 | `in_degree` | Number of incoming TRANSACTS_WITH edges | `()-[:TRANSACTS_WITH]->(g)` |
| 23 | `out_degree` | Number of outgoing TRANSACTS_WITH edges | `(g)-[:TRANSACTS_WITH]->()` |

#### D. Compliance Features (4 features)
| # | Feature Name | Description | Source Query |
|---|-------------|-------------|-------------|
| 24 | `gstr1_filing_rate` | Proportion of GSTR-1 filings (max 1.0) | `filed / 12` |
| 25 | `gstr3b_filing_rate` | Proportion of GSTR-3B filings (max 1.0) | `filed / 12` |
| 26 | `late_filing_count` | Number of late return filings | `filing_status = 'filed_late'` |
| 27 | `avg_filing_delay_days` | Average filing delay in days | Return dates |

#### E. Financial Pattern Features (3 features)
| # | Feature Name | Description | Computation |
|---|-------------|-------------|-------------|
| 28 | `itc_to_output_ratio` | ITC claimed vs output tax (capped at 5.0) | `received / issued` |
| 29 | `value_concentration_index` | How concentrated values are in max invoice | `max_value / total_issued` |
| 30 | `month_over_month_growth` | MoM transaction growth rate | Simplified to 0 |

---

## 4. Model Configuration

### 4.1 XGBoost Classifier Parameters

```python
XGBClassifier(
    n_estimators=200,          # Number of boosting rounds
    max_depth=6,               # Maximum tree depth (prevents overfitting)
    learning_rate=0.1,         # Step size shrinkage
    subsample=0.8,             # Row subsampling ratio
    colsample_bytree=0.8,     # Column subsampling per tree
    random_state=42,           # Reproducibility seed
    use_label_encoder=False,
    eval_metric='logloss',     # Binary cross-entropy loss
    enable_categorical=False
)
```

### 4.2 Why XGBoost?

| Aspect | Justification |
|--------|--------------|
| **Tabular data** | XGBoost excels on structured/tabular features — our 28 features are numeric |
| **Handling imbalance** | Built-in support for class weights and threshold tuning |
| **Feature interaction** | Tree-based models naturally capture feature interactions (e.g., high ITC + phantom invoice) |
| **Interpretability** | Compatible with SHAP for per-prediction explanations |
| **Speed** | Fast training on ~64 GSTINs with 28 features |
| **Robustness** | Regularization via max_depth, subsample, colsample prevents overfitting |

---

## 5. Training Pipeline

### 5.1 Label Generation (Unsupervised → Supervised Bootstrap)

Since no ground-truth fraud labels exist initially, labels are **bootstrapped from graph-computed risk scores**:

```python
def _generate_labels(gstins, features):
    labels = []
    for gstin in gstins:
        result = execute_query(
            "MATCH (g:GSTIN {gstin_number: $gstin}) RETURN g.risk_score AS score",
            {"gstin": gstin}
        )
        score = float(result[0]["score"]) if result and result[0]["score"] else 0.0
        labels.append(1 if score > 0.5 else 0)  # Binary: high-risk (>50%) = 1
    return np.array(labels)
```

**Threshold**: `risk_score > 0.5` (50%) → High-Risk (label = 1), else Low-Risk (label = 0)

### 5.2 Training Process

1. **Feature extraction**: Extract 28 features for all 64 active GSTINs from Neo4j
2. **Label generation**: Bootstrap labels from graph-based risk scores
3. **Train/Test split**: 80/20 stratified split (preserves class distribution)
4. **Model training**: XGBoost fit on training set
5. **Evaluation**: Compute accuracy, precision, recall, F1, AUC-ROC on test set
6. **SHAP computation**: Build TreeExplainer for interpretability

```python
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
model.fit(X_train, y_train)
```

### 5.3 Model Performance

| Metric | Score | Description |
|--------|-------|-------------|
| **Accuracy** | **84.62%** | Overall correct predictions |
| **Precision** | Varies | True positives / (True + False positives) |
| **Recall** | Varies | True positives / (True + False negatives) |
| **F1 Score** | Varies | Harmonic mean of precision and recall |
| **AUC-ROC** | Varies | Area under ROC curve (discrimination ability) |

---

## 6. Risk Scoring

### 6.1 Composite Risk Score Formula

The `CompositeRiskScore` in `risk_scorer.py` uses a weighted formula:

```
Composite Risk = 0.4 × Financial Impact + 0.3 × Probability + 0.3 × Vendor Risk
```

Where each component is on a **0-100 scale**:

#### Financial Impact (40% weight)
| Invoice Value | Impact Score |
|--------------|-------------|
| ≥ ₹50,00,000 (₹50L+) | 100 |
| ≥ ₹10,00,000 (₹10L+) | 85 |
| ≥ ₹5,00,000 (₹5L+) | 70 |
| ≥ ₹1,00,000 (₹1L+) | 55 |
| ≥ ₹50,000 | 40 |
| < ₹50,000 | 25 |

#### Probability (30% weight) — Per Mismatch Type
| Mismatch Type | Probability |
|--------------|------------|
| PHANTOM_INVOICE | 95% |
| CIRCULAR_TRADE | 92% |
| MISSING_IN_GSTR2B | 90% |
| FICTITIOUS_ITC | 88% |
| VALUE_MISMATCH | 75% |
| LATE_FILING | 60% |
| TAX_RATE_MISMATCH | 70% |
| DUPLICATE_INVOICE | 85% |
| CANCELLED_BUT_CLAIMED | 80% |
| REVERSE_CHARGE_EVASION | 78% |
| PLACE_OF_SUPPLY_MISMATCH | 65% |

#### Vendor Risk (30% weight)
- Sourced from the GSTIN node's `risk_score` property in Neo4j
- Pre-computed via graph analytics (PageRank, community detection, etc.)

### 6.2 ML Risk Score Thresholds

```
LOW:      ml_risk_score < 0.3  (30%)
MEDIUM:   0.3 ≤ score < 0.5   (30-50%)
HIGH:     0.5 ≤ score < 0.7   (50-70%)
CRITICAL: score ≥ 0.85        (85%+)
```

---

## 7. SHAP Explainability

### 7.1 How It Works

The system uses **SHAP (SHapley Additive exPlanations)** with a `TreeExplainer` for per-prediction interpretability:

```python
self.explainer = shap.TreeExplainer(self.model)
shap_values = self.explainer.shap_values(features_array)
```

### 7.2 Output Format

For each prediction, the top 8 contributing factors are returned:

```json
{
  "gstin": "29AABCU9603R1ZM",
  "risk_score": 0.87,
  "risk_label": "critical",
  "confidence": 0.91,
  "top_factors": [
    {"feature": "total_mismatches", "impact": 0.342, "value": 12.0},
    {"feature": "has_circular_trade", "impact": 0.218, "value": 1.0},
    {"feature": "critical_mismatches", "impact": 0.156, "value": 4.0},
    {"feature": "itc_to_output_ratio", "impact": 0.134, "value": 3.2},
    {"feature": "mismatch_rate", "impact": 0.098, "value": 0.45},
    {"feature": "pagerank", "impact": 0.067, "value": 0.0342},
    {"feature": "total_itc_at_risk", "impact": 0.054, "value": 2500000},
    {"feature": "avg_risk_score", "impact": 0.041, "value": 78.5}
  ],
  "explanation": "Critical risk: GSTIN 29AABCU... exhibits 12 mismatches with 4 critical alerts. Circular trade pattern detected with ITC ratio of 3.2x. High mismatch rate of 45% and significant PageRank centrality suggest hub role in suspicious network."
}
```

### 7.3 Human-Readable Explanations

The model generates natural language explanations:

```python
explanation = f"{label}: {gstin} exhibits {features['total_mismatches']:.0f} mismatches "
              f"with {features['critical_mismatches']:.0f} critical alerts."
              f" Circular trade {'detected' if features['has_circular_trade'] else 'not detected'}."
              f" ITC ratio: {features['itc_to_output_ratio']:.1f}x."
              f" Mismatch rate: {features['mismatch_rate']*100:.0f}%."
```

---

## 8. Fraud Detection Types

The system detects **11 types** of GST fraud through reconciliation:

| # | Fraud Type | Description | Severity |
|---|-----------|-------------|----------|
| 1 | **PHANTOM_INVOICE** | Invoice exists in seller's GSTR-1 but no corresponding goods/services delivered | CRITICAL |
| 2 | **CIRCULAR_TRADE** | Chain of transactions forming a loop (A→B→C→A) to inflate ITC claims | CRITICAL |
| 3 | **MISSING_IN_GSTR2B** | Invoice in GSTR-1 but not auto-populated in buyer's GSTR-2B | HIGH |
| 4 | **FICTITIOUS_ITC** | ITC claimed on non-existent or fraudulent invoices | CRITICAL |
| 5 | **VALUE_MISMATCH** | Discrepancy in invoice values between seller and buyer filings | MEDIUM-HIGH |
| 6 | **DUPLICATE_INVOICE** | Same invoice number used multiple times for different claims | HIGH |
| 7 | **CANCELLED_BUT_CLAIMED** | ITC claimed on invoices that were cancelled | HIGH |
| 8 | **REVERSE_CHARGE_EVASION** | Failure to pay GST under reverse charge mechanism | MEDIUM |
| 9 | **TAX_RATE_MISMATCH** | Different tax rates applied to same supply by seller and buyer | MEDIUM |
| 10 | **LATE_FILING** | Returns filed after due date, potential for manipulation | LOW-MEDIUM |
| 11 | **PLACE_OF_SUPPLY_MISMATCH** | Incorrect place of supply to evade IGST/SGST | MEDIUM |

---

## 9. Knowledge Graph Schema

### 9.1 Node Types (7 types)

| Node Label | Key Properties | Count |
|-----------|---------------|-------|
| **GSTIN** | gstin_number, trade_name, risk_score, risk_label, pagerank, community_id | 64 |
| **Invoice** | invoice_number, invoice_date, taxable_value, total_tax, total_value | 5000+ |
| **Mismatch** | mismatch_id, mismatch_type, severity, itc_at_risk, composite_risk_score, narrative | 200+ |
| **Return** | return_type (GSTR1/GSTR2B/GSTR3B), return_period, filing_status | 500+ |
| **IRN** | irn_number, generated_date, status | 200+ |
| **EWayBill** | ewb_number, generated_date, valid_until | 100+ |
| **Taxpayer** | legal_name, trade_name, pan, registration_date | 60+ |

### 9.2 Relationship Types

| Relationship | From → To | Description |
|-------------|-----------|-------------|
| `ISSUED_INVOICE` | GSTIN → Invoice | Seller issued this invoice |
| `RECEIVED_INVOICE` | Invoice → GSTIN | Buyer received this invoice |
| `TRANSACTS_WITH` | GSTIN → GSTIN | Trade relationship between entities |
| `FILED_RETURN` | GSTIN → Return | GSTIN filed this GST return |
| `REPORTED_IN` | Invoice → Return | Invoice reported in this return |
| `HAS_IRN` | Invoice → IRN | Invoice has this IRN |
| `HAS_EWB` | Invoice → EWayBill | Invoice has this E-Way Bill |
| `INVOLVES` | Mismatch → Invoice | Mismatch involves this invoice |
| `DETECTED_FOR` | Mismatch → GSTIN | Mismatch detected for this entity |
| `HAS_GSTIN` | Taxpayer → GSTIN | Taxpayer owns this GSTIN |

### 9.3 Graph Analytics (Pre-computed via Neo4j GDS)

| Algorithm | Purpose | Stored Property |
|-----------|---------|----------------|
| **PageRank** | Identify influential/central entities | `GSTIN.pagerank` |
| **Degree Centrality** | Number of direct connections | `GSTIN.degree_centrality` |
| **Betweenness Centrality** | Bridge nodes between clusters | `GSTIN.betweenness_centrality` |
| **Louvain Community Detection** | Group related entities into clusters | `GSTIN.community_id` |
| **Clustering Coefficient** | Local clustering density | `GSTIN.clustering_coefficient` |

---

## 10. Batch Prediction & Neo4j Update

After training, the model can make **batch predictions** for all GSTINs and write results back to Neo4j:

```python
def predict_batch(self):
    """Predict risk for all GSTINs and store in Neo4j."""
    gstins, X, _ = extract_all_features()
    probabilities = self.model.predict_proba(X)[:, 1]  # P(high-risk)
    
    for gstin, prob in zip(gstins, probabilities):
        label = "critical" if prob >= 0.85 else "high" if prob >= 0.7 else \
                "medium" if prob >= 0.5 else "low" if prob >= 0.3 else "very_low"
        
        execute_query("""
            MATCH (g:GSTIN {gstin_number: $gstin})
            SET g.ml_risk_score = $score,
                g.ml_risk_label = $label
        """, {"gstin": gstin, "score": float(prob), "label": label})
```

---

## 11. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /api/v1/risk/train` | POST | Train the XGBoost model on all GSTINs |
| `GET /api/v1/risk/vendor/{gstin}` | GET | Get risk details for a specific vendor |
| `GET /api/v1/risk/heatmap` | GET | Risk heatmap across all entities |
| `GET /api/v1/risk/communities` | GET | Risk communities and clusters |

---

## 12. Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| ML Framework | XGBoost | Latest |
| Explainability | SHAP | Latest |
| Graph Database | Neo4j Aura | 5.x |
| Backend API | FastAPI | 0.100+ |
| Feature Engineering | NumPy | Latest |
| Runtime | Python | 3.12 |
| Frontend Visualization | Recharts + vis-network | React 18 |

---

## 13. Model Limitations & Future Work

### Current Limitations
1. **Bootstrap labels**: Labels derived from unsupervised risk scores — no verified ground truth
2. **Small dataset**: Only 64 GSTINs — model may overfit
3. **Static features**: Month-over-month growth simplified to 0
4. **Filing delay**: Average filing delay not computed from actual dates
5. **Single-model**: No ensemble or model comparison

### Future Improvements
1. **Active learning**: Incorporate auditor feedback to refine labels
2. **Temporal features**: Time-series analysis of transaction patterns
3. **Graph Neural Networks**: Use GNNs for end-to-end graph-based prediction
4. **Anomaly detection**: Unsupervised methods (Isolation Forest, Autoencoders) for novel fraud
5. **Real-time scoring**: Stream processing for live fraud detection
6. **Multi-class**: Predict specific fraud type instead of binary risk

---

*Generated for GST Reconciliation Engine — Knowledge Graph Powered Fraud Detection System*
