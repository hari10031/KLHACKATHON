"""
XGBoost vendor risk prediction model with SHAP explainability.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

import xgboost as xgb
import shap
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report,
)

from app.ml.feature_extraction import extract_features, extract_all_features, FEATURE_NAMES
from app.database import execute_query


MODEL_DIR = Path("models")
MODEL_PATH = MODEL_DIR / "vendor_risk_model.json"
METADATA_PATH = MODEL_DIR / "model_metadata.json"

# Risk label thresholds (based on composite metric from graph signals)
RISK_THRESHOLDS = {"low": 0.3, "medium": 0.5, "high": 0.7}


class VendorRiskModel:
    """XGBoost classifier for vendor compliance risk with SHAP explanations."""

    def __init__(self):
        self.model: Optional[xgb.XGBClassifier] = None
        self.explainer: Optional[shap.TreeExplainer] = None
        self._load_model()

    def _load_model(self):
        if MODEL_PATH.exists():
            self.model = xgb.XGBClassifier()
            self.model.load_model(str(MODEL_PATH))
            self.explainer = shap.TreeExplainer(self.model)
            logger.info("Loaded vendor risk model from disk.")

    def train(self) -> Dict:
        """Train XGBoost on extracted graph features with synthetic labels."""
        gstins, X, feature_names = extract_all_features()

        if len(gstins) < 10:
            raise ValueError(f"Too few GSTINs ({len(gstins)}) for training. Need ≥10.")

        # Generate training labels from graph risk scores (unsupervised → supervised bootstrap)
        y = self._generate_labels(gstins)

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None
        )

        # XGBoost configuration
        self.model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            scale_pos_weight=max(1, sum(y == 0) / max(sum(y == 1), 1)),
            objective="binary:logistic",
            eval_metric="auc",
            random_state=42,
            use_label_encoder=False,
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # Evaluate
        y_pred = self.model.predict(X_test)
        y_prob = self.model.predict_proba(X_test)[:, 1]

        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "f1": float(f1_score(y_test, y_pred, zero_division=0)),
            "auc_roc": float(roc_auc_score(y_test, y_prob)) if len(set(y_test)) > 1 else 0.0,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "positive_rate": float(sum(y) / len(y)),
        }

        # Feature importance
        importance = dict(zip(feature_names, [float(v) for v in self.model.feature_importances_]))
        metrics["feature_importance"] = dict(sorted(importance.items(), key=lambda x: -x[1])[:10])

        # Save model
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(MODEL_PATH))
        with open(METADATA_PATH, "w") as f:
            json.dump({"metrics": metrics, "features": feature_names}, f, indent=2)

        # Initialize SHAP
        self.explainer = shap.TreeExplainer(self.model)

        logger.info(f"Model trained: AUC={metrics['auc_roc']:.3f}, F1={metrics['f1']:.3f}")
        return metrics

    def predict_single(self, gstin: str) -> Dict:
        """Predict risk for a single GSTIN with SHAP explanation."""
        if self.model is None:
            raise FileNotFoundError("Model not trained.")

        features = extract_features(gstin)
        X = np.array([[features.get(name, 0.0) for name in FEATURE_NAMES]])

        prob = float(self.model.predict_proba(X)[0, 1])
        label = self._score_to_label(prob)

        # SHAP explanation
        shap_values = self.explainer.shap_values(X)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # positive class

        top_factors = []
        shap_flat = shap_values.flatten()
        sorted_idx = np.argsort(np.abs(shap_flat))[::-1][:8]
        for idx in sorted_idx:
            top_factors.append({
                "feature": FEATURE_NAMES[idx],
                "value": float(X[0, idx]),
                "shap_contribution": float(shap_flat[idx]),
                "direction": "increases" if shap_flat[idx] > 0 else "decreases",
            })

        return {
            "gstin": gstin,
            "risk_score": round(prob, 4),
            "risk_label": label,
            "confidence": round(max(prob, 1 - prob), 4),
            "top_factors": top_factors,
            "explanation": self._generate_explanation(gstin, top_factors, prob),
        }

    def predict_batch(self) -> List[Dict]:
        """Predict risk for all GSTINs and store results."""
        if self.model is None:
            raise FileNotFoundError("Model not trained.")

        gstins, X, _ = extract_all_features()
        probs = self.model.predict_proba(X)[:, 1]

        results = []
        for gstin, prob in zip(gstins, probs):
            label = self._score_to_label(float(prob))
            results.append({"gstin": gstin, "risk_score": float(prob), "risk_label": label})

            # Store back to Neo4j
            execute_query("""
                MATCH (g:GSTIN {gstin_number: $gstin})
                SET g.ml_risk_score = $score, g.ml_risk_label = $label
            """, {"gstin": gstin, "score": float(prob), "label": label})

        logger.info(f"Batch prediction complete for {len(results)} GSTINs.")
        return results

    def _generate_labels(self, gstins: List[str]) -> np.ndarray:
        """Generate binary labels from graph risk scores (high-risk = 1)."""
        labels = []
        for gstin in gstins:
            result = execute_query("""
                MATCH (g:GSTIN {gstin_number: $gstin})
                RETURN COALESCE(g.risk_score, 0) AS score
            """, {"gstin": gstin})
            score = float(result[0]["score"]) if result else 0.0
            labels.append(1 if score > 0.5 else 0)
        return np.array(labels)

    @staticmethod
    def _score_to_label(score: float) -> str:
        if score > RISK_THRESHOLDS["high"]:
            return "critical" if score > 0.85 else "high"
        if score > RISK_THRESHOLDS["medium"]:
            return "medium"
        return "low"

    @staticmethod
    def _generate_explanation(gstin: str, factors: List[Dict], score: float) -> str:
        label = "HIGH RISK" if score > 0.5 else "LOW RISK"
        top3 = factors[:3]
        reasons = []
        for f in top3:
            direction = "↑" if f["direction"] == "increases" else "↓"
            reasons.append(f"{f['feature'].replace('_', ' ')} ({direction})")
        return (
            f"GSTIN {gstin} is classified as {label} (score: {score:.2%}). "
            f"Key contributing factors: {', '.join(reasons)}."
        )
