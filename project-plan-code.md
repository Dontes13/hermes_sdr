# Lead Quality Scorer — Code Plan

## What We're Building

A scoring function that takes a lead's prospect-time data (the stuff Hermes collects from Google Places before spending money on enrichment) and outputs a probability that the lead will eventually reply. Two uses:

1. **Class project**: Train on synthetic data, compare perceptron vs. decision tree vs. logistic regression, write up results.
2. **Real Hermes**: Plug the trained model into `campaign_runner.py` so Hermes enriches high-score leads first instead of blindly doing FIFO. Saves enrichment spend by skipping leads that were never going to reply anyway.

---

## Where It Plugs Into Hermes

Right now in `campaign_runner.py` lines 169–177:

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
```

This grabs new leads in arbitrary order. After the scorer exists, this becomes:

```python
# 2. Enrich highest-scoring 'new' leads first
new_leads = (
    supabase.table("leads")
    .select("id, google_rating, google_reviews, website, phone, city, intel_json")
    .eq("campaign_id", campaign_id)
    .eq("status", "new")
    .execute()
)
scored = [(row, score_lead(row)) for row in new_leads.data]
scored.sort(key=lambda x: x[1], reverse=True)
for row, sc in scored[:ENRICH_PER_TICK]:
    if sc < MIN_SCORE_THRESHOLD:
        # mark as dead — not worth the $0.002 enrichment cost
        supabase.table("leads").update({"status": "dead"}).eq("id", row["id"]).execute()
        continue
    enrich(row["id"])
```

That's the whole integration. Everything below is about building `score_lead()`.

---

## Features (What the Model Sees)

Every feature must be available at prospect time — meaning it comes from the Google Places API response before we spend money enriching. Here's what `prospect.py` actually stores:

| Feature | Column / Path | Type | Why It Matters |
|---------|--------------|------|----------------|
| `google_rating` | `leads.google_rating` | float 1.0–5.0 (nullable) | Higher-rated businesses tend to be more established and responsive |
| `google_reviews` | `leads.google_reviews` | int (nullable) | Proxy for business size — 5 reviews vs. 500 reviews is a different lead |
| `has_website` | `leads.website IS NOT NULL` | bool | No website = no enrichment possible = dead lead anyway |
| `has_phone` | `leads.phone IS NOT NULL` | bool | Completeness signal |
| `city` | `leads.city` | categorical | Some markets respond better than others |
| `place_types` | `intel_json.types` | list[str] | Google's business categories — "real_estate_agency" vs. "insurance_agency" etc. |
| `log_reviews` | `log(google_reviews + 1)` | float | Compresses the long tail (a lead with 1000 reviews isn't 200x better than one with 5) |
| `rating_x_log_reviews` | `google_rating * log_reviews` | float | Interaction term: a 5.0 rating with 200 reviews is stronger signal than 5.0 with 2 reviews |
| `has_rating` | `google_rating IS NOT NULL` | bool | Missing rating is itself a signal (business hasn't been reviewed) |

### Feature Extraction Function

This is the core reusable piece — same function for training and production:

```python
import numpy as np

def extract_features(lead: dict) -> dict:
    """Extract model features from a lead row. Works on both
    real Supabase rows and synthetic data dicts."""
    intel = lead.get("intel_json") or {}
    types = intel.get("types", [])

    rating = lead.get("google_rating")
    reviews = lead.get("google_reviews") or 0
    log_reviews = np.log1p(reviews)

    return {
        "google_rating": rating if rating is not None else 0.0,
        "has_rating": int(rating is not None),
        "log_reviews": log_reviews,
        "has_website": int(bool(lead.get("website"))),
        "has_phone": int(bool(lead.get("phone"))),
        "rating_x_log_reviews": (rating or 0.0) * log_reviews,
        "is_real_estate": int("real_estate_agency" in types),
        "is_insurance": int("insurance_agency" in types),
        "city_encoded": lead.get("city", "unknown"),  # will be one-hot encoded
    }
