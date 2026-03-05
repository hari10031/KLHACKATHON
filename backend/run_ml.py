"""
XGBoost Vendor Risk Prediction — Dual Model (Classifier + Regressor)
Trains on locally exported dataset with data augmentation for small datasets.
"""
import sys, os, json, csv, random
sys.path.insert(0, ".")
os.environ["LOGURU_LEVEL"] = "WARNING"

import numpy as np
import xgboost as xgb
import shap
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix,
    mean_absolute_error, r2_score
)
from sklearn.preprocessing import StandardScaler
from pathlib import Path

print("=" * 65)
print("  GST RECONCILIATION ENGINE - XGBoost Vendor Risk Model")
print("=" * 65)
print()

DATASET_DIR = Path(__file__).parent.parent / "dataset"

# ── 1. Load exported dataset ─────────────────────────────────────
print("[1/6] Loading dataset from local CSV files...")

gstins_data = {}
with open(DATASET_DIR / "risk_scores.csv", "r") as f:
    for row in csv.DictReader(f):
        gstins_data[row["gstin"]] = row

invoices = []
with open(DATASET_DIR / "invoices.csv", "r") as f:
    for row in csv.DictReader(f):
        invoices.append(row)

mismatches = []
with open(DATASET_DIR / "mismatches.csv", "r") as f:
    for row in csv.DictReader(f):
        mismatches.append(row)

returns_list = []
with open(DATASET_DIR / "returns.csv", "r") as f:
    for row in csv.DictReader(f):
        returns_list.append(row)

print(f"       {len(gstins_data)} GSTINs | {len(invoices)} invoices | {len(mismatches)} mismatches | {len(returns_list)} returns")

# ── 2. Feature engineering ────────────────────────────────────────
print("[2/6] Engineering features...")

# Aggregate stats
issued_stats = {}
received_stats = {}
for inv in invoices:
    seller = inv.get("seller_gstin", "")
    buyer = inv.get("buyer_gstin", "")
    val = float(inv.get("total_value", 0) or 0)
    
    if seller:
        if seller not in issued_stats:
            issued_stats[seller] = {"count": 0, "total_val": 0.0, "max_val": 0.0, "values": [], "buyers": set()}
        issued_stats[seller]["count"] += 1
        issued_stats[seller]["total_val"] += val
        issued_stats[seller]["max_val"] = max(issued_stats[seller]["max_val"], val)
        issued_stats[seller]["values"].append(val)
        if buyer:
            issued_stats[seller]["buyers"].add(buyer)
    
    if buyer:
        if buyer not in received_stats:
            received_stats[buyer] = {"count": 0, "total_val": 0.0}
        received_stats[buyer]["count"] += 1
        received_stats[buyer]["total_val"] += val

mm_stats = {}
for mm in mismatches:
    for g in [mm.get("seller_gstin", ""), mm.get("buyer_gstin", "")]:
        if not g:
            continue
        if g not in mm_stats:
            mm_stats[g] = {"total": 0, "critical": 0, "high": 0, "medium": 0,
                           "itc_risk": 0.0, "risk_scores": [], "circular": 0, "phantom": 0}
        mm_stats[g]["total"] += 1
        sev = mm.get("severity", "").upper()
        if sev == "CRITICAL": mm_stats[g]["critical"] += 1
        elif sev == "HIGH": mm_stats[g]["high"] += 1
        elif sev == "MEDIUM": mm_stats[g]["medium"] += 1
        itc = float(mm.get("itc_risk", mm.get("itc_at_risk", 0)) or 0)
        mm_stats[g]["itc_risk"] += itc
        rs = float(mm.get("risk_score", mm.get("composite_risk_score", 0)) or 0)
        mm_stats[g]["risk_scores"].append(rs)
        mtype = mm.get("type", mm.get("mismatch_type", ""))
        if "CIRCULAR" in mtype.upper(): mm_stats[g]["circular"] += 1
        if "PHANTOM" in mtype.upper(): mm_stats[g]["phantom"] += 1

filing_stats = {}
for ret in returns_list:
    g = ret.get("gstin", "")
    rtype = ret.get("return_type", "")
    if g:
        if g not in filing_stats:
            filing_stats[g] = {"gstr1": 0, "gstr3b": 0, "gstr2b": 0, "total": 0}
        filing_stats[g]["total"] += 1
        if "1" in rtype and "2" not in rtype: filing_stats[g]["gstr1"] += 1
        elif "3B" in rtype.upper() or "3b" in rtype: filing_stats[g]["gstr3b"] += 1
        elif "2B" in rtype.upper() or "2b" in rtype: filing_stats[g]["gstr2b"] += 1

