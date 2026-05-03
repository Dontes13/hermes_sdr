"""Main entry: run GA + baselines on the default pool and print a comparison table.

Outputs:
  - data/convergence.csv (columns: generation, best_fitness, avg_fitness)
  - data/results_summary.json (used by evaluate.py to avoid re-running the GA)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from . import generate as gen_mod
from .baselines import (
    chromosome_stats,
    exact_dp_knapsack,
    greedy_knapsack,
    random_knapsack,
)
from .ga import GAConfig, run_ga

HERE = Path(__file__).parent
DATA = HERE / "data"


def _ensure_pool():
    if not (DATA / "leads_pool.csv").exists() or not (DATA / "budget.json").exists():
        gen_mod.main()


def _leads_list(df) -> list[dict]:
    return df.to_dict(orient="records")


def _pct(a: float, b: float) -> str:
    if b <= 0:
        return "  n/a"
    delta = (a - b) / b * 100.0
    return f"{delta:+.1f}%"


def _print_table(rows: list[dict], greedy_value: float) -> None:
    header = f"{'Method':<14} {'Value':>10} {'Cost':>10} {'Leads':>10} {'vs Greedy':>12}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in rows:
        print(
            f"{r['method']:<14} "
            f"${r['value']:>9.2f} "
            f"${r['cost']:>9.4f} "
            f"{r['leads']:>4}/{r['pool']:<5} "
            f"{_pct(r['value'], greedy_value):>12}"
        )
    print(sep)


def main(seed: int = 42) -> dict:
    _ensure_pool()
    df = gen_mod.load_pool()
    budget = gen_mod.load_budget()
    leads = _leads_list(df)
    n = len(leads)

    # Random
    rand = random_knapsack(leads, budget, n_trials=1000, seed=seed)
    rand_best_stats = chromosome_stats(rand.best_chromosome, leads)

    # Greedy
    greedy_chromo = greedy_knapsack(leads, budget)
    greedy_stats = chromosome_stats(greedy_chromo, leads)

    # Exact DP
    dp_chromo = exact_dp_knapsack(leads, budget)
    dp_stats = chromosome_stats(dp_chromo, leads) if dp_chromo is not None else None

    # GA
    ga_result = run_ga(leads, budget, GAConfig(), seed=seed)
    ga_stats = chromosome_stats(ga_result.best_chromosome, leads)

    rows = [
        {
            "method": "Random (avg)",
            "value": rand.mean_value,
            "cost": 0.0,
            "leads": 0,
            "pool": n,
        },
        {
            "method": "Random (best)",
            "value": rand.best_value,
            "cost": rand_best_stats["total_cost"],
            "leads": rand_best_stats["leads_selected"],
            "pool": n,
        },
        {
            "method": "Greedy",
            "value": greedy_stats["total_value"],
            "cost": greedy_stats["total_cost"],
            "leads": greedy_stats["leads_selected"],
            "pool": n,
        },
        {
            "method": "GA",
            "value": ga_stats["total_value"],
            "cost": ga_stats["total_cost"],
            "leads": ga_stats["leads_selected"],
            "pool": n,
        },
    ]
    if dp_stats is not None:
        rows.append(
            {
                "method": "DP (exact)",
                "value": dp_stats["total_value"],
                "cost": dp_stats["total_cost"],
                "leads": dp_stats["leads_selected"],
                "pool": n,
            }
        )

    print(f"Pool: {n} leads | Budget: ${budget:.4f}")
    _print_table(rows, greedy_stats["total_value"])

    if dp_stats is not None:
        gap = ga_stats["total_value"] / dp_stats["total_value"] * 100.0
        print(f"GA optimality vs DP: {gap:.2f}%")

    # Convergence CSV
    with (DATA / "convergence.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["generation", "best_fitness", "avg_fitness"])
        for i, (bf, af) in enumerate(
            zip(ga_result.convergence_history, ga_result.avg_fitness_history)
        ):
            w.writerow([i, bf, af])

    summary = {
        "pool_size": n,
        "budget": budget,
        "random": {
            "mean_value": rand.mean_value,
            "best_value": rand.best_value,
            "best_cost": rand_best_stats["total_cost"],
            "best_leads": rand_best_stats["leads_selected"],
        },
        "greedy": greedy_stats,
        "ga": {
            "best_fitness": ga_result.best_fitness,
            "total_value": ga_stats["total_value"],
            "total_cost": ga_stats["total_cost"],
            "leads_selected": ga_stats["leads_selected"],
            "generations_run": ga_result.generations_run,
            "population_size": ga_result.population_size,
        },
        "dp": dp_stats,
        "ga_over_greedy_pct": (
            ga_stats["total_value"] / greedy_stats["total_value"] * 100.0
            if greedy_stats["total_value"] > 0
            else None
        ),
        "ga_over_dp_pct": (
            ga_stats["total_value"] / dp_stats["total_value"] * 100.0
            if dp_stats and dp_stats["total_value"] > 0
            else None
        ),
    }
    (DATA / "results_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {DATA / 'convergence.csv'}")
    print(f"wrote {DATA / 'results_summary.json'}")
    return summary


if __name__ == "__main__":
    main()