```

---

## Synthetic Data Generation

### The Ground Truth Model

We define a hidden logistic model that generates the reply labels. This is the "answer key" — we know the true coefficients, so we can verify our trained models recover them.

```python
TRUE_COEFFICIENTS = {
    "intercept": -3.5,           # base reply rate ~3% before features
    "google_rating": 0.6,        # higher rating → more likely to reply
    "log_reviews": 0.35,         # more reviews → more likely
    "has_website": 0.8,          # big deal — no website leads are mostly dead
    "has_phone": 0.2,            # minor signal
    "rating_x_log_reviews": 0.15,# interaction: high rating + many reviews compounds
    "is_real_estate": 0.3,       # target vertical responds better
    "has_rating": 0.4,           # having any rating beats having none
}
# noise features (is_insurance, city) get 0 coefficient — tests if models ignore them
```

With these coefficients, the expected reply rate across 1,000 leads will land around 15–18%.

### Generating Realistic Distributions

Pull distributions from what Google Places actually returns:

```python
def generate_synthetic_leads(n=1000, seed=42):
    rng = np.random.default_rng(seed)

    leads = []
    for _ in range(n):
        # ~10% of leads have no rating at all
        has_rating = rng.random() > 0.10
        rating = round(rng.normal(4.2, 0.5), 1) if has_rating else None
        if rating is not None:
            rating = np.clip(rating, 1.0, 5.0)

        reviews = int(rng.lognormal(3.0, 1.2)) if has_rating else 0
        reviews = max(0, reviews)

        has_website = rng.random() < 0.75
        has_phone = rng.random() < 0.85

        city = rng.choice(
            ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale",
             "Naples", "Sarasota", "Boca Raton"],
            p=[0.20, 0.15, 0.15, 0.10, 0.10, 0.10, 0.10, 0.10]
        )

        types = rng.choice(
            [["real_estate_agency"], ["insurance_agency"],
             ["real_estate_agency", "point_of_interest"],
             ["finance", "point_of_interest"]],
            p=[0.50, 0.15, 0.20, 0.15]
        )

        lead = {
            "google_rating": rating,
            "google_reviews": reviews,
            "website": f"https://{city.lower()}realty{_}.com" if has_website else None,
            "phone": f"+1555{rng.integers(1000000,9999999)}" if has_phone else None,
            "city": city,
            "intel_json": {"types": list(types), "place_id": f"fake_{_}"},
        }

        # Extract features, compute true probability, sample label
        feats = extract_features(lead)
        logit = TRUE_COEFFICIENTS["intercept"]
        for key, coef in TRUE_COEFFICIENTS.items():
            if key == "intercept":
                continue
            logit += coef * feats.get(key, 0)

        prob = 1 / (1 + np.exp(-logit))
        replied = int(rng.random() < prob)

        lead["_reply_prob"] = prob  # for analysis only
        lead["replied"] = replied
        leads.append(lead)

    return leads
```

### Split

- 800 train / 200 test, stratified on `replied`
- Set `random_state=42` everywhere

---

## Models

### 1. Perceptron

```python
from sklearn.linear_model import Perceptron

perceptron = Perceptron(max_iter=1000, random_state=42, eta0=0.1)
perceptron.fit(X_train, y_train)
```

The perceptron only outputs 0/1 (no probabilities), so for ROC we use `decision_function()` as the score. It will struggle with the `rating_x_log_reviews` interaction because it can only learn a linear boundary — which is the point. That gap between the perceptron and the tree is where the interesting analysis lives.

### 2. Decision Tree

```python
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

tree = DecisionTreeClassifier(max_depth=5, random_state=42)
tree.fit(X_train, y_train)

# Visualize it — this is the showpiece for the report
plot_tree(tree, feature_names=feature_names, class_names=["no_reply", "reply"], filled=True)
```

Try max_depth values of 3, 5, 7, and None. Report the AUC for each to show overfitting at higher depths. The depth=5 tree should be the sweet spot and produce readable rules like "if google_rating > 4.35 and log_reviews > 3.2 and has_website = 1 → reply."

### 3. Logistic Regression

```python
from sklearn.linear_model import LogisticRegression

