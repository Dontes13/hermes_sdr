"""Baseline solver tests."""

from __future__ import annotations

from itertools import product

from enrichment_optimizer.baselines import (
    chromosome_stats,
    exact_dp_knapsack,
    greedy_knapsack,
    random_knapsack,
)


def test_greedy_feasible(small_pool, small_budget):
    chromo = greedy_knapsack(small_pool, small_budget)
    stats = chromosome_stats(chromo, small_pool)
    assert stats["total_cost"] <= small_budget + 1e-9


def test_greedy_sorted_correctly(small_pool, small_budget):
    """If we halve the budget, greedy should still pick from the top-ratio side."""
    chromo = greedy_knapsack(small_pool, small_budget * 0.3)
    selected_ratios = [
        l["value_to_cost_ratio"] for l, g in zip(small_pool, chromo) if g == 1
    ]
    unselected_ratios = [
        l["value_to_cost_ratio"] for l, g in zip(small_pool, chromo) if g == 0
    ]
    # With a ratio-greedy fill, the median selected ratio should beat the median unselected.
    if selected_ratios and unselected_ratios:
        selected_ratios.sort()
        unselected_ratios.sort()
        assert selected_ratios[len(selected_ratios) // 2] > unselected_ratios[
            len(unselected_ratios) // 2
        ]


def test_random_feasible(small_pool, small_budget):
    res = random_knapsack(small_pool, small_budget, n_trials=100, seed=7)
    stats = chromosome_stats(res.best_chromosome, small_pool)
    assert stats["total_cost"] <= small_budget + 1e-9


def test_random_mean_worse_than_greedy(small_pool, small_budget):
    res = random_knapsack(small_pool, small_budget, n_trials=200, seed=9)
    greedy_chromo = greedy_knapsack(small_pool, small_budget)
    greedy_stats = chromosome_stats(greedy_chromo, small_pool)
    assert res.mean_value < greedy_stats["total_value"]


def test_dp_matches_brute_force(tiny_pool, tiny_budget):
    """Exhaustively enumerate all 2^12 subsets; confirm DP returns the same optimum."""
    n = len(tiny_pool)
    costs = [l["enrichment_cost"] for l in tiny_pool]
    values = [l["estimated_value"] for l in tiny_pool]

    best_brute = 0.0
    for bits in product([0, 1], repeat=n):
        c = sum(w for g, w in zip(bits, costs) if g == 1)
        if c <= tiny_budget:
            v = sum(w for g, w in zip(bits, values) if g == 1)
            if v > best_brute:
                best_brute = v

    dp_chromo = exact_dp_knapsack(tiny_pool, tiny_budget)
    assert dp_chromo is not None
    stats = chromosome_stats(dp_chromo, tiny_pool)
    assert stats["total_cost"] <= tiny_budget + 1e-9
    assert abs(stats["total_value"] - best_brute) < 1e-6
