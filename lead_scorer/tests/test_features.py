import numpy as np

from lead_scorer.features import FEATURE_NAMES, extract_features


def test_extract_features_normal_lead():
    lead = {
        "google_rating": 4.5,
        "google_reviews": 100,
        "website": "https://example.com",
        "phone": "+1-555-1234",
        "intel_json": {"types": ["real_estate_agency"]},
    }
    feats = extract_features(lead)
    assert len(feats) == len(FEATURE_NAMES)
    assert feats[0] == 4.5
    assert feats[1] == 1.0
    assert feats[2] == float(np.log1p(100))
    assert feats[3] == 1.0
    assert feats[4] == 1.0
    assert feats[5] == 4.5 * float(np.log1p(100))
    assert feats[6] == 1.0
    assert feats[7] == 0.0


def test_extract_features_null_rating():
    lead = {
        "google_rating": None,
        "google_reviews": 0,
        "website": None,
        "phone": None,
        "intel_json": {},
    }
    feats = extract_features(lead)
    i = FEATURE_NAMES.index
    assert feats[i("google_rating")] == 0.0
    assert feats[i("has_rating")] == 0.0
    assert feats[i("rating_x_log_reviews")] == 0.0


def test_extract_features_nan_rating():
    lead = {"google_rating": float("nan"), "google_reviews": 10}
    feats = extract_features(lead)
    i = FEATURE_NAMES.index
    assert feats[i("has_rating")] == 0.0
    assert feats[i("google_rating")] == 0.0


def test_extract_features_no_website():
    lead = {"google_rating": 4.0, "website": None, "intel_json": {"types": []}}
    feats = extract_features(lead)
    assert feats[FEATURE_NAMES.index("has_website")] == 0.0


def test_extract_features_no_phone():
    lead = {"google_rating": 4.0, "phone": None, "intel_json": {"types": []}}
    feats = extract_features(lead)
    assert feats[FEATURE_NAMES.index("has_phone")] == 0.0


def test_extract_features_empty_intel():
    lead = {"google_rating": 4.0, "intel_json": {}}
    feats = extract_features(lead)
    assert feats[FEATURE_NAMES.index("is_real_estate")] == 0.0
    assert feats[FEATURE_NAMES.index("is_insurance")] == 0.0


def test_extract_features_missing_intel_key():
    lead = {"google_rating": 4.0, "google_reviews": 5}
    feats = extract_features(lead)
    assert len(feats) == len(FEATURE_NAMES)
    assert feats[FEATURE_NAMES.index("is_real_estate")] == 0.0


def test_extract_features_all_nulls():
    assert extract_features({}) == [0.0] * len(FEATURE_NAMES)
