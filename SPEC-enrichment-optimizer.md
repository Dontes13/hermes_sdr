# Enrichment Budget Optimizer — Build Spec

## Overview

A genetic algorithm that solves the daily enrichment allocation problem: given a pool of prospected leads, each with an estimated value and a variable enrichment cost, select the optimal subset to enrich under a daily budget constraint. This is a 0/1 knapsack variant.

The project serves dual purposes:
1. **Class project** (IFSA CS38-09, Intro to AI): GA implementation with convergence analysis, parameter sensitivity, and baseline comparisons. Professor has approved the approach and is fine with the DP comparison.
2. **Hermes production**: replaces the current FIFO enrichment logic in `campaign_runner.py` with budget-aware prioritization.

Professor wants runnable code.

---

## The Problem

Every day, Hermes prospects new leads via Google Places. Before a lead can receive a cold email, it must be **enriched** — Gemini scrapes the lead's website and extracts intel (owner name, email, specialties, etc.). Enrichment costs real money ($0.002/lead for Gemini Flash, plus ~30% of leads die during enrichment because they have no email, wasting that spend).

Currently Hermes enriches leads in arbitrary order up to a per-tick cap. There's no intelligence about *which* leads to enrich. If the daily budget is tight, low-value leads consume budget that could have gone to high-value ones.

**The optimization question**: Given a pool of N un-enriched leads, each with an estimated value and enrichment cost, and a fixed daily budget B, which subset should we enrich to maximize total expected value?

This is the **0/1 knapsack problem**: each lead is an item with a weight (cost) and a value (expected reply value). The budget is the knapsack capacity.

---

## PEAS Analysis (Class 3)

Frame the enrichment optimizer as an intelligent agent using the PEAS framework from class.

| Dimension | Description |
|-----------|-------------|
| **Performance** | Maximize total expected value of enriched leads within daily budget. Measured by: total value captured, budget utilization (% of budget spent), value density (total value / total cost). |
| **Environment** | Pool of N prospected leads, each with observable features (Google rating, review count, website presence, business type) and derived attributes (estimated enrichment cost, estimated reply value). Environment is **fully observable** (all lead features known at decision time), **deterministic** (costs and values are fixed for a given day), **episodic** (each day's allocation is independent), **static** (leads don't change while we're deciding), **discrete** (enrich or don't — binary per lead), **single-agent**. |
| **Actuators** | Select a subset of leads to enrich (binary include/exclude decision per lead). |
| **Sensors** | Google Places API data (rating, reviews, website, phone, business types) and enrichment cost estimates from the Hermes cost model. |

### Agent Type

The current Hermes campaign runner is a **simple reflex agent** for enrichment — it just grabs the next N leads in queue order. The GA optimizer upgrades this to a **utility-based agent** that assigns expected value to each lead and optimizes the allocation to maximize total utility under constraints. This is the agent type progression covered in Class 3.

### Environment Classification (Class 3)

- **Fully observable**: all lead features and costs are known before deciding
- **Deterministic**: given the same leads and budget, the optimal subset is fixed
- **Episodic**: each day's enrichment batch is a standalone decision (no multi-day dependency)
- **Static**: leads don't change during the optimization
- **Discrete**: binary decision per lead (enrich or skip)
- **Single-agent**: no adversary

---

## Supervised Learning Connection (Class 4)

While the GA itself is an optimization algorithm (not supervised learning), the **value estimation** that feeds the GA uses supervised learning concepts from class:

