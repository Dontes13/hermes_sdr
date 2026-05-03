"""GA unit tests."""

from __future__ import annotations

import random

import pytest

from enrichment_optimizer.ga import (
    GAConfig,
    bit_flip_mutate,
    budget_repair,
    fitness,
    run_ga,
    tournament_select,
    uniform_crossover,
)


def test_fitness_within_budget(small_pool, small_budget):
    costs = [l["enrichment_cost"] for l in small_pool]
    values = [l["estimated_value"] for l in small_pool]
    chromo = [0] * len(small_pool)
    chromo[0] = 1  # cheap selection
    assert fitness(chromo, costs, values, small_budget) == values[0]


def test_fitness_over_budget_is_penalized(small_pool):
    costs = [l["enrichment_cost"] for l in small_pool]
    values = [l["estimated_value"] for l in small_pool]
    chromo = [1] * len(small_pool)  # select everything
    tight_budget = sum(costs) * 0.1
    penalized = fitness(chromo, costs, values, tight_budget)
    total_value = sum(values)
    assert penalized < total_value
    assert penalized == pytest.approx(total_value * 0.01)


def test_tournament_select_prefers_fitter():
    rng = random.Random(0)
    pop = [[0], [0], [0], [0]]
    fitnesses = [1.0, 2.0, 3.0, 10.0]
    wins_best = sum(
        tournament_select(pop, fitnesses, k=3, rng=rng) == pop[3] for _ in range(200)
    )
    assert wins_best > 100  # best should win the majority of tournaments


def test_uniform_crossover_length_invariant():
    rng = random.Random(1)
    p1 = [1, 0, 1, 0, 1]
    p2 = [0, 1, 0, 1, 0]
    c1, c2 = uniform_crossover(p1, p2, rate=1.0, rng=rng)
    assert len(c1) == len(p1)
    assert len(c2) == len(p2)


def test_mutate_rate_zero_unchanged():
    rng = random.Random(2)
    chromo = [1, 0, 1, 0, 1]
    assert bit_flip_mutate(chromo, rate=0.0, rng=rng) == chromo


def test_mutate_rate_one_flips_all():
    rng = random.Random(3)
    chromo = [1, 0, 1, 0, 1]
    flipped = bit_flip_mutate(chromo, rate=1.0, rng=rng)
    assert flipped == [0, 1, 0, 1, 0]


def test_budget_repair_feasible(small_pool, small_budget):
    costs = [l["enrichment_cost"] for l in small_pool]
    values = [l["estimated_value"] for l in small_pool]
    chromo = [1] * len(small_pool)
    repaired = budget_repair(chromo, costs, values, small_budget)
    total_cost = sum(c for c, g in zip(costs, repaired) if g == 1)
    assert total_cost <= small_budget + 1e-9


def test_run_ga_feasible_and_monotone(small_pool, small_budget):
    res = run_ga(
        small_pool, small_budget, GAConfig(generations=30, population_size=30), seed=42
    )
    assert res.best_cost <= small_budget + 1e-9
    # Elitism guarantees monotone non-decreasing best-fitness history.
    for a, b in zip(res.convergence_history, res.convergence_history[1:]):
        assert b >= a - 1e-9


def test_run_ga_deterministic(small_pool, small_budget):
    cfg = GAConfig(generations=20, population_size=30)
    r1 = run_ga(small_pool, small_budget, cfg, seed=42)
    r2 = run_ga(small_pool, small_budget, cfg, seed=42)
    assert r1.best_chromosome == r2.best_chromosome
    assert r1.best_fitness == r2.best_fitness
