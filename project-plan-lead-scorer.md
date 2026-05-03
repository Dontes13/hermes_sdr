# Lead Quality Scorer — Project Plan
**IFSA CS38-09 · Spring 2026 · Enrique Perez Alonso**

---

## 1. Project Summary

Build a binary classifier that predicts whether a prospected lead will reply to a cold email, using only features available at prospect time (before enrichment). Compare three models covered in class — a perceptron, a decision tree, and logistic regression — on a synthetic dataset modeled after the real Hermes B2B sales platform. Evaluate with ROC-AUC, confusion matrices, and feature importance analysis. Deliver a report that frames Hermes as an intelligent agent using the PEAS framework and grounds every technique in class terminology.

---

## 2. Framing Hermes as an AI Agent (Class 3 Content)

The report's introduction should position Hermes using the frameworks from Class 3.

### 2.1 PEAS Analysis

| Dimension | Hermes |
|---|---|
| **Performance** | Reply rate, booking rate, cost per booked meeting, send-to-reply ratio |
| **Environment** | Pool of small-business leads (real estate brokerages) with Google Places data, websites, and contact info |
| **Actuators** | Send cold emails, enrich leads (scrape + LLM), skip/kill dead leads |
| **Sensors** | Google Places API (rating, reviews, website URL), Firecrawl web scraper, inbox listener for replies |

### 2.2 Environment Classification

Classify Hermes's task environment the same way class exercises did (poker agent, exam grader):

