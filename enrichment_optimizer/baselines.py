"""Baseline solvers for the enrichment knapsack: greedy, random, exact DP."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

Chromosome = list[int]
Lead = dict

DP_CELL_BUDGET = 50_000_000  # guard: skip DP if N × W_scaled exceeds this
DP_SCALE = 100_000  # $0.00001 granularity (costs are $0.001–$0.003)


def _cv(leads: Sequence[Lead]) -> tuple[list[float], list[float]]:
    return (
        [float(l["enrichment_cost"]) for l in leads],
        [float(l["estimated_value"]) for l in leads],
    )


def _total(chromosome: Chromosome, vec: list[float]) -> float:
    return sum(v for g, v in zip(chromosome, vec) if g == 1)


def greedy_knapsack(leads: Sequence[Lead], budget: float) -> Chromosome:
    """Sort by value/cost ratio descending, greedily add while feasible."""
    costs, values = _cv(leads)
    n = len(leads)
    order = sorted(
        range(n),
        key=lambda i: (values[i] / costs[i]) if costs[i] > 0 else float("inf"),
        reverse=True,
    )
    chromo = [0] * n
    remaining = budget
    for i in order:
        if costs[i] <= remaining:
            chromo[i] = 1
            remaining -= costs[i]
    return chromo


@dataclass
class RandomResult:
    best_chromosome: Chromosome
    best_value: float
    mean_value: float
    trials: int


def random_knapsack(
    leads: Sequence[Lead],
    budget: float,
    n_trials: int = 1000,
    seed: int = 42,
) -> RandomResult:
    """Randomly include leads until budget is exhausted; return best + mean over trials."""
    rng = random.Random(seed)
    costs, values = _cv(leads)
    n = len(leads)

    best_chromo: Chromosome = [0] * n
    best_value = 0.0
    total = 0.0

    for _ in range(n_trials):
        order = list(range(n))
        rng.shuffle(order)
        chromo = [0] * n
        remaining = budget
        for i in order:
            if costs[i] <= remaining:
                chromo[i] = 1
                remaining -= costs[i]
        v = _total(chromo, values)
        total += v
        if v > best_value:
            best_value = v
            best_chromo = chromo

    return RandomResult(
        best_chromosome=best_chromo,
        best_value=best_value,
        mean_value=total / n_trials,
        trials=n_trials,
    )


def exact_dp_knapsack(
    leads: Sequence[Lead],
    budget: float,
    scale: int = DP_SCALE,
    cell_budget: int = DP_CELL_BUDGET,
) -> Chromosome | None:
    """Exact 0/1 knapsack via DP. Returns None if the table would exceed cell_budget."""
    costs, values = _cv(leads)
    n = len(leads)
    scaled_costs = [int(round(c * scale)) for c in costs]
    scaled_budget = int(round(budget * scale))

    if n * (scaled_budget + 1) > cell_budget:
        return None

    # dp[i][w] = max value using first i items with capacity w
    dp = [[0.0] * (scaled_budget + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        wi = scaled_costs[i - 1]
        vi = values[i - 1]
        row_prev = dp[i - 1]
        row_cur = dp[i]
        for w in range(scaled_budget + 1):
            best = row_prev[w]
            if wi <= w:
                cand = row_prev[w - wi] + vi
                if cand > best:
                    best = cand
            row_cur[w] = best

    # Backtrack
    chromo = [0] * n
    w = scaled_budget
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            chromo[i - 1] = 1
            w -= scaled_costs[i - 1]
    return chromo


def chromosome_stats(chromosome: Chromosome, leads: Sequence[Lead]) -> dict:
    costs, values = _cv(leads)
    return {
        "total_value": _total(chromosome, values),
        "total_cost": _total(chromosome, costs),
        "leads_selected": sum(chromosome),
    }
