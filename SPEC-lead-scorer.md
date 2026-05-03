# Lead Quality Scorer — Build Spec

## Overview

Standalone Python module that scores leads by P(reply) using prospect-time features. Built and tested outside Hermes first, then dropped into `agent/src/functions/` when ready.

The scorer also serves as the final project for IFSA CS38-09 (Intro to AI, Spring 2026). The report must frame Hermes as an intelligent agent using course concepts (PEAS, environment classification, supervised learning, perceptrons, decision trees).

---

## Phase 1: Standalone Module

### 1.1 New files to create

```
lead_scorer/
├── __init__.py
├── features.py          # extract_features()
├── generate.py          # synthetic dataset generator
├── train.py             # train all models, save best one
├── evaluate.py          # metrics, plots, comparison table
├── score.py             # production scorer: load model, score a lead
├── models/              # saved .joblib files go here
│   └── .gitkeep
├── data/                # generated CSVs go here
│   └── .gitkeep
├── figures/             # exported plots go here
│   └── .gitkeep
└── requirements.txt     # scikit-learn, pandas, matplotlib, seaborn, joblib, numpy
```

This lives at the repo root (`hermes/lead_scorer/`) during development. No dependency on any Hermes code — pure Python + sklearn.

### 1.2 `requirements.txt`

```
scikit-learn==1.5.2
pandas==2.2.3
matplotlib==3.9.2
seaborn==0.13.2
numpy>=1.26.0,<2.0.0
joblib==1.4.2
```

---

### 1.3 `features.py`

Single function. This is the contract between training and production — if you change features here, you retrain.

```python
"""Feature extraction for lead scoring.

Every feature must be available at prospect time (Google Places data only).
No enrichment data allowed — the whole point is scoring BEFORE we spend
money enriching.
"""
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
    """Lead dict → fixed-length float vector.

    Accepts both Supabase rows and synthetic data dicts.
    Returns values in FEATURE_NAMES order.
    """
    intel = lead.get("intel_json") or {}
    types = intel.get("types", [])

    rating = lead.get("google_rating")
    reviews = lead.get("google_reviews") or 0
    log_reviews = float(np.log1p(reviews))

    return [
        float(rating) if rating is not None else 0.0,   # google_rating
        1.0 if rating is not None else 0.0,              # has_rating
        log_reviews,                                      # log_reviews
        1.0 if lead.get("website") else 0.0,             # has_website
        1.0 if lead.get("phone") else 0.0,               # has_phone
        (float(rating) if rating else 0.0) * log_reviews, # rating_x_log_reviews
        1.0 if "real_estate_agency" in types else 0.0,   # is_real_estate
        1.0 if "insurance_agency" in types else 0.0,     # is_insurance
    ]
```

**Acceptance criteria:**
- `len(extract_features(lead))` always equals `len(FEATURE_NAMES)`
- Handles all nulls gracefully (no rating, no reviews, no website, no phone, empty intel_json, missing intel_json)
- Same output whether input is a real Supabase row or a synthetic dict

---

### 1.4 `generate.py`

Generates 1,000 synthetic leads with labels from a known logistic model.

**True coefficients (hardcoded):**

| Feature | Coefficient | Why |
|---------|------------|-----|
| intercept | -3.5 | Sets base reply rate low (~3%) |
| google_rating | 0.6 | Better-rated → more responsive |
| has_rating | 0.4 | Having any rating beats none |
| log_reviews | 0.35 | More reviews = bigger/more active business |
| has_website | 0.8 | No website leads are mostly dead — biggest single signal |
| has_phone | 0.2 | Minor completeness signal |
| rating_x_log_reviews | 0.15 | High rating + many reviews compounds |
| is_real_estate | 0.3 | Target vertical responds better |
| is_insurance | 0.0 | Noise — models should learn to ignore |

**Distributions to match Google Places reality:**

| Field | Distribution | Notes |
|-------|-------------|-------|
| google_rating | N(4.2, 0.5) clipped [1.0, 5.0], null 10% of the time | Ratings cluster high |
| google_reviews | lognormal(3.0, 1.2), 0 if no rating | Right-skewed: most have <50, some have 500+ |
| has_website | Bernoulli(0.75) | ~25% of Places results lack websites |
| has_phone | Bernoulli(0.85) | Most have a phone listed |
| city | Categorical, 8 Florida cities, weighted | Miami 20%, rest distributed |
| types | Categorical, 4 combos | 50% real_estate, 15% insurance, rest mixed |

**Output:** `data/leads_synthetic.csv` with columns for every raw field + `replied` (0/1) + `reply_prob` (the true probability, for validation only).