- Each lead's expected value is estimated from prospect-time features — this is a function approximation problem: given features x, estimate value v(x).
- For the synthetic dataset, values are generated from a known function (like the lead scorer's logistic model). In production, values would come from a trained model.
- This connects to the Class 4 definition: "Given examples (x_i, y_i), find h such that h(x) ≈ y" — here y is the lead's value.

---

## Phase 1: Standalone Module

### 1.1 Files to create

```
enrichment_optimizer/
├── __init__.py
├── generate.py          # synthetic lead pool generator
├── ga.py                # genetic algorithm implementation
├── baselines.py         # greedy and random baselines
├── optimize.py          # main entry point: run GA + baselines, print results
├── experiments.py       # parameter sensitivity & scaling experiments
├── evaluate.py          # plots and analysis
├── data/                # generated CSVs
│   └── .gitkeep
├── figures/             # exported plots
│   └── .gitkeep
└── requirements.txt
```

No Hermes dependencies. Pure Python + numpy + matplotlib.

### 1.2 `requirements.txt`

```
numpy>=1.26.0,<2.0.0
pandas==2.2.3
matplotlib==3.9.2
seaborn==0.13.2
```

No sklearn needed — the GA is implemented from scratch.

---

### 1.3 `generate.py`

Generates a pool of synthetic leads with costs and values.

**Lead attributes:**

| Field | Distribution | Notes |
|-------|-------------|-------|
| `lead_id` | Sequential int | Just an identifier |
| `google_rating` | N(4.2, 0.5) clipped [1.0, 5.0], null 10% | From real Places data |
| `google_reviews` | lognormal(3.0, 1.2), 0 if no rating | Right-skewed |
| `has_website` | Bernoulli(0.75) | ~25% lack websites |
| `has_phone` | Bernoulli(0.85) | Most have phone |
| `business_type` | Categorical: real_estate (50%), insurance (15%), finance (20%), other (15%) | Hermes targets |
| `city` | Categorical: 8 Florida cities, weighted | Miami 20%, rest spread |
| `estimated_employees` | lognormal(3.0, 1.0), rounded to int, clipped [1, 500] | Right-skewed: most are small shops, some are large brokerages |

**Deal size model (real Hermes pricing):**

Hermes quotes clients based on company size:
- **50+ employees** → $5,000 deal
- **Under 50 employees** → $3,000 deal

This is the actual revenue per closed deal, so it directly drives the lead's value in the knapsack.

**Derived attributes (the knapsack inputs):**

| Field | How it's computed | Notes |
|-------|------------------|-------|
| `deal_size` | $5,000 if `estimated_employees >= 50`, else $3,000 | Real Hermes pricing tiers |
| `reply_probability` | Function of features: `sigmoid(-2.5 + 0.6*(rating/5) + 0.3*log(reviews+1)/6 + 0.4*has_website + 0.2*is_real_estate + noise)` | Estimated likelihood the lead replies. Range ~5–40%. |
| `enrichment_cost` | Base $0.002 × cost multiplier | Multiplier varies by lead: leads with websites cost 1.0x (standard scrape), leads without websites cost 0.5x (quick fail), leads with large websites (reviews > 200) cost 1.5x (more tokens). Range: $0.001–$0.003 per lead. |
| `estimated_value` | `deal_size × reply_probability` | Expected revenue from enriching this lead. A 50-person brokerage with 30% reply chance = $5,000 × 0.30 = $1,500 expected value. A 10-person shop with 8% reply chance = $3,000 × 0.08 = $240. This creates real tradeoffs: do you spend enrichment budget on a long-shot big deal or a likely small one? |
| `value_to_cost_ratio` | `estimated_value / enrichment_cost` | For greedy baseline sorting |

**Budget**: Set daily budget B = cost to enrich ~60% of the pool. For 200 leads at avg $0.002, that's about $0.24. This forces the GA to make real tradeoffs — it can't take everything.

**Output**: `data/leads_pool.csv` with all fields. Also generate pools of size 50, 100, 200, 500 for scaling experiments.

**Acceptance criteria:**
- Default pool: 200 leads
- Budget constrains selection to ~60% of pool (can't take all)
- Deterministic with `seed=42`
- At least 3 leads should have obviously high value-to-cost ratios (for sanity checking)
- At least 3 leads should have obviously bad ratios (high cost, low value)

---

### 1.4 `ga.py`

The genetic algorithm. Implemented from scratch — no libraries.

**Representation:**

```python
# Chromosome: binary list of length N
# chromosome[i] = 1 means "enrich lead i", 0 means "skip"
# Example for 5 leads: [1, 0, 1, 1, 0] → enrich leads 0, 2, 3
```

**Fitness function:**

```python
def fitness(chromosome: list[int], leads: list[dict], budget: float) -> float:
    """Total value of selected leads. Penalize if over budget."""
    total_cost = sum(
        leads[i]["enrichment_cost"] for i, gene in enumerate(chromosome) if gene == 1
    )
    total_value = sum(
        leads[i]["estimated_value"] for i, gene in enumerate(chromosome) if gene == 1
    )
    if total_cost > budget:
        return total_value * 0.01  # heavy penalty, not zero (preserves selection pressure)
    return total_value
```

**GA parameters (defaults):**

| Parameter | Default | Range for sensitivity analysis |
|-----------|---------|-------------------------------|
| `population_size` | 50 | [20, 50, 100, 200] |
| `generations` | 100 | [50, 100, 200, 500] |
| `crossover_rate` | 0.8 | [0.5, 0.7, 0.8, 0.9] |
| `mutation_rate` | 0.02 | [0.005, 0.01, 0.02, 0.05, 0.1] |
| `tournament_size` | 3 | [2, 3, 5] |
| `elitism_count` | 2 | [0, 1, 2, 5] |

**Operators:**

1. **Initialization**: Random binary chromosomes. To seed feasibility, generate ~20% of initial population using the greedy solution with random perturbations (flip 5-10 random bits).

2. **Selection — Tournament selection**:
   ```python
   def tournament_select(population, fitnesses, k=3):
       """Pick k random individuals, return the one with highest fitness."""
       candidates = random.sample(range(len(population)), k)
       best = max(candidates, key=lambda i: fitnesses[i])
       return population[best]
   ```

3. **Crossover — Uniform crossover**:
   ```python
   def uniform_crossover(parent1, parent2, rate=0.8):
       """Each gene independently inherited from either parent."""
       if random.random() > rate:
           return parent1[:], parent2[:]
       child1, child2 = [], []
       for g1, g2 in zip(parent1, parent2):
           if random.random() < 0.5:
               child1.append(g1); child2.append(g2)
           else:
               child1.append(g2); child2.append(g1)
       return child1, child2
   ```

4. **Mutation — Bit-flip mutation**:
   ```python
   def mutate(chromosome, rate=0.02):
       """Each gene has `rate` probability of flipping."""
       return [gene if random.random() > rate else 1 - gene for gene in chromosome]
   ```

5. **Elitism**: Top `elitism_count` individuals pass directly to next generation unchanged.

**Budget repair heuristic** (optional, improves convergence):
After crossover/mutation, if a chromosome exceeds the budget, randomly drop selected leads (gene 1→0) starting with the worst value-to-cost ratio until feasible.

**Return value:**

```python
@dataclass
class GAResult:
    best_chromosome: list[int]
    best_fitness: float
    best_cost: float
    convergence_history: list[float]  # best fitness per generation
    avg_fitness_history: list[float]  # average fitness per generation
    generations_run: int
    population_size: int
    leads_selected: int
    budget_used: float
    budget_total: float
```

**Acceptance criteria:**
- GA runs without errors on pools of 50–500 leads
- GA result respects budget constraint (total cost ≤ budget)
- GA fitness ≥ greedy fitness × 0.95 (should be close to or better than greedy)
- Convergence history is monotonically non-decreasing (elitism guarantees this)
- Deterministic with `seed=42`

---

### 1.5 `baselines.py`

Two comparison baselines.

**Greedy**:
```python
def greedy_knapsack(leads: list[dict], budget: float) -> list[int]:
    """Sort by value/cost ratio descending, greedily add until budget full."""
    indexed = [(i, lead["estimated_value"] / lead["enrichment_cost"]) for i, lead in enumerate(leads)]
    indexed.sort(key=lambda x: x[1], reverse=True)
    
    chromosome = [0] * len(leads)
    remaining = budget
    for i, _ in indexed:
        if leads[i]["enrichment_cost"] <= remaining:
            chromosome[i] = 1
            remaining -= leads[i]["enrichment_cost"]
    return chromosome
```

**Random**:
```python
def random_knapsack(leads: list[dict], budget: float, seed=None) -> list[int]:
    """Randomly include leads until budget is exhausted. Run 1000 times, return best."""
    # Average of 1000 random feasible solutions as the baseline
```

**Acceptance criteria:**
- Greedy always produces a feasible solution (within budget)
- Greedy value ≥ random value (sanity check)
- Both return the same chromosome format as the GA

---

### 1.6 `optimize.py`

Main entry point. Run as `python -m enrichment_optimizer.optimize`.

**What it does:**
1. Load lead pool from `data/leads_pool.csv` (or generate if missing)
2. Set budget B
3. Run greedy baseline → print result
4. Run random baseline (1000 iterations) → print average and best
5. Run GA with default parameters → print result
6. Print comparison table:

```
╔══════════════╦═══════════╦══════════╦════════════╦═══════════════╗
║ Method       ║ Value     ║ Cost     ║ Leads      ║ vs Greedy     ║
╠══════════════╬═══════════╬══════════╬════════════╬═══════════════╣
║ Random (avg) ║ $X.XX     ║ $X.XXXX  ║ XX/200     ║ -XX.X%        ║
║ Random (best)║ $X.XX     ║ $X.XXXX  ║ XX/200     ║ -X.X%         ║
║ Greedy       ║ $X.XX     ║ $X.XXXX  ║ XX/200     ║ baseline      ║
║ GA           ║ $X.XX     ║ $X.XXXX  ║ XX/200     ║ +X.X%         ║
╚══════════════╩═══════════╩══════════╩════════════╩═══════════════╝
```

7. Save GA convergence history to `data/convergence.csv`

**Acceptance criteria:**
- Runs end-to-end without errors
- GA value ≥ 95% of greedy value
- All solutions are feasible (within budget)
- Comparison table prints clearly

---

### 1.7 `experiments.py`

Parameter sensitivity and scaling experiments. Run as `python -m enrichment_optimizer.experiments`.

**Experiment 1 — Mutation rate sensitivity:**
Run GA with mutation rates [0.005, 0.01, 0.02, 0.05, 0.1] on the 200-lead pool. 5 runs each (different seeds). Record best fitness and generations to converge (within 1% of final). Save results to `data/mutation_sensitivity.csv`.

**Experiment 2 — Population size sensitivity:**
Run GA with population sizes [20, 50, 100, 200] on the 200-lead pool. 5 runs each. Record best fitness, convergence speed, and wall-clock time. Save to `data/population_sensitivity.csv`.

**Experiment 3 — Scaling:**
Run GA and greedy on pools of size [50, 100, 200, 500]. Record fitness, time, and GA-vs-greedy gap at each size. Save to `data/scaling.csv`.

**Experiment 4 — Budget tightness:**
Run GA on 200 leads with budget set to [30%, 50%, 60%, 80%, 100%] of total pool cost. Record fitness and how many leads are selected at each level. Save to `data/budget_sensitivity.csv`.

**Acceptance criteria:**
- All experiments complete without errors
- Results are deterministic (seeded)
- CSV files are saved for `evaluate.py` to plot

---

### 1.8 `evaluate.py`

Generates all plots. Run as `python -m enrichment_optimizer.evaluate`.

**Outputs:**

| File | What |
|------|------|
| `figures/convergence.png` | GA best fitness and average fitness per generation (dual y-axis or dual line). Show greedy baseline as a horizontal dashed line. |
| `figures/ga_vs_baselines.png` | Bar chart: Random avg, Random best, Greedy, GA. Clear visual of relative performance. |
| `figures/mutation_sensitivity.png` | Line plot: mutation rate (x) vs best fitness (y), with error bars from 5 runs. |
| `figures/population_sensitivity.png` | Line plot: population size (x) vs best fitness (y), with convergence speed as secondary metric. |
| `figures/scaling.png` | Dual plot: pool size (x) vs fitness gap between GA and greedy (y1) and wall-clock time (y2). |
| `figures/budget_sensitivity.png` | Line plot: budget % (x) vs leads selected (y1) and total value captured (y2). |
| `figures/chromosome_heatmap.png` | Heatmap of top 10 chromosomes from final generation, showing which leads each selects. Visual proof that good solutions converge to similar subsets. |

**Acceptance criteria:**
- All 7 PNGs generated, 300 dpi
- Every plot has axis labels, title, legend where applicable
- Convergence plot clearly shows the GA approaching/exceeding the greedy line

---

## Phase 1.5: Report Content

`evaluate.py` should also generate `data/report_sections.md` with pre-written sections:

### 1.5.1 PEAS Table
The full PEAS analysis from the section above, formatted for the report.

### 1.5.2 Problem Formulation
Formal statement: "Given N items, each with value v_i and cost c_i, and a capacity B, find binary vector x = (x_1, ..., x_N) that maximizes Σ(v_i · x_i) subject to Σ(c_i · x_i) ≤ B and x_i ∈ {0, 1}."

### 1.5.3 GA Design Justification
For each design choice, explain WHY:
- **Binary chromosome**: natural mapping — each gene is a yes/no decision for one lead
- **Tournament selection (k=3)**: balances selection pressure vs diversity. k=2 too weak, k=5 too greedy.
- **Uniform crossover**: better than single-point for problems where good genes aren't positionally clustered (lead quality is independent across positions)
- **Bit-flip mutation**: standard for binary chromosomes. Rate of 0.02 = ~4 flips per chromosome on 200 leads, enough to explore without destroying good solutions.
- **Elitism (2)**: guarantees best-so-far is never lost. Proven to improve GA convergence.

### 1.5.4 Synthetic Data Justification
Same framing as the lead scorer spec — synthetic data calibrated against real Hermes cost model ($0.002/lead enrichment, 30% waste factor from `cost.ts`). Feature distributions match real Google Places API responses.

### 1.5.5 Limitations
- GA doesn't guarantee optimality (but for 200 items, exact DP gives the ground truth to compare against)
- Estimated lead values are heuristic, not learned from real reply data yet
- Budget model assumes independent enrichment costs (in reality, batch API calls could change pricing)

---

## Phase 2: Testing

### 2.1 Unit tests (`test_ga.py`)

```
test_fitness_within_budget          → returns total value
test_fitness_over_budget            → returns penalized value (< total_value)
test_tournament_select              → returns valid index, higher fitness wins more often
test_uniform_crossover              → children are same length as parents
test_mutate_rate_zero               → chromosome unchanged
test_mutate_rate_one                → every gene flipped
test_elitism_preserved              → best from gen N appears in gen N+1
```

### 2.2 Unit tests (`test_baselines.py`)

```
test_greedy_feasible                → total cost ≤ budget
test_greedy_sorted_correctly        → highest value/cost leads selected first
test_random_feasible                → all random solutions within budget
test_random_worse_than_greedy       → average random < greedy (over 100 runs)
```

### 2.3 Integration test (`test_pipeline.py`)

```
test_full_pipeline:
    1. generate.py → CSV exists, 200 rows, costs and values in expected ranges
    2. optimize.py → GA runs, result feasible, GA ≥ 95% of greedy
    3. experiments.py → all CSV outputs exist and have expected columns
```

---

## Phase 3: Hermes Integration

### 3.1 Add to agent

```
agent/src/functions/enrichment_optimizer/
├── __init__.py
├── ga.py         # copied from enrichment_optimizer/ga.py
└── baselines.py  # copied, used as fallback if GA is too slow
```

### 3.2 Modify `campaign_runner.py`

Current enrich step (lines 169–189) grabs leads in arbitrary order:

```python
new_leads = (
    supabase.table("leads")
    .select("id")
    .eq("campaign_id", campaign_id)
    .eq("status", "new")
    .limit(ENRICH_PER_TICK)
    .execute()
)
```

New code:

```python
from agent.src.functions.enrichment_optimizer.ga import run_ga, estimate_lead_value, estimate_enrichment_cost

DAILY_ENRICH_BUDGET = 0.30  # $0.30/day default

# 2. Optimize which leads to enrich
new_leads = (
    supabase.table("leads")
    .select("*")
    .eq("campaign_id", campaign_id)
    .eq("status", "new")
    .execute()
)

if len(new_leads.data) <= ENRICH_PER_TICK:
    # Small pool — no optimization needed, just enrich all
    to_enrich = new_leads.data
else:
    # Estimate value and cost for each lead
    leads_with_estimates = []
    for lead in new_leads.data:
        lead["estimated_value"] = estimate_lead_value(lead)
        lead["enrichment_cost"] = estimate_enrichment_cost(lead)
        leads_with_estimates.append(lead)

    # Run GA (or greedy fallback for speed)
    result = run_ga(leads_with_estimates, budget=DAILY_ENRICH_BUDGET, generations=50)
    to_enrich = [leads_with_estimates[i] for i, gene in enumerate(result.best_chromosome) if gene == 1]
    to_enrich = to_enrich[:ENRICH_PER_TICK]  # respect per-tick cap

enriched = 0
for lead in to_enrich:
    try:
        ok = enrich(lead["id"])
        enriched += 1 if ok else 0
        summary["enriched"] += 1 if ok else 0
    except Exception as e:
        summary["errors"].append(f"enrich {lead['id']}: {e}")
```

### 3.3 Value and cost estimation functions

These go in `ga.py` and use real Hermes data:

```python
import numpy as np

def estimate_enrichment_cost(lead: dict) -> float:
    """Estimate enrichment cost based on lead characteristics.
    Base: $0.002 (Gemini Flash). Adjusted by website complexity."""
    base = 0.002
    if not lead.get("website"):
        return base * 0.5   # quick fail, minimal tokens
    # Leads with higher review counts tend to have bigger websites
    reviews = lead.get("google_reviews") or 0
    if reviews > 200:
        return base * 1.5   # larger site, more scraping
    return base

def estimate_lead_value(lead: dict) -> float:
    """Estimate expected value of enriching this lead.
    expected_value = deal_size × reply_probability.
    
    Deal sizes (real Hermes pricing):
      - 50+ employees → $5,000
      - Under 50      → $3,000
    """
    rating = lead.get("google_rating") or 0
    reviews = lead.get("google_reviews") or 0
    has_website = 1.0 if lead.get("website") else 0.0
    intel = lead.get("intel_json") or {}
    types = intel.get("types", [])
    is_target = 1.0 if "real_estate_agency" in types else 0.0
    employees = lead.get("estimated_employees") or 10

    # Deal size based on company size
    deal_size = 5000.0 if employees >= 50 else 3000.0

    # Reply probability estimate
    logit = -2.5 + 0.6 * (rating / 5.0) + 0.3 * np.log1p(reviews) / 6.0 + 0.4 * has_website + 0.2 * is_target
    reply_prob = 1.0 / (1.0 + np.exp(-logit))

    return round(deal_size * reply_prob, 2)
```

---

## Run Commands

```bash
# Phase 1 — build and run
cd enrichment_optimizer
pip install -r requirements.txt
python -m enrichment_optimizer.generate        # → data/leads_pool.csv + scaling pools
python -m enrichment_optimizer.optimize        # → comparison table + data/convergence.csv
python -m enrichment_optimizer.experiments     # → data/*.csv for all experiments
python -m enrichment_optimizer.evaluate        # → figures/*.png + data/report_sections.md

# Phase 2 — test
pytest enrichment_optimizer/ -v
```

---

## What Gets Submitted

```
enrichment_optimizer/
├── __init__.py
├── generate.py
├── ga.py
├── baselines.py
├── optimize.py
├── experiments.py
├── evaluate.py
├── requirements.txt
├── data/
│   ├── leads_pool.csv
│   ├── convergence.csv
│   ├── mutation_sensitivity.csv
│   ├── population_sensitivity.csv
│   ├── scaling.csv
│   ├── budget_sensitivity.csv
│   └── report_sections.md
└── figures/
    ├── convergence.png
    ├── ga_vs_baselines.png
    ├── mutation_sensitivity.png
    ├── population_sensitivity.png
    ├── scaling.png
    ├── budget_sensitivity.png
    └── chromosome_heatmap.png
```

Plus the report (format TBD). No Hermes code included.
