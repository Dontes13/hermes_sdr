"""Production lead scorer.

Usage:
    from lead_scorer.score import score_lead, score_leads

    prob = score_lead(lead_row)           # single lead → float
    probs = score_leads([lead1, lead2])   # batch → list[float]
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

from .features import extract_features

_artifact = None
_MODEL_PATH = Path(__file__).parent / "models" / "lead_scorer.joblib"


def _load() -> dict:
    global _artifact
    if _artifact is None:
        _artifact = joblib.load(_MODEL_PATH)
    return _artifact


def _predict_proba(model, X: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    # Perceptron fallback — sigmoid of decision function.
    z = model.decision_function(X)
    return 1.0 / (1.0 + np.exp(-z))


def score_lead(lead: dict) -> float:
    """P(reply) for a single lead. Returns float in [0, 1]."""
    art = _load()
    features = np.array([extract_features(lead)])
    scaled = art["scaler"].transform(features)
    return float(_predict_proba(art["model"], scaled)[0])


def score_leads(leads: list[dict]) -> list[float]:
    """P(reply) for a batch of leads. Same order as input."""
    if not leads:
        return []
    art = _load()
    features = np.array([extract_features(lead) for lead in leads])
    scaled = art["scaler"].transform(features)
    return _predict_proba(art["model"], scaled).tolist()