FEATURE_NAMES = [
    "invoices_issued", "invoices_received", "value_issued", "value_received",
    "avg_invoice_value", "max_invoice_value", "counterparties", "invoice_stddev",
    "total_mismatches", "critical_mismatches", "high_mismatches", "medium_mismatches",
    "mismatch_rate", "itc_at_risk", "avg_mismatch_risk", "has_circular_trade", "has_phantom",
    "pagerank", "degree_centrality", "betweenness_centrality",
    "clustering_coefficient", "community_id",
    "gstr1_filings", "gstr3b_filings",
    "value_ratio", "inv_concentration",
    "filing_completeness", "mismatch_severity_score"
]

X_orig = []
y_orig = []
y_reg = []  # continuous risk scores for regression

for gstin, gd in gstins_data.items():
    iss = issued_stats.get(gstin, {})
    rec = received_stats.get(gstin, {})
    mm = mm_stats.get(gstin, {})
    fil = filing_stats.get(gstin, {})

    inv_issued_cnt = float(iss.get("count", 0))
    inv_received_cnt = float(rec.get("count", 0))
    val_issued = float(iss.get("total_val", 0))
    val_received = float(rec.get("total_val", 0))
    total_inv = inv_issued_cnt + inv_received_cnt

    values = iss.get("values", [])
    avg_val = np.mean(values) if values else 0.0
    stddev = np.std(values) if len(values) > 1 else 0.0

    # Computed features
    mismatch_severity = (mm.get("critical", 0) * 4 + mm.get("high", 0) * 3 + 
                         mm.get("medium", 0) * 2) / max(mm.get("total", 1), 1)
    filing_complete = (fil.get("gstr1", 0) + fil.get("gstr3b", 0)) / max(fil.get("total", 1), 1)

    features = [
        inv_issued_cnt, inv_received_cnt, val_issued, val_received,
        avg_val, float(iss.get("max_val", 0)),
        float(len(iss.get("buyers", set()))), stddev,
        float(mm.get("total", 0)), float(mm.get("critical", 0)),
        float(mm.get("high", 0)), float(mm.get("medium", 0)),
        float(mm.get("total", 0)) / max(total_inv, 1),
        float(mm.get("itc_risk", 0)),
        np.mean(mm.get("risk_scores", [0])),
        1.0 if mm.get("circular", 0) > 0 else 0.0,
        1.0 if mm.get("phantom", 0) > 0 else 0.0,
        float(gd.get("pagerank", 0) or 0),
        float(gd.get("degree", gd.get("degree_centrality", 0)) or 0),
        float(gd.get("betweenness", gd.get("betweenness_centrality", 0)) or 0),
        float(gd.get("clustering_coefficient", gd.get("clustering", 0)) or 0),
        float(gd.get("community", gd.get("community_id", 0)) or 0),
        float(fil.get("gstr1", 0)), float(fil.get("gstr3b", 0)),
        val_received / max(val_issued, 1),
        float(iss.get("max_val", 0)) / max(avg_val, 0.01),
        filing_complete, mismatch_severity,
    ]

    score = float(gd.get("risk_score", 0) or 0)
    label = 1 if score > 55 else 0

    X_orig.append(features)
    y_orig.append(label)
    y_reg.append(score / 100.0)

X_orig = np.array(X_orig)
y_orig = np.array(y_orig)
y_reg = np.array(y_reg)

print(f"       Original: {X_orig.shape[0]} samples x {X_orig.shape[1]} features")
print(f"       Classes: {sum(y_orig==1)} HIGH-RISK vs {sum(y_orig==0)} LOW-RISK")

# ── 3. Data augmentation (SMOTE-like + noise injection) ───────────
print("[3/6] Augmenting dataset with synthetic samples...")

np.random.seed(42)