**Acceptance criteria:**
- Exactly 1,000 rows
- Reply rate between 12% and 22%
- Deterministic with `seed=42`
- CSV round-trips cleanly (load it back, extract features, get identical vectors)

---

### 1.5 `train.py`

Trains four models, prints comparison table, saves the best one.

**Models:**

| Model | Class | Key params |
|-------|-------|-----------|
| Perceptron | `sklearn.linear_model.Perceptron` | `max_iter=1000, eta0=0.1, random_state=42` |
| Decision Tree | `sklearn.tree.DecisionTreeClassifier` | `max_depth=5, random_state=42` |
| Logistic Regression | `sklearn.linear_model.LogisticRegression` | `max_iter=1000, random_state=42` |
| Random Forest | `sklearn.ensemble.RandomForestClassifier` | `n_estimators=100, max_depth=5, random_state=42` |

**Pipeline:**
1. Load `data/leads_synthetic.csv`
2. Extract features using `features.extract_features()` for every row
3. 80/20 stratified split on `replied`, `random_state=42`
4. Min-max scale all features (fit on train only, transform both)
5. Train all four models
6. Compute on test set: AUC, accuracy, precision, recall, F1
7. Print comparison table to stdout
8. Save the best model (by AUC) + the fitted scaler as `models/lead_scorer.joblib`

**What gets saved (joblib dict):**

```python
{
    "model": fitted_model,          # the sklearn estimator
    "scaler": fitted_scaler,        # MinMaxScaler fitted on training data
    "feature_names": FEATURE_NAMES, # ordered list
    "threshold": 0.5,               # default decision threshold
    "auc": float,                   # test AUC for reference
    "trained_at": "2026-04-21T...", # ISO timestamp
}
```