logreg = LogisticRegression(max_iter=1000, random_state=42)
logreg.fit(X_train, y_train)

# Recover coefficients — should approximately match TRUE_COEFFICIENTS
for name, coef in zip(feature_names, logreg.coef_[0]):
    print(f"{name}: {coef:.3f}")
```

This is the validation step. If the trained coefficients roughly match the true ones, it proves the synthetic data is well-constructed and the model is working correctly. Include a side-by-side table in the report.

### 4. Random Forest (bonus)

```python
from sklearn.ensemble import RandomForestClassifier

rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
rf.fit(X_train, y_train)
```

Brief mention only. Shows awareness of ensembles, but keep focus on the three class-covered models.

---

## Evaluation

### Metrics to Compute

```python
from sklearn.metrics import (
    roc_auc_score, roc_curve, confusion_matrix,
    classification_report, precision_recall_curve
)

# For each model:
y_prob = model.predict_proba(X_test)[:, 1]  # (use decision_function for perceptron)
y_pred = model.predict(X_test)

auc = roc_auc_score(y_test, y_prob)
cm = confusion_matrix(y_test, y_pred)
report = classification_report(y_test, y_pred)
```

### Plots to Generate

1. **ROC curves** — all 3 (or 4) models on one plot, with AUC in the legend
2. **Confusion matrices** — 2x2 heatmaps side by side
3. **Feature importance bar chart** — logistic regression coefficients + tree feature importances on the same figure
4. **Decision tree visualization** — `plot_tree()` at depth 5
5. **Coefficient recovery table** — true vs. learned coefficients for logistic regression
6. **Perceptron convergence** — accuracy per epoch if training with `partial_fit` in a loop

### Expected Results

Because the data was generated by a logistic model:
- Logistic regression will win (AUC ~0.82–0.88) since it matches the true data-generating process
- Decision tree will be close (AUC ~0.78–0.85), especially at depth 5
- Perceptron will trail (AUC ~0.72–0.78) because it misses the interaction term
- Random forest may slightly beat logistic regression due to averaging

This ranking gives you a clean narrative: "simpler models have limitations, but even the perceptron provides useful signal."

---

## File Structure

```
lead-scorer/
├── lead_scorer.ipynb          # Everything: data gen, training, eval, plots
├── score.py                   # Standalone scoring module for Hermes integration
├── data/
│   └── leads_synthetic.csv    # Generated dataset (committed for reproducibility)
├── models/
│   └── lead_scorer.joblib     # Trained logistic regression (production model)
└── figures/
    ├── roc_curves.png
    ├── confusion_matrices.png
    ├── feature_importance.png
    └── decision_tree.png
```

---

## Hermes Integration: `score.py`

The production module. This is what actually runs inside Hermes:

```python
"""Lead quality scorer for Hermes.

Loads a trained model and scores leads at prospect time,
before enrichment spend. Used by campaign_runner to prioritize
which leads to enrich.
"""
import joblib
import numpy as np
from pathlib import Path

MODEL_PATH = Path(__file__).parent / "models" / "lead_scorer.joblib"
_model = None

def _load_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model

def extract_features(lead: dict) -> dict:
    """Extract model features from a Supabase lead row."""
    intel = lead.get("intel_json") or {}
    types = intel.get("types", [])
    rating = lead.get("google_rating")
    reviews = lead.get("google_reviews") or 0
    log_reviews = np.log1p(reviews)

    return {
        "google_rating": rating if rating is not None else 0.0,
        "has_rating": int(rating is not None),
        "log_reviews": log_reviews,
        "has_website": int(bool(lead.get("website"))),
        "has_phone": int(bool(lead.get("phone"))),
        "rating_x_log_reviews": (rating or 0.0) * log_reviews,
        "is_real_estate": int("real_estate_agency" in types),
        "is_insurance": int("insurance_agency" in types),
    }

# Feature order must match training
FEATURE_ORDER = [
    "google_rating", "has_rating", "log_reviews", "has_website",
    "has_phone", "rating_x_log_reviews", "is_real_estate", "is_insurance"
]