def augment_data(X, y, y_scores, multiplier=5):
    """Generate synthetic samples with gaussian noise for each class."""
    X_aug = list(X)
    y_aug = list(y)
    yr_aug = list(y_scores)
    
    for cls in [0, 1]:
        idx = np.where(y == cls)[0]
        X_cls = X[idx]
        yr_cls = y_scores[idx]
        
        for _ in range(multiplier):
            for i in range(len(X_cls)):
                # Add gaussian noise (5-15% of feature value)
                noise_scale = np.random.uniform(0.05, 0.15)
                noise = np.random.randn(X_cls.shape[1]) * noise_scale
                new_sample = X_cls[i] * (1 + noise)
                new_sample = np.maximum(new_sample, 0)  # keep non-negative
                
                # Also interpolate between random pairs (SMOTE-like)
                j = np.random.randint(len(X_cls))
                alpha = np.random.uniform(0.2, 0.8)
                interpolated = X_cls[i] * alpha + X_cls[j] * (1 - alpha)
                
                X_aug.append(new_sample)
                y_aug.append(cls)
                yr_aug.append(yr_cls[i] + np.random.normal(0, 0.02))
                
                X_aug.append(interpolated)
                y_aug.append(cls)
                yr_aug.append(yr_cls[i] * alpha + yr_cls[j] * (1 - alpha))
    
    return np.array(X_aug), np.array(y_aug), np.array(yr_aug)

X_aug, y_aug, yr_aug = augment_data(X_orig, y_orig, y_reg, multiplier=5)
yr_aug = np.clip(yr_aug, 0, 1)

print(f"       Augmented: {X_aug.shape[0]} samples ({sum(y_aug==1)} HIGH / {sum(y_aug==0)} LOW)")

# ── 4. Train classifier ─────────────────────────────────────────
print("[4/6] Training XGBoost classifier...")

# Scale features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_aug)

X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y_aug, test_size=0.2, random_state=42, stratify=y_aug
)

clf = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=5,
    learning_rate=0.08,
    subsample=0.85,
    colsample_bytree=0.85,
    min_child_weight=2,
    gamma=0.05,
    reg_alpha=0.1,
    reg_lambda=1.5,
    scale_pos_weight=max(1, sum(y_train == 0) / max(sum(y_train == 1), 1)),
    objective="binary:logistic",
    eval_metric="auc",
    random_state=42,
)

clf.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

# ── 5. Evaluate ──────────────────────────────────────────────────
print("[5/6] Evaluating model performance...")
print()

y_pred = clf.predict(X_test)
y_prob = clf.predict_proba(X_test)[:, 1]

acc = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, zero_division=0)
rec = recall_score(y_test, y_pred, zero_division=0)
f1 = f1_score(y_test, y_pred, zero_division=0)
auc = roc_auc_score(y_test, y_prob) if len(set(y_test)) > 1 else 0.0

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_acc = cross_val_score(clf, X_scaled, y_aug, cv=cv, scoring="accuracy")
cv_f1 = cross_val_score(clf, X_scaled, y_aug, cv=cv, scoring="f1")
cv_auc = cross_val_score(clf, X_scaled, y_aug, cv=cv, scoring="roc_auc")

# Also train regressor for risk score prediction
reg = xgb.XGBRegressor(
    n_estimators=200, max_depth=5, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8, random_state=42,
)
Xr_train, Xr_test, yr_train, yr_test = train_test_split(
    X_scaled, yr_aug, test_size=0.2, random_state=42
)
reg.fit(Xr_train, yr_train, eval_set=[(Xr_test, yr_test)], verbose=False)
yr_pred = reg.predict(Xr_test)
mae = mean_absolute_error(yr_test, yr_pred)
r2 = r2_score(yr_test, yr_pred)

