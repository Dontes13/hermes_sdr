"""Parameter sensitivity and scaling experiments.

Writes four CSVs to data/ for evaluate.py to plot.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

from . import generate as gen_mod
from .baselines import chromosome_stats, exact_dp_knapsack, greedy_knapsack
from .ga import GAConfig, run_ga

HERE = Path(__file__).parent
DATA = HERE / "data"

SEEDS = [42, 43, 44, 45, 46]
MUTATION_RATES = [0.005, 0.01, 0.02, 0.05, 0.1]
POPULATION_SIZES = [20, 50, 100, 200]
SCALING_POOLS = [50, 100, 200, 500]
BUDGET_PCTS = [0.30, 0.50, 0.60, 0.80, 1.00]


def _gens_to_converge(history: list[float], tol: float = 0.01) -> int:
    if not history:
        return 0
    final = history[-1]
    target = final * (1 - tol)
    for i, v in enumerate(history):
        if v >= target:
            return i + 1
    return len(history)


def _load_default_leads() -> tuple[list[dict], float]:
    if not (DATA / "leads_pool.csv").exists() or not (DATA / "budget.json").exists():
        gen_mod.main()
    df = gen_mod.load_pool()
    return df.to_dict(orient="records"), gen_mod.load_budget()


def _load_scaling_leads(size: int) -> list[dict]:
    path = DATA / f"leads_pool_{size}.csv"
    if not path.exists():
        gen_mod.main()
    return gen_mod.load_pool(path).to_dict(orient="records")


def _budget_for_pool(leads: list[dict], fraction: float) -> float:
    return sum(l["enrichment_cost"] for l in leads) * fraction


def experiment_mutation(leads: list[dict], budget: float) -> None:
    rows = []
    for rate in MUTATION_RATES:
        for seed in SEEDS:
            cfg = GAConfig(mutation_rate=rate)
            res = run_ga(leads, budget, cfg, seed=seed)
            rows.append(
                {
                    "mutation_rate": rate,
                    "seed": seed,
                    "best_fitness": res.best_fitness,
                    "gens_to_converge": _gens_to_converge(res.convergence_history),
                }
            )
    _write_csv(DATA / "mutation_sensitivity.csv", rows)
    print(f"wrote mutation_sensitivity.csv ({len(rows)} rows)")


def experiment_population(leads: list[dict], budget: float) -> None:
    rows = []
    for pop in POPULATION_SIZES:
        for seed in SEEDS:
            cfg = GAConfig(population_size=pop)
            t0 = time.perf_counter()
            res = run_ga(leads, budget, cfg, seed=seed)
            elapsed = time.perf_counter() - t0
            rows.append(
                {
                    "pop_size": pop,
                    "seed": seed,
                    "best_fitness": res.best_fitness,
                    "wall_time_s": elapsed,
                    "gens_to_converge": _gens_to_converge(res.convergence_history),
                }
            )
    _write_csv(DATA / "population_sensitivity.csv", rows)
    print(f"wrote population_sensitivity.csv ({len(rows)} rows)")


def experiment_scaling() -> None:
    rows = []
    for size in SCALING_POOLS:
        leads = _load_scaling_leads(size)
        budget = _budget_for_pool(leads, 0.60)

        t0 = time.perf_counter()
        greedy_chromo = greedy_knapsack(leads, budget)
        greedy_elapsed = time.perf_counter() - t0
        g_stats = chromosome_stats(greedy_chromo, leads)
        rows.append(
            {
                "pool_size": size,
                "method": "greedy",
                "fitness": g_stats["total_value"],
                "wall_time_s": greedy_elapsed,
            }
        )

        t0 = time.perf_counter()
        res = run_ga(leads, budget, GAConfig(), seed=42)
        ga_elapsed = time.perf_counter() - t0
        rows.append(
            {
                "pool_size": size,
                "method": "ga",
                "fitness": res.best_fitness,
                "wall_time_s": ga_elapsed,
            }
        )

        t0 = time.perf_counter()
        dp_chromo = exact_dp_knapsack(leads, budget)
        dp_elapsed = time.perf_counter() - t0
        if dp_chromo is not None:
            d_stats = chromosome_stats(dp_chromo, leads)
            rows.append(
                {
                    "pool_size": size,
                    "method": "dp",
                    "fitness": d_stats["total_value"],
                    "wall_time_s": dp_elapsed,
                }
            )
    _write_csv(DATA / "scaling.csv", rows)
    print(f"wrote scaling.csv ({len(rows)} rows)")


def experiment_budget(leads: list[dict]) -> None:
    total_cost = sum(l["enrichment_cost"] for l in leads)
    rows = []
    for pct in BUDGET_PCTS:
        b = total_cost * pct
        for seed in SEEDS:
            res = run_ga(leads, b, GAConfig(), seed=seed)
            stats = chromosome_stats(res.best_chromosome, leads)
            rows.append(
                {
                    "budget_pct": pct,
                    "seed": seed,
                    "leads_selected": stats["leads_selected"],
                    "total_value": stats["total_value"],
                    "total_cost": stats["total_cost"],
                }
            )
    _write_csv(DATA / "budget_sensitivity.csv", rows)
    print(f"wrote budget_sensitivity.csv ({len(rows)} rows)")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    DATA.mkdir(exist_ok=True)
    leads, budget = _load_default_leads()

    print("Experiment 1: mutation rate sensitivity")
    experiment_mutation(leads, budget)

    print("Experiment 2: population size sensitivity")
    experiment_population(leads, budget)

    print("Experiment 3: scaling")
    experiment_scaling()

    print("Experiment 4: budget tightness")
    experiment_budget(leads)


if __name__ == "__main__":
    main()
