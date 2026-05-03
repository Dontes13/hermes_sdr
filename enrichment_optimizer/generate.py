"""Synthetic lead pool generator for the enrichment knapsack problem.

Each lead has:
  - Observable Google Places features (rating, reviews, website, phone, type, city, employees)
  - Derived knapsack inputs: deal_size, reply_probability, estimated_value, enrichment_cost

Deal size uses real Hermes pricing: $5k (50+ employees) / $3k (under 50).
Enrichment cost: $0.002 base × multiplier (0.5× if no website, 1.5× if reviews>200).
Daily budget = 60% × total cost of the 200-lead pool — written to data/budget.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"

DEFAULT_POOL_SIZE = 200
SCALING_SIZES = [50, 100, 200, 500]
DEFAULT_SEED = 42
BUDGET_FRACTION = 0.60

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

BUSINESS_TYPES = [
    ("real_estate", 0.50),
    ("finance", 0.20),
    ("insurance", 0.15),
    ("other", 0.15),
]

ENRICHMENT_BASE_COST = 0.002


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def generate(n: int = DEFAULT_POOL_SIZE, seed: int = DEFAULT_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    rating_missing = rng.random(n) < 0.10
    rating_raw = rng.normal(4.2, 0.5, n).clip(1.0, 5.0)
    google_rating = np.where(rating_missing, np.nan, rating_raw)

    reviews_raw = rng.lognormal(3.0, 1.2, n).astype(int)
    google_reviews = np.where(rating_missing, 0, reviews_raw)

    has_website = rng.random(n) < 0.75
    has_phone = rng.random(n) < 0.85

    cities = rng.choice(
        [c[0] for c in CITIES], size=n, p=np.array([c[1] for c in CITIES])
    )
    business_types = rng.choice(
        [b[0] for b in BUSINESS_TYPES],
        size=n,
        p=np.array([b[1] for b in BUSINESS_TYPES]),
    )

    employees = rng.lognormal(3.0, 1.0, n).round().clip(1, 500).astype(int)

    deal_size = np.where(employees >= 50, 5000.0, 3000.0)

    rating_for_logit = np.where(rating_missing, 0.0, google_rating)
    has_website_f = has_website.astype(float)
    is_real_estate = (business_types == "real_estate").astype(float)
    noise = rng.normal(0.0, 0.3, n)
    logit = (
        -2.5
        + 0.6 * (rating_for_logit / 5.0)
        + 0.3 * np.log1p(google_reviews) / 6.0
        + 0.4 * has_website_f
        + 0.2 * is_real_estate
        + noise
    )
    reply_probability = _sigmoid(logit)

    cost_multiplier = np.where(
        ~has_website,
        0.5,
        np.where(google_reviews > 200, 1.5, 1.0),
    )
    enrichment_cost = ENRICHMENT_BASE_COST * cost_multiplier

    estimated_value = deal_size * reply_probability
    value_to_cost = estimated_value / enrichment_cost

    df = pd.DataFrame(
        {
            "lead_id": np.arange(n),
            "google_rating": google_rating,
            "google_reviews": google_reviews.astype(int),
            "has_website": has_website,
            "has_phone": has_phone,
            "business_type": business_types,
            "city": cities,
            "estimated_employees": employees,
            "deal_size": deal_size,
            "reply_probability": reply_probability,
            "enrichment_cost": enrichment_cost,
            "estimated_value": estimated_value,
            "value_to_cost_ratio": value_to_cost,
        }
    )

    return df


def _sanity_check(df: pd.DataFrame) -> None:
    n = len(df)
    top_decile = df["value_to_cost_ratio"].quantile(0.90)
    bot_decile = df["value_to_cost_ratio"].quantile(0.10)
    top_count = int((df["value_to_cost_ratio"] >= top_decile).sum())
    bot_count = int((df["value_to_cost_ratio"] <= bot_decile).sum())
    assert top_count >= 3, f"pool n={n}: only {top_count} leads in top decile"
    assert bot_count >= 3, f"pool n={n}: only {bot_count} leads in bottom decile"


def _write_pool(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def main() -> None:
    DATA.mkdir(exist_ok=True)

    pools: dict[int, pd.DataFrame] = {}
    for size in SCALING_SIZES:
        df = generate(n=size, seed=DEFAULT_SEED)
        _sanity_check(df)
        _write_pool(df, DATA / f"leads_pool_{size}.csv")
        pools[size] = df

    default_pool = pools[DEFAULT_POOL_SIZE]
    _write_pool(default_pool, DATA / "leads_pool.csv")

    total_cost_default = float(default_pool["enrichment_cost"].sum())
    daily_budget = round(total_cost_default * BUDGET_FRACTION, 6)

    budget_info = {
        "daily_budget": daily_budget,
        "pool_size": DEFAULT_POOL_SIZE,
        "total_pool_cost": total_cost_default,
        "budget_fraction": BUDGET_FRACTION,
        "seed": DEFAULT_SEED,
    }
    (DATA / "budget.json").write_text(json.dumps(budget_info, indent=2))

    print(f"wrote pools: {[f'leads_pool_{s}.csv' for s in SCALING_SIZES]}")
    print(f"default pool ({DEFAULT_POOL_SIZE} leads): {DATA / 'leads_pool.csv'}")
    print(f"  total cost: ${total_cost_default:.4f}")
    print(f"  daily budget ({int(BUDGET_FRACTION * 100)}%): ${daily_budget:.4f}")
    print(f"  avg reply prob: {default_pool['reply_probability'].mean():.3f}")
    print(f"  avg estimated value: ${default_pool['estimated_value'].mean():.2f}")


def load_pool(path: Path | str | None = None) -> pd.DataFrame:
    if path is None:
        path = DATA / "leads_pool.csv"
    return pd.read_csv(path)


def load_budget() -> float:
    info = json.loads((DATA / "budget.json").read_text())
    return float(info["daily_budget"])


if __name__ == "__main__":
    main()
