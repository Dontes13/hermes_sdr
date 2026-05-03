"""Synthetic lead dataset generator.

Labels come from a known logistic generative model so we can later verify
that the trained logistic regression recovers the true coefficients.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, extract_features

TRUE_COEFFICIENTS: dict[str, float] = {
    # Intercept tuned to -8.0 (spec said -3.5) so the base reply rate lands in
    # the target 12–22% range given the actual raw feature magnitudes.
    "intercept": -8.8,
    "google_rating": 0.6,
    "has_rating": 0.4,
    "log_reviews": 0.35,
    "has_website": 0.8,
    "has_phone": 0.2,
    "rating_x_log_reviews": 0.15,
    "is_real_estate": 0.3,
    "is_insurance": 0.0,
}

CITIES = [
    ("Miami", 0.20),
    ("Orlando", 0.15),
    ("Tampa", 0.15),
    ("Jacksonville", 0.12),
    ("Fort Lauderdale", 0.10),
    ("St. Petersburg", 0.10),
    ("Tallahassee", 0.09),
    ("Naples", 0.09),
]

TYPE_COMBOS = [
    (["real_estate_agency"], 0.50),
    (["insurance_agency"], 0.15),
    (["real_estate_agency", "finance"], 0.20),
    (["point_of_interest", "establishment"], 0.15),
]


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def generate(n: int = 1000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    rating_missing = rng.random(n) < 0.10
    rating_raw = rng.normal(4.2, 0.5, n).clip(1.0, 5.0)
    rating = np.where(rating_missing, np.nan, rating_raw)

    reviews_raw = rng.lognormal(3.0, 1.2, n).astype(int)
    reviews = np.where(rating_missing, 0, reviews_raw)

    has_website = rng.random(n) < 0.75
    has_phone = rng.random(n) < 0.85

    city_labels = [c[0] for c in CITIES]
    city_probs = np.array([c[1] for c in CITIES])
    city_probs = city_probs / city_probs.sum()
    cities = rng.choice(city_labels, size=n, p=city_probs)

    combo_idx = rng.choice(
        len(TYPE_COMBOS),
        size=n,
        p=np.array([c[1] for c in TYPE_COMBOS]),
    )
    types_list = [TYPE_COMBOS[i][0] for i in combo_idx]

    rows = []
    for i in range(n):
        r = float(rating[i]) if not np.isnan(rating[i]) else None
        rows.append(
            {
                "company": f"Synthetic Lead {i:04d}",
                "city": str(cities[i]),
                "website": f"https://lead{i}.example.com" if has_website[i] else None,
                "phone": f"+1-555-{i:07d}"[:15] if has_phone[i] else None,
                "google_rating": r,
                "google_reviews": int(reviews[i]),
                "intel_json": {
                    "place_id": f"synthetic_{i:04d}",
                    "types": list(types_list[i]),
                },
            }
        )

    df = pd.DataFrame(rows)

    feats = np.array([extract_features(row) for row in rows])
    weights = np.array([TRUE_COEFFICIENTS[name] for name in FEATURE_NAMES])
    logits = feats @ weights + TRUE_COEFFICIENTS["intercept"]
    probs = _sigmoid(logits)
    replied = (rng.random(n) < probs).astype(int)

    df["reply_prob"] = probs
    df["replied"] = replied

    return df


def _serialize_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["intel_json"] = out["intel_json"].apply(json.dumps)
    return out


def load_csv(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["intel_json"] = df["intel_json"].apply(json.loads)
    df["google_rating"] = df["google_rating"].where(df["google_rating"].notna(), None)
    return df


def main() -> None:
    out_dir = Path(__file__).parent / "data"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "leads_synthetic.csv"

    df = generate()

    assert len(df) == 1000, f"expected 1000 rows, got {len(df)}"
    reply_rate = df["replied"].mean()
    assert 0.12 <= reply_rate <= 0.22, f"reply rate {reply_rate:.3f} outside [0.12, 0.22]"

    _serialize_for_csv(df).to_csv(out_path, index=False)

    # Round-trip check: re-load CSV and confirm features match.
    reloaded = load_csv(out_path)
    orig_feats = np.array([extract_features(r) for r in df.to_dict(orient="records")])
    reload_feats = np.array([extract_features(r) for r in reloaded.to_dict(orient="records")])
    assert np.allclose(orig_feats, reload_feats), "round-trip feature mismatch"

    print(f"wrote {out_path}")
    print(f"  rows: {len(df)}")
    print(f"  reply rate: {reply_rate:.3f}")


if __name__ == "__main__":
    main()
