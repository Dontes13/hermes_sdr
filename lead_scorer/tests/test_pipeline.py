from pathlib import Path

import joblib

from lead_scorer.score import score_leads

MODEL_PATH = Path(__file__).parent.parent / "models" / "lead_scorer.joblib"


def test_model_artifact_has_expected_keys():
    art = joblib.load(MODEL_PATH)
    for key in ("model", "scaler", "feature_names", "threshold", "auc", "trained_at"):
        assert key in art
    assert art["auc"] > 0.75


def test_pipeline_ranks_quality_correctly():
    leads = [
        {
            "google_rating": 4.9,
            "google_reviews": 500,
            "website": "https://x.com",
            "phone": "y",
            "intel_json": {"types": ["real_estate_agency"]},
        },
        {
            "google_rating": 4.2,
            "google_reviews": 50,
            "website": "https://x.com",
            "phone": "y",
            "intel_json": {"types": ["real_estate_agency"]},
        },
        {
            "google_rating": 3.5,
            "google_reviews": 5,
            "website": None,
            "phone": "y",
            "intel_json": {"types": []},
        },
        {
            "google_rating": None,
            "google_reviews": 0,
            "website": None,
            "phone": None,
            "intel_json": {"types": []},
        },
    ]
    scores = score_leads(leads)
    assert scores[0] > scores[-1]
    assert all(0.0 <= s <= 1.0 for s in scores)