print("=" * 65)
print("         CLASSIFICATION MODEL PERFORMANCE")
print("=" * 65)
print()
print(f"  {'Metric':<30} {'Score':>10}  {'Bar'}")
print(f"  {'-'*30} {'-'*10}  {'-'*25}")
print(f"  {'Accuracy':<30} {acc*100:>9.2f}%  {'#' * int(acc*25)}")
print(f"  {'Precision':<30} {prec*100:>9.2f}%  {'#' * int(prec*25)}")
print(f"  {'Recall':<30} {rec*100:>9.2f}%  {'#' * int(rec*25)}")
print(f"  {'F1 Score':<30} {f1*100:>9.2f}%  {'#' * int(f1*25)}")
print(f"  {'AUC-ROC':<30} {auc*100:>9.2f}%  {'#' * int(auc*25)}")
print()
print(f"  {'Cross-Val Accuracy (5-Fold)':<30} {cv_acc.mean()*100:>9.2f}%  +/- {cv_acc.std()*100:.2f}%")
print(f"  {'Cross-Val F1 (5-Fold)':<30} {cv_f1.mean()*100:>9.2f}%  +/- {cv_f1.std()*100:.2f}%")
print(f"  {'Cross-Val AUC (5-Fold)':<30} {cv_auc.mean()*100:>9.2f}%  +/- {cv_auc.std()*100:.2f}%")
print()
print(f"  {'Training Samples':<30} {len(X_train):>10}")
print(f"  {'Testing Samples':<30} {len(X_test):>10}")
print(f"  {'Original Dataset Size':<30} {len(X_orig):>10}")
print(f"  {'Augmented Dataset Size':<30} {len(X_aug):>10}")
print(f"  {'Features':<30} {len(FEATURE_NAMES):>10}")
print()

# Confusion Matrix
cm = confusion_matrix(y_test, y_pred)
print("-" * 65)
print("  CONFUSION MATRIX")
print("-" * 65)
if cm.shape == (2, 2):
    print(f"                        Predicted LOW   Predicted HIGH")
    print(f"  Actual LOW            {cm[0][0]:>10}     {cm[0][1]:>10}")
    print(f"  Actual HIGH           {cm[1][0]:>10}     {cm[1][1]:>10}")
    tn, fp, fn, tp = cm.ravel()
    print(f"\n  True Positives: {tp}  |  True Negatives: {tn}")
    print(f"  False Positives: {fp} |  False Negatives: {fn}")
else:
    print(f"  {cm}")
print()

print("-" * 65)
print("  CLASSIFICATION REPORT")
print("-" * 65)
print(classification_report(y_test, y_pred, target_names=["LOW RISK", "HIGH RISK"], zero_division=0))

# Regression results
print("=" * 65)
print("         REGRESSION MODEL (Risk Score Prediction)")
print("=" * 65)
print()
print(f"  {'Mean Absolute Error':<30} {mae*100:>9.2f}%")
print(f"  {'R-squared (R2)':<30} {r2:>9.4f}")
print(f"  {'Prediction Accuracy (1-MAE)':<30} {(1-mae)*100:>9.2f}%")
print()

# Feature importance
print("-" * 65)
print("  TOP 10 FEATURE IMPORTANCES (Classifier)")
print("-" * 65)
importance = dict(zip(FEATURE_NAMES, [float(v) for v in clf.feature_importances_]))
sorted_imp = sorted(importance.items(), key=lambda x: -x[1])[:10]
max_imp = sorted_imp[0][1] if sorted_imp else 1
for feat, imp in sorted_imp:
    bar = "#" * int(imp / max_imp * 30)
    print(f"  {feat:<28} {imp:.4f}  {bar}")
print()

# ── 6. Save model ────────────────────────────────────────────────
print("[6/6] Saving models...")
model_dir = Path("models")
model_dir.mkdir(parents=True, exist_ok=True)
clf.save_model(str(model_dir / "vendor_risk_model.json"))
reg.save_model(str(model_dir / "vendor_risk_regressor.json"))

metadata = {
    "classifier": {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "auc_roc": round(auc, 4),
        "cv_accuracy": round(cv_acc.mean(), 4),
        "cv_f1": round(cv_f1.mean(), 4),
        "cv_auc": round(cv_auc.mean(), 4),
    },
    "regressor": {
        "mae": round(mae, 4),
        "r2": round(r2, 4),
    },
    "dataset": {
        "original_size": len(X_orig),
        "augmented_size": len(X_aug),
        "train_size": len(X_train),
        "test_size": len(X_test),
    },
    "features": FEATURE_NAMES,
    "feature_importance": {k: round(v, 4) for k, v in sorted_imp},
}
with open(model_dir / "model_metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

explainer = shap.TreeExplainer(clf)
shap_values = explainer.shap_values(X_test[:10])

print()
print("=" * 65)
print(f"  Classifier saved  -> models/vendor_risk_model.json")
print(f"  Regressor saved   -> models/vendor_risk_regressor.json")
print(f"  Metadata saved    -> models/model_metadata.json")
print(f"  SHAP explainer initialized for {len(FEATURE_NAMES)} features")
print("=" * 65)
print()
print("  Training complete!")
