"""Feature extraction for lead scoring.

Every feature must be available at prospect time (Google Places data only).
No enrichment data allowed — the whole point is scoring BEFORE we spend
money enriching.
"""

from __future__ import annotations

import numpy as np

FEATURE_NAMES = [
    "google_rating",
    "has_rating",
    "log_reviews",
    "has_website",
    "has_phone",
    "rating_x_log_reviews",
    "is_real_estate",
    "is_insurance",
]


def extract_features(lead: dict) -> list[float]:
    """Lead dict → fixed-length float vector in FEATURE_NAMES order.

    Accepts Supabase rows and synthetic dicts. Null-safe on every field.
    """
    intel = lead.get("intel_json") or {}
    types = intel.get("types") or []

    rating_raw = lead.get("google_rating")
    rating_present = rating_raw is not None and not (
        isinstance(rating_raw, float) and np.isnan(rating_raw)
    )
    rating = float(rating_raw) if rating_present else 0.0
    has_rating = 1.0 if rating_present else 0.0

    reviews_raw = lead.get("google_reviews")
    if reviews_raw is None or (isinstance(reviews_raw, float) and np.isnan(reviews_raw)):
        reviews = 0
    else:
        reviews = int(reviews_raw)
    log_reviews = float(np.log1p(reviews))

    return [
        rating,
        has_rating,
        log_reviews,
        _truthy_str(lead.get("website")),
        _truthy_str(lead.get("phone")),
        rating * log_reviews,
        1.0 if "real_estate_agency" in types else 0.0,
        1.0 if "insurance_agency" in types else 0.0,
    ]


def _truthy_str(v) -> float:
    """1.0 if v is a non-empty string, else 0.0. Treats None and NaN as absent."""
    if v is None:
        return 0.0
    if isinstance(v, float) and np.isnan(v):
        return 0.0
    return 1.0 if str(v).strip() else 0.0