**Acceptance criteria:**
- All four models train without errors
- Logistic regression AUC > 0.75 (if it doesn't, the synthetic data has a problem)
- Logistic regression coefficients roughly match TRUE_COEFFICIENTS (within ±0.3 for each)
- Perceptron AUC < Logistic Regression AUC (confirms the interaction term matters)
- Saved joblib loads cleanly and produces identical predictions

---

### 1.6 `evaluate.py`

Generates all plots and the coefficient recovery table. Run after `train.py`.

**Outputs:**

| File | What |
|------|------|
| `figures/roc_curves.png` | All 4 models on one plot, AUC in legend |
| `figures/confusion_matrices.png` | 2x2 heatmap per model, 4-panel figure |
| `figures/feature_importance.png` | Logistic regression coefficients + tree importances side by side |
| `figures/decision_tree.png` | `plot_tree()` visualization at depth 5 |
| `figures/coefficient_recovery.png` | Bar chart: true coefficients vs. learned coefficients |
| `figures/calibration_curve.png` | Predicted probability vs. actual reply rate in bins, for logistic regression and random forest |

**Acceptance criteria:**
- All 6 PNGs generated, 300 dpi, readable at report size
- ROC plot has proper axis labels, legend, diagonal reference line
- Coefficient recovery chart makes it visually obvious the model learned the right weights
- Calibration curve shows predicted vs actual with a diagonal reference line

---

### 1.7 `score.py`

Production scoring interface. Loads saved model, exposes two functions.

```python
"""Production lead scorer.

Usage:
    from lead_scorer.score import score_lead, score_leads

    prob = score_lead(lead_row)           # single lead → float
    probs = score_leads([lead1, lead2])   # batch → list[float]
"""
import joblib
import numpy as np
from pathlib import Path
from .features import extract_features

_artifact = None

def _load():
    global _artifact
    if _artifact is None:
        path = Path(__file__).parent / "models" / "lead_scorer.joblib"
        _artifact = joblib.load(path)
    return _artifact

def score_lead(lead: dict) -> float:
    """P(reply) for a single lead. Returns float in [0, 1]."""
    art = _load()
    features = np.array([extract_features(lead)])
    scaled = art["scaler"].transform(features)
    return float(art["model"].predict_proba(scaled)[0, 1])

def score_leads(leads: list[dict]) -> list[float]:
    """P(reply) for a batch of leads. Same order as input."""
    if not leads:
        return []
    art = _load()
    features = np.array([extract_features(lead) for lead in leads])
    scaled = art["scaler"].transform(features)
    return art["model"].predict_proba(scaled)[:, 1].tolist()
```

**Acceptance criteria:**
- `score_lead()` returns float between 0.0 and 1.0 for any valid lead dict
- `score_lead()` handles degenerate leads (all nulls) without crashing
- `score_leads([])` returns `[]`
- Scoring 1,000 leads takes < 100ms (it's just matrix math)

---

## Phase 1.5: Report Content Generation

The class project report needs specific academic framing. `evaluate.py` should also print/save the following sections as markdown to `data/report_sections.md` so they can be pasted into the final report.

### 1.5.1 PEAS Analysis of Hermes Lead Scorer

The report must frame the lead scoring agent using the PEAS framework (Performance measure, Environment, Actuators, Sensors) from IFSA CS38-09 Class 3.

**PEAS Table to generate:**

| Dimension | Description |
|-----------|-------------|
| **Performance** | Maximize reply rate while minimizing enrichment spend. Measured by precision (% of enriched leads that reply) and cost savings (leads correctly skipped). |
| **Environment** | Pool of prospected B2B leads (real estate brokerages in Florida cities). Each lead has Google Places metadata (rating, review count, website, phone, business types). Environment is **partially observable** (we can't see recipient intent or inbox state), **stochastic** (replies depend on unobservable factors), **sequential** (prospect → score → enrich → draft → send), **dynamic** (lead situations change independently), **discrete** (finite actions per stage), **single-agent** (lead isn't adversarial). |
| **Actuators** | Assign a reply-probability score to each lead. Flag low-scoring leads as dead. Rank remaining leads for enrichment priority. |
| **Sensors** | Google Places API (rating, review count, website URL, phone, business types/categories, address). These are the raw inputs available before enrichment. |

### 1.5.2 Agent Type Classification

The report should classify the lead scorer's role in Hermes's agent architecture (from Class 3 agent types):

- Hermes without the scorer operates as a **model-based reflex agent**: it tracks internal state (lead status, intel_json) and applies condition-action rules (hook tier logic, per-tick caps, daily send ceiling).
- Adding the lead scorer introduces a **utility-based component**: the scorer assigns a utility value (P(reply)) to each lead, allowing Hermes to prioritize actions that maximize expected value rather than processing leads in arbitrary order.
- This demonstrates how a simple reflex system can be enhanced with learned utility functions — a core progression in the class's agent type hierarchy.

### 1.5.3 Supervised Learning Framing

Use the exact class definition from Class 4: "Given a set of examples (x_i, y_i), find a hypothesis h such that h(x) ≈ y."

- **x_i** = feature vector for lead i (google_rating, log_reviews, has_website, etc.)
- **y_i** = binary label (1 = replied, 0 = did not reply)
- **h(x)** = trained model's prediction
- This is **inductive learning** — generalizing from specific labeled examples to predict unseen leads.

### 1.5.4 Perceptron Connection (Class 5)

The report should include a **manual perceptron computation** for one example lead, showing:
1. Feature values for a sample lead (e.g., google_rating=4.5, log_reviews=3.2, has_website=1, ...)
2. Multiply each feature by its learned weight
3. Sum to get z = Σ(w_i · x_i) + bias
4. Apply step function: predict 1 if z ≥ 0, else 0

This ties directly to the Class 5 perceptron exercises (RGB color classifier) but applied to lead features instead of color channels.

### 1.5.5 Noise Feature Ablation

Frame `is_insurance` (coefficient = 0 in the true model) as a deliberate experiment:
- **Hypothesis**: "Can each model correctly identify that business type 'insurance' carries no predictive signal for reply likelihood?"
- **Expected result**: Logistic regression should assign near-zero weight. Decision tree should rarely split on it. Random forest feature importance should rank it last.
- **Why it matters**: Demonstrates that the models are learning real patterns, not memorizing noise.

### 1.5.6 Synthetic Data Justification

The report must explicitly acknowledge and justify the use of synthetic data:
- Hermes is a live production system. Early-stage real data (limited volume, class imbalance) would produce unreliable models.
- Synthetic data with a known generative process allows **controlled validation**: we can verify that logistic regression recovers the true coefficients, proving the pipeline works correctly.
- Feature distributions in the synthetic data were calibrated against real Google Places API responses from Hermes's production database to ensure realism.
- The trained model will be retrained on real reply data once Hermes accumulates sufficient volume (200+ sent leads with outcome labels).

---

## Phase 2: Testing

### 2.1 Unit tests (`test_features.py`)

```
test_extract_features_normal_lead        → correct length, correct values
test_extract_features_null_rating        → has_rating=0, google_rating=0, interaction=0
test_extract_features_no_website         → has_website=0
test_extract_features_empty_intel        → is_real_estate=0, is_insurance=0
test_extract_features_missing_intel_key  → doesn't crash
```

### 2.2 Unit tests (`test_score.py`)

```
test_score_lead_returns_float            → isinstance(result, float)
test_score_lead_range                    → 0.0 <= result <= 1.0
test_score_lead_high_quality             → lead with 4.8 rating, 200 reviews, website scores > 0.3
test_score_lead_low_quality              → lead with no rating, no website scores < 0.15
test_score_leads_batch                   → len(output) == len(input)
test_score_leads_empty                   → returns []
test_score_deterministic                 → same lead → same score every time
```

### 2.3 Integration test (`test_pipeline.py`)

```
test_full_pipeline:
    1. generate.py → CSV exists, 1000 rows, reply rate in range
    2. train.py → joblib exists, AUC > 0.75
    3. score.py → loads model, scores sample leads, results make sense
```

---

## Phase 3: Hermes Integration

Only start this after Phase 2 passes. Three changes to existing code:

### 3.1 Add dependency

In `agent/requirements.txt`, add:
```
scikit-learn==1.5.2
joblib==1.4.2
```

numpy is already an indirect dependency.

### 3.2 Move module into Hermes

```
# Move the scoring code (not the training/eval code) into the agent
agent/src/functions/lead_scorer/
├── __init__.py
├── features.py      # copied from lead_scorer/features.py
├── score.py         # copied from lead_scorer/score.py
└── models/
    └── lead_scorer.joblib  # copied from lead_scorer/models/
```

The training code (`generate.py`, `train.py`, `evaluate.py`) stays in the standalone `lead_scorer/` directory. Hermes only needs the scoring side.

### 3.3 Modify `campaign_runner.py`

One change to the enrich step. Current code (lines 169–189):

```python
# 2. Enrich all status='new' leads in this campaign
new_leads = (
    supabase.table("leads")
    .select("id")
    .eq("campaign_id", campaign_id)
    .eq("status", "new")
    .limit(ENRICH_PER_TICK)
    .execute()
)
for row in new_leads.data:
    try:
        ok = enrich(row["id"])
        ...
```

New code:

```python
from agent.src.functions.lead_scorer.score import score_lead

MIN_SCORE = 0.10

# 2. Score new leads, enrich the best ones
new_leads = (
    supabase.table("leads")
    .select("*")
    .eq("campaign_id", campaign_id)
    .eq("status", "new")
    .execute()
)

ranked = sorted(
    [(row, score_lead(row)) for row in new_leads.data],
    key=lambda x: x[1],
    reverse=True,
)

enriched = 0
for row, prob in ranked:
    if enriched >= ENRICH_PER_TICK:
        break
    if prob < MIN_SCORE:
        supabase.table("leads").update({"status": "dead"}).eq("id", row["id"]).execute()
        summary["dead"] = summary.get("dead", 0) + 1
        log.info("lead_below_threshold", lead_id=row["id"], score=round(prob, 3))
        continue
    try:
        ok = enrich(row["id"])
        enriched += 1 if ok else 0
        summary["enriched"] += 1 if ok else 0
    except Exception as e:
        summary["errors"].append(f"enrich {row['id']}: {e}")
```

**Key differences:**
- `.select("*")` instead of `.select("id")` — scorer needs the full row
- No `.limit()` — we fetch all new leads, score them, THEN take the top N
- Leads below `MIN_SCORE` get marked dead immediately
- Leads above threshold get enriched in score order (best first)

### 3.4 Schema migration (optional)

If you want scores visible in the dashboard:

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS lead_score numeric;
```

Score at prospect time in `prospect.py`:

```python
from agent.src.functions.lead_scorer.score import score_lead

# after insert:
score = score_lead(lead_row)
supabase.table("leads").update({"lead_score": round(score, 4)}).eq("id", lead_id).execute()
```

---

## Run Commands

```bash
# Phase 1 — build and train
cd lead_scorer
pip install -r requirements.txt
python -m lead_scorer.generate          # → data/leads_synthetic.csv
python -m lead_scorer.train             # → models/lead_scorer.joblib + comparison table
python -m lead_scorer.evaluate          # → figures/*.png + data/report_sections.md

# Phase 2 — test
pytest lead_scorer/ -v

# Phase 3 — integrate
cp lead_scorer/features.py agent/src/functions/lead_scorer/features.py
cp lead_scorer/score.py agent/src/functions/lead_scorer/score.py
cp lead_scorer/models/lead_scorer.joblib agent/src/functions/lead_scorer/models/
# then apply the campaign_runner.py diff
```

---

## Retraining on Real Data

Once Hermes has 200+ leads that reached `sent` status (and some have moved to `replied`/`booked`):

```python
# pull_real_data.py
from agent.src.clients.supabase_client import supabase

resp = supabase.table("leads").select("*").in_(
    "status", ["sent", "replied", "booked", "dead", "unsubscribed"]
).execute()

for lead in resp.data:
    lead["replied"] = int(lead["status"] in ("replied", "booked"))

# write to data/leads_real.csv in same format as leads_synthetic.csv
# then: python -m lead_scorer.train --data data/leads_real.csv
```

Nothing else changes. Same features, same pipeline, same score.py. Just better data.
