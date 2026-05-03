"""Train 4 classifiers on synthetic lead data and persist the best one.

Models: Perceptron, DecisionTree, LogisticRegression, RandomForest.
Selection: best AUC on the held-out test set.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, Perceptron
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.tree import DecisionTreeClassifier

from .features import FEATURE_NAMES, extract_features
from .generate import TRUE_COEFFICIENTS, load_csv

HERE = Path(__file__).parent
DATA_PATH = HERE / "data" / "leads_synthetic.csv"
MODELS_DIR = HERE / "models"


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def _proba(model, X: np.ndarray) -> np.ndarray:
    """Positive-class probability. Perceptron has no predict_proba — use
    decision_function passed through a sigmoid so we can compute AUC."""
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    return _sigmoid(model.decision_function(X))


def _metrics(model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    probs = _proba(model, X_test)
    preds = (probs >= 0.5).astype(int)
    return {
        "auc": roc_auc_score(y_test, probs),
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds, zero_division=0),
        "recall": recall_score(y_test, preds, zero_division=0),
        "f1": f1_score(y_test, preds, zero_division=0),
    }


def train() -> dict:
    df = load_csv(DATA_PATH)
    X = np.array([extract_features(r) for r in df.to_dict(orient="records")])
    y = df["replied"].to_numpy(dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    scaler = MinMaxScaler().fit(X_train)
    X_train_s = scaler.transform(X_train)
    X_test_s = scaler.transform(X_test)

    models = {
        "Perceptron": Perceptron(max_iter=1000, eta0=0.1, random_state=42),
        "DecisionTree": DecisionTreeClassifier(max_depth=5, random_state=42),
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
        "RandomForest": RandomForestClassifier(
            n_estimators=100, max_depth=5, random_state=42
        ),
    }

    results: dict[str, dict] = {}
    for name, model in models.items():
        model.fit(X_train_s, y_train)
        results[name] = {"model": model, **_metrics(model, X_test_s, y_test)}

    table = pd.DataFrame(
        [
            {
                "model": name,
                "auc": r["auc"],
                "accuracy": r["accuracy"],
                "precision": r["precision"],
                "recall": r["recall"],
                "f1": r["f1"],
            }
            for name, r in results.items()
        ]
    ).round(4)
    print(table.to_string(index=False))

    # Acceptance checks
    lr_auc = results["LogisticRegression"]["auc"]
    assert lr_auc > 0.75, f"LogisticRegression AUC {lr_auc:.3f} below 0.75"

    # Coefficient recovery: rescale LR coefficients back to original feature scale.
    # MinMaxScaler: x_scaled = (x - min) / (max - min). So coefficient on the
    # original scale is w_scaled / (max - min).
    lr = results["LogisticRegression"]["model"]
    feat_range = scaler.data_max_ - scaler.data_min_
    feat_range = np.where(feat_range == 0, 1.0, feat_range)
    learned = lr.coef_[0] / feat_range
    recovery_errors: dict[str, float] = {
        name: abs(learned[i] - TRUE_COEFFICIENTS[name])
        for i, name in enumerate(FEATURE_NAMES)
    }

    # Noise-feature sanity check: is_insurance should land near zero.
    insurance_idx = FEATURE_NAMES.index("is_insurance")
    assert abs(learned[insurance_idx]) < 0.2, (
        f"is_insurance (noise feature) coefficient {learned[insurance_idx]:.3f} too large"
    )

    # Signs on informative features should match the generative model.
    for name in ("google_rating", "log_reviews", "has_website", "has_rating"):
        idx = FEATURE_NAMES.index(name)
        true = TRUE_COEFFICIENTS[name]
        assert np.sign(learned[idx]) == np.sign(true) or abs(learned[idx]) < 0.05, (
            f"Sign mismatch on {name}: true={true}, learned={learned[idx]:.3f}"
        )

    best_name = max(results, key=lambda n: results[n]["auc"])
    best = results[best_name]

    MODELS_DIR.mkdir(exist_ok=True)
    artifact = {
        "model": best["model"],
        "scaler": scaler,
        "feature_names": FEATURE_NAMES,
        "threshold": 0.5,
        "auc": float(best["auc"]),
        "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "model_name": best_name,
    }
    joblib.dump(artifact, MODELS_DIR / "lead_scorer.joblib")

    # Persist everything evaluate.py needs so it doesn't retrain.
    joblib.dump(
        {
            "results": results,
            "scaler": scaler,
            "X_test": X_test,
            "X_test_s": X_test_s,
            "y_test": y_test,
            "feature_names": FEATURE_NAMES,
            "learned_lr_coefs_original_scale": learned.tolist(),
            "lr_intercept": float(lr.intercept_[0]),
            "recovery_errors": recovery_errors,
        },
        MODELS_DIR / "all_metrics.joblib",
    )

    print(f"\nbest model: {best_name} (AUC={best['auc']:.4f})")
    print(f"saved: {MODELS_DIR / 'lead_scorer.joblib'}")
    return artifact


def main() -> None:
    train()


if __name__ == "__main__":
    main()