def score_lead(lead: dict) -> float:
    """Return P(reply) for a single lead. Range [0, 1]."""
    model = _load_model()
    feats = extract_features(lead)
    X = np.array([[feats[f] for f in FEATURE_ORDER]])
    return float(model.predict_proba(X)[0, 1])

def score_leads(leads: list[dict]) -> list[float]:
    """Batch score. Returns list of P(reply) in same order."""
    model = _load_model()
    X = np.array([
        [extract_features(lead)[f] for f in FEATURE_ORDER]
        for lead in leads
    ])
    return model.predict_proba(X)[:, 1].tolist()
```

### Campaign Runner Change (the actual diff)

In `campaign_runner.py`, the enrich step changes from ~5 lines to ~12 lines:

```python
from agent.src.functions.score import score_lead

MIN_SCORE_THRESHOLD = 0.10  # leads below 10% reply probability get skipped

# 2. Score and enrich top leads
new_leads = (
    supabase.table("leads")
    .select("*")
    .eq("campaign_id", campaign_id)
    .eq("status", "new")
    .execute()
)

scored_leads = [(row, score_lead(row)) for row in new_leads.data]
scored_leads.sort(key=lambda x: x[1], reverse=True)

enriched = 0
for row, reply_prob in scored_leads:
    if enriched >= ENRICH_PER_TICK:
        break
    if reply_prob < MIN_SCORE_THRESHOLD:
        supabase.table("leads").update({"status": "dead"}).eq("id", row["id"]).execute()
        summary["dead"] += 1
        log.info("lead_scored_dead", lead_id=row["id"], score=round(reply_prob, 3))
        continue
    try:
        ok = enrich(row["id"])
        enriched += 1 if ok else 0
        summary["enriched"] += 1 if ok else 0
    except Exception as e:
        summary["errors"].append(f"enrich {row['id']}: {e}")
```

### Dashboard Addition (optional)

Add a `lead_score` column to the leads table and show it in the dashboard so you can see scores next to each lead:

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS lead_score numeric;
CREATE INDEX IF NOT EXISTS leads_score_idx ON leads(lead_score) WHERE lead_score IS NOT NULL;
```

Score gets written right after prospecting:

```python
# in prospect.py, after insert:
score = score_lead(lead_row)
supabase.table("leads").update({"lead_score": round(score, 4)}).eq("id", lead_id).execute()
```

---

## Build Order

| Step | What | Output | Time |
|------|------|--------|------|
| 1 | `extract_features()` function | Tested on a few hand-written lead dicts | 30 min |
| 2 | `generate_synthetic_leads()` with TRUE_COEFFICIENTS | `leads_synthetic.csv`, verify 15–18% reply rate | 1 hr |
| 3 | Train all 3 models, compute metrics | Model comparison table, verify logreg recovers true coefficients | 1 hr |
| 4 | Generate all plots (ROC, confusion matrices, tree, feature importance) | `figures/` directory | 1 hr |
| 5 | Write `score.py` production module | Working `score_lead()` function | 30 min |
| 6 | Modify `campaign_runner.py` to use scorer | Tested locally with a few leads | 30 min |
| 7 | Write the report | PDF / notebook writeup | 3 hrs |
| 8 | Re-run notebook from scratch to verify reproducibility | Clean run, all outputs match | 30 min |

**Total: ~8 hours of actual work.** Steps 1–4 are the class project. Steps 5–6 are the Hermes integration. Step 7 is the writeup.

---

## How To Retrain on Real Data Later

Once Hermes has sent enough emails to have real reply data (50+ replies), swap synthetic for real:

```python
# Pull real data from Supabase
leads = supabase.table("leads").select("*").in_("status", ["sent", "replied", "booked", "dead"]).execute()

for lead in leads.data:
    lead["replied"] = int(lead["status"] in ("replied", "booked"))

# Same extract_features(), same training code, real labels
```

The feature extraction function, model pipeline, and `score.py` module don't change at all. Only the training data changes. That's the whole point of designing it this way.