- **Partially observable** — Hermes can't see the recipient's intent or inbox state
- **Stochastic** — whether a lead replies depends on unobservable factors
- **Sequential** — prospect → enrich → draft → send → wait for reply; each step depends on the prior
- **Dynamic** — leads' situations change over time independent of Hermes
- **Discrete** — finite set of actions at each stage
- **Single agent** — Hermes acts alone (the lead isn't an adversary optimizing against it)

### 2.3 Agent Type

Hermes currently operates as a **model-based reflex agent**: it maintains internal state (lead status, intel_json) and uses condition-action rules (hook tier logic, campaign tick caps). This project adds a **utility-based** component — the lead scorer assigns a utility (reply probability) to each lead, enabling Hermes to prioritize high-value prospects.

---

## 3. The Machine Learning Problem (Class 4 Content)

### 3.1 Supervised Learning Framing

Use the exact class definition: "Given a set of examples (x_i, y_i), find a hypothesis h such that h(x) ≈ y." This is **inductive learning** — generalizing from specific labeled examples to a function that predicts unseen leads.

- **x_i** = feature vector for lead i (Google rating, review count, has_website, city, business_type, etc.)
- **y_i** = binary label: 1 if the lead replied, 0 if not
- **h(x)** = the trained model's prediction: reply or no-reply

### 3.2 Why Classification (Not Regression)

The dependent variable is binary (replied / didn't reply), making this a classification task. Class 4 covered regression for continuous outputs and decision trees for categorical decisions — this project uses the classification side. Logistic regression bridges both: it's a regression that outputs a probability, thresholded into a class label.

---

## 4. Feature Engineering

All features come from data Hermes actually collects during prospecting (before enrichment). This grounds the project in the real system.

### 4.1 Feature Table

| # | Feature | Source | Type | Rationale |
|---|---------|--------|------|-----------|
| 1 | `google_rating` | Google Places API | Continuous (1.0–5.0) | Higher-rated businesses may be more professional/responsive |
| 2 | `google_reviews` | Google Places API | Integer | Proxy for business size and online presence |
| 3 | `has_website` | Google Places API | Binary (0/1) | Leads without websites are harder to research and less likely to engage |
| 4 | `has_phone` | Google Places API | Binary (0/1) | Indicates business completeness |
| 5 | `has_owner_name` | Enrichment output | Binary (0/1) | Personalized emails perform better |
| 6 | `city_tier` | Derived from city | Ordinal (1–3) | Major metros vs. mid-size vs. small markets |
| 7 | `business_type` | Google Places category | Categorical (encoded) | Some verticals reply more than others |
| 8 | `review_density` | `google_reviews / years_since_founded` | Continuous | Growth signal — fast-growing firms may be more receptive |
| 9 | `hook_tier_count` | `len(compute_available_tiers(lead))` | Integer (1–5) | More available hooks = richer data = better email = more replies |
| 10 | `has_specialties` | `intel_json.specialties` | Binary (0/1) | Enrichment depth indicator |

### 4.2 Feature Preprocessing

- One-hot encode `business_type` (cap at top 8 categories + "other")
- Min-max scale continuous features (google_rating, google_reviews, review_density) to [0, 1] — required for the perceptron to converge
- No scaling needed for tree-based models, but apply it uniformly for fair comparison

---

## 5. Synthetic Dataset Design

The council's key recommendation: design the dataset with a **known logistic model underneath** so ground truth is controlled and results are interpretable.

### 5.1 Data Generation Strategy

1. **Define the true model**: Pick 4–5 features with known coefficients. For example:
   ```
   logit(P(reply)) = -3.0 + 0.8·google_rating + 0.3·log(reviews+1) + 0.5·has_website + 0.4·hook_tier_count + noise
   ```
   The intercept of -3.0 produces a base reply rate around 5%. The features push it up. This gives ~15–18% overall reply rate (realistic for cold email).

2. **Generate 1,000 leads** with realistic distributions:
   - `google_rating`: normal(4.2, 0.5), clipped to [1.0, 5.0]
   - `google_reviews`: lognormal(3.0, 1.2), rounded to integers — gives a right-skewed distribution (many leads with <50 reviews, few with 500+)
   - `has_website`: Bernoulli(0.75)
   - `city_tier`: categorical [1, 2, 3] with weights [0.3, 0.45, 0.25]
   - `business_type`: 8 categories with realistic frequencies
   - `hook_tier_count`: derived from other features using the real `compute_available_tiers()` logic

3. **Generate labels**: For each lead, compute P(reply) from the true logistic model, then sample y_i ~ Bernoulli(P(reply)). This creates realistic noise — not every high-probability lead replies, not every low-probability lead is silent.

4. **Add two noise features** (`days_since_founded_approx`, `phone_area_code`) that have zero true coefficient. These test whether models correctly ignore irrelevant features.

### 5.2 Train/Test Split

- 80/20 stratified split (stratify on y to preserve class balance in both sets)
- Report class distribution in both splits

### 5.3 Class Imbalance

With ~15–18% reply rate, the dataset is imbalanced. Address this in the report:
- Discuss why accuracy alone is misleading (a "predict all 0" model gets 82–85% accuracy)
- This motivates ROC-AUC as the primary metric (class 4 connection: model evaluation)

---

## 6. Models to Compare

### 6.1 Model 1: Perceptron (Class 5 Content)

Directly ties to Class 5 (Perceptron & Neural Networks). The class covered:
- Weighted sum: z = Σ(w_i · x_i) + bias
- Step function: output 1 if z ≥ 0, else 0
- Training: update weights when prediction is wrong

**Implementation approach**: Use `sklearn.linear_model.Perceptron` but explain it from scratch in the report using the class formulation. Include a diagram showing the perceptron architecture with the lead features as inputs (similar to the RGB color classifier exercise from Class 5, but with lead features instead of color channels).

**Why include it**: It's the simplest model and connects directly to a class exercise. It establishes a baseline. Its limitation (linear decision boundary only) motivates the more powerful models.

### 6.2 Model 2: Decision Tree (Class 4 Content)

Directly ties to Class 4 (Linear Regression, Decision Trees). Decision trees split the feature space using if/then rules.

**Implementation**: `sklearn.tree.DecisionTreeClassifier` with max_depth tuning (try 3, 5, 7, None).

**Why include it**: Covered in Class 4. Produces interpretable rules that map to business logic ("if google_rating > 4.5 AND has_website = 1, predict reply"). Visualize the tree — the grader can see the model's reasoning. Handles non-linear relationships that the perceptron misses.

### 6.3 Model 3: Logistic Regression (Extension of Class 4)

Class 4 covered linear regression (find h(x) = wx + b to minimize squared error). Logistic regression extends this to classification by wrapping the linear output in a sigmoid function. The report should explicitly show this connection:
- Linear regression: h(x) = w·x + b (continuous output)
- Logistic regression: h(x) = σ(w·x + b) = 1/(1+e^(-(w·x+b))) (probability output)

**Implementation**: `sklearn.linear_model.LogisticRegression`.

**Why include it**: Bridges the class's regression content to classification. Outputs probabilities (not just 0/1), enabling ROC analysis. Coefficients are directly interpretable as feature importance.

### 6.4 (Bonus) Model 4: Random Forest

Brief comparison with an ensemble of decision trees. Keeps the section short — the point is to show awareness that ensemble methods exist and improve on individual trees. Not a class topic, so position it as "further exploration."

---

## 7. Evaluation Plan

### 7.1 Metrics

| Metric | What It Shows | Rubric Connection |
|--------|---------------|-------------------|
| **ROC-AUC** | Overall discrimination ability across all thresholds | Accuracy of Results (15pts) |
| **Confusion Matrix** | True/false positives and negatives at chosen threshold | Accuracy of Results (15pts) |
| **Precision & Recall** | Trade-off between catching replies vs. false alarms | Solves the Problem (20pts) |
| **Feature Importance** | Which lead attributes matter most | Report Quality (30pts) |

### 7.2 Experiments to Run

1. **Model comparison table**: AUC, accuracy, precision, recall, F1 for all models on the test set
2. **ROC curves**: All models on one plot — visually compare discrimination
3. **Confusion matrices**: Side-by-side for each model at threshold = 0.5
4. **Decision tree visualization**: Export and display the tree at max_depth=5
5. **Logistic regression coefficients**: Bar chart of feature weights — tells the "which features predict replies" story
6. **Perceptron convergence**: Plot training accuracy over epochs to show learning (ties to Class 5 weight-update rule)
7. **Feature importance comparison**: Do all three models agree on the top features?

### 7.3 Validation of Synthetic Data

Since the true data-generating model is known, include a "sanity check" section:
- Show that logistic regression recovers approximately the true coefficients
- Show that noise features get near-zero weight
- This proves the synthetic data is well-constructed (addresses the council's concern about synthetic data credibility)

---

## 8. Report Structure (Mapped to Rubric)

### Report Quality — 30 points

| Section | Content | Est. Pages |
|---------|---------|------------|
| **1. Introduction** | What is Hermes, what problem does the lead scorer solve, why it matters | 1 |
| **2. Hermes as an AI Agent** | PEAS analysis, environment classification, agent type (model-based → utility-based) | 1.5 |
| **3. Problem Definition** | Supervised learning framing using class definition, induction, feature descriptions | 1.5 |
| **4. Dataset** | Synthetic data generation process, distributions, train/test split, class imbalance discussion | 1.5 |
| **5. Models** | Perceptron (with class diagram), Decision Tree, Logistic Regression, brief Random Forest | 3 |
| **6. Results** | All experiments from Section 7.2, tables and plots | 2.5 |
| **7. Discussion** | What the models learned, business implications for Hermes, limitations | 1 |
| **8. Conclusion** | Summary, how this would deploy in the real system | 0.5 |
| **Appendix** | Full code, additional plots | as needed |

**Total: ~12–13 pages** (solid for an intro class, not padded)

### Clarity & Reproducibility — 20 points

- All code in a single Jupyter notebook with clear markdown cells between code
- `requirements.txt` with pinned versions
- Random seed set everywhere (`random_state=42`)
- Dataset generation is deterministic — anyone can re-run and get identical results
- Every plot has axis labels, title, and legend

### Solves the Problem — 20 points

- The problem is clearly stated: "predict which leads will reply to prioritize outreach"
- Models produce actionable output: a reply probability for each lead
- Connect back to Hermes: "a lead with P(reply) > 0.3 should be prioritized for enrichment"
- Show that the best model outperforms random guessing and a naive baseline

### Originality — 15 points

- Real system connection (not a Kaggle dataset or textbook example)
- PEAS + environment classification applied to a real agent (not a toy example)
- Perceptron as a classifier tied back to the class exercise (RGB → lead features)
- Feature engineering from actual database schema, not generic features

### Accuracy of Results — 15 points

- ROC-AUC gives a concrete, comparable metric
- Sanity check: logistic regression should recover the true coefficients (since data was generated by a logistic model — this is a known-answer test)
- Confusion matrices show real performance at operational thresholds
- Noise features should get low importance (validates the models work correctly)

---

## 9. Implementation Timeline

| Day | Task | Deliverable |
|-----|------|-------------|
| **Day 1** | Set up Jupyter notebook, write data generation function with known logistic model, generate 1,000 leads, train/test split | `data_generation.py`, CSV of synthetic leads |
| **Day 2** | Implement all three models (perceptron, decision tree, logistic regression), basic training and prediction | Working model code in notebook |
| **Day 3** | Run all experiments: ROC curves, confusion matrices, feature importance, decision tree viz, perceptron convergence plot | All figures and tables |
| **Day 4** | Write report sections 1–4 (Introduction, PEAS, Problem Definition, Dataset) | Draft of first half |
| **Day 5** | Write report sections 5–8 (Models, Results, Discussion, Conclusion) | Complete draft |
| **Day 6** | Review, polish, verify reproducibility (re-run notebook from scratch), add appendix | Final submission |

---

## 10. Code Architecture

```
lead-quality-scorer/
├── README.md                    # How to run
├── requirements.txt             # sklearn, pandas, matplotlib, seaborn, numpy
├── lead_scorer.ipynb            # Main notebook (all-in-one)
├── data/
│   ├── generate_dataset.py      # Synthetic data generation with known model
│   └── leads_synthetic.csv      # Generated dataset (committed for reproducibility)
├── figures/                     # Exported plots for report
│   ├── roc_curves.png
│   ├── confusion_matrices.png
│   ├── feature_importance.png
│   ├── decision_tree.png
│   └── perceptron_convergence.png
└── report/
    └── lead_quality_scorer_report.pdf
```

---

## 11. Key Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| All models perform similarly on synthetic data | Boring results, thin analysis | Engineer the data with non-linear interactions (e.g., rating × reviews) so the tree outperforms the perceptron. This creates a real performance gap to discuss. |
| Perceptron performs badly | Could look like a poor model choice | Frame it positively: "The perceptron's linear boundary cannot capture the interaction between rating and review count, motivating non-linear models." This is a feature, not a bug. |
| Report is too short | Loses Report Quality points | The PEAS framing, environment classification, and class-concept sections add 2–3 pages of substantive content that most students won't have. |
| Grader questions synthetic data | Loses Accuracy points | The known-model sanity check (recovering true coefficients) proves the data is well-constructed. Explicitly state: "We use synthetic data with a known generative process so we can validate model correctness." |

---

## 12. Class Concepts Checklist

Before submitting, verify the report explicitly references:

- [ ] **PEAS framework** (Class 3) — Section 2.1
- [ ] **Environment classification** (Class 3) — Section 2.2, with all 6 dimensions
- [ ] **Agent types** (Class 3) — Section 2.3, model-based reflex → utility-based
- [ ] **Supervised learning definition** (Class 4) — "Given (x_i, y_i), find h(x) ≈ y"
- [ ] **Induction vs. deduction** (Class 4) — This project uses induction (generalizing from examples)
- [ ] **Linear regression → logistic regression** (Class 4) — Section 6.3 bridge
- [ ] **Decision trees** (Class 4) — Section 6.2 with visualization
- [ ] **Perceptron** (Class 5) — Section 6.1 with architecture diagram
- [ ] **Weighted sum + step function** (Class 5) — Explain perceptron mechanics
- [ ] **Neural network connection** (Class 5) — Brief note: "a perceptron is a single-neuron network; adding layers creates a neural network capable of more complex boundaries"

---

## 13. The One Thing to Do First

**Write the data generation function.** Everything else depends on the dataset. Define the true coefficients, generate 1,000 leads with realistic distributions, sample reply labels, and verify the overall reply rate is 15–18%. Once this works, the rest is execution.
