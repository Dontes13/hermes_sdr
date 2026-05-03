"""Genetic algorithm for the enrichment budget knapsack.

Representation: binary chromosome of length N. chromosome[i] = 1 means "enrich lead i".
Fitness: sum of estimated_value for selected leads; heavy penalty (× 0.01) if over budget.
Operators: tournament selection, uniform crossover, bit-flip mutation, elitism.

Deterministic when a seed is provided — uses local random.Random / np.random.Generator
instances so parallel experiments do not interfere via global RNG state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Sequence

Chromosome = list[int]
Lead = dict  # keys of interest: enrichment_cost, estimated_value


@dataclass
class GAConfig:
    population_size: int = 50
    generations: int = 100
    crossover_rate: float = 0.8
    mutation_rate: float = 0.02
    tournament_size: int = 3
    elitism_count: int = 2
    repair: bool = True
    greedy_seed_fraction: float = 0.20  # fraction of initial pop seeded from greedy perturbations


@dataclass
class GAResult:
    best_chromosome: Chromosome
    best_fitness: float
    best_cost: float
    convergence_history: list[float]
    avg_fitness_history: list[float]
    generations_run: int
    population_size: int
    leads_selected: int
    budget_used: float
    budget_total: float
    config: GAConfig = field(default_factory=GAConfig)


def _leads_as_arrays(leads: Sequence[Lead]) -> tuple[list[float], list[float]]:
    costs = [float(lead["enrichment_cost"]) for lead in leads]
    values = [float(lead["estimated_value"]) for lead in leads]
    return costs, values


def _total(chromosome: Chromosome, vec: list[float]) -> float:
    return sum(v for g, v in zip(chromosome, vec) if g == 1)


def fitness(
    chromosome: Chromosome,
    costs: list[float],
    values: list[float],
    budget: float,
    penalty_factor: float = 0.01,
) -> float:
    total_cost = _total(chromosome, costs)
    total_value = _total(chromosome, values)
    if total_cost > budget:
        return total_value * penalty_factor
    return total_value


def tournament_select(
    population: list[Chromosome],
    fitnesses: list[float],
    k: int,
    rng: random.Random,
) -> Chromosome:
    candidates = rng.sample(range(len(population)), k)
    best = max(candidates, key=lambda i: fitnesses[i])
    return population[best][:]


def uniform_crossover(
    parent1: Chromosome,
    parent2: Chromosome,
    rate: float,
    rng: random.Random,
) -> tuple[Chromosome, Chromosome]:
    if rng.random() > rate:
        return parent1[:], parent2[:]
    child1, child2 = [], []
    for g1, g2 in zip(parent1, parent2):
        if rng.random() < 0.5:
            child1.append(g1)
            child2.append(g2)
        else:
            child1.append(g2)
            child2.append(g1)
    return child1, child2


def bit_flip_mutate(
    chromosome: Chromosome,
    rate: float,
    rng: random.Random,
) -> Chromosome:
    return [g if rng.random() > rate else 1 - g for g in chromosome]


def budget_repair(
    chromosome: Chromosome,
    costs: list[float],
    values: list[float],
    budget: float,
) -> Chromosome:
    """Drop selected leads with worst value/cost ratio until within budget."""
    chromosome = chromosome[:]
    total_cost = _total(chromosome, costs)
    if total_cost <= budget:
        return chromosome

    selected = [i for i, g in enumerate(chromosome) if g == 1]
    # Sort ascending by value/cost: drop worst first.
    selected.sort(key=lambda i: values[i] / costs[i] if costs[i] > 0 else float("inf"))
    for i in selected:
        if total_cost <= budget:
            break
        chromosome[i] = 0
        total_cost -= costs[i]
    return chromosome


def _greedy_chromosome(
    costs: list[float], values: list[float], budget: float
) -> Chromosome:
    n = len(costs)
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


def _perturb(chromosome: Chromosome, flips: int, rng: random.Random) -> Chromosome:
    chromo = chromosome[:]
    idxs = rng.sample(range(len(chromo)), min(flips, len(chromo)))
    for i in idxs:
        chromo[i] = 1 - chromo[i]
    return chromo


def _initialize_population(
    n: int,
    costs: list[float],
    values: list[float],
    budget: float,
    config: GAConfig,
    rng: random.Random,
) -> list[Chromosome]:
    pop_size = config.population_size
    n_greedy = int(round(pop_size * config.greedy_seed_fraction))
    n_random = pop_size - n_greedy

    # Tune bernoulli p so expected cost ≈ budget (bounded to [0.1, 0.9]).
    total_cost = sum(costs) or 1.0
    p = max(0.1, min(0.9, budget / total_cost))

    pop: list[Chromosome] = []
    for _ in range(n_random):
        pop.append([1 if rng.random() < p else 0 for _ in range(n)])

    if n_greedy > 0:
        greedy = _greedy_chromosome(costs, values, budget)
        for _ in range(n_greedy):
            flips = rng.randint(5, 10)
            pop.append(_perturb(greedy, flips, rng))
    return pop


def run_ga(
    leads: Sequence[Lead],
    budget: float,
    config: GAConfig | None = None,
    seed: int = 42,
) -> GAResult:
    config = config or GAConfig()
    rng = random.Random(seed)
    n = len(leads)
    costs, values = _leads_as_arrays(leads)

    population = _initialize_population(n, costs, values, budget, config, rng)
    if config.repair:
        population = [budget_repair(c, costs, values, budget) for c in population]

    def fit(c: Chromosome) -> float:
        return fitness(c, costs, values, budget)

    fitnesses = [fit(c) for c in population]
    best_history: list[float] = []
    avg_history: list[float] = []

    best_overall_idx = max(range(len(population)), key=lambda i: fitnesses[i])
    best_overall = population[best_overall_idx][:]
    best_overall_fit = fitnesses[best_overall_idx]

    for _gen in range(config.generations):
        elite_idxs = sorted(
            range(len(population)), key=lambda i: fitnesses[i], reverse=True
        )[: config.elitism_count]
        elites = [population[i][:] for i in elite_idxs]

        new_pop: list[Chromosome] = list(elites)
        while len(new_pop) < config.population_size:
            p1 = tournament_select(population, fitnesses, config.tournament_size, rng)
            p2 = tournament_select(population, fitnesses, config.tournament_size, rng)
            c1, c2 = uniform_crossover(p1, p2, config.crossover_rate, rng)
            c1 = bit_flip_mutate(c1, config.mutation_rate, rng)
            c2 = bit_flip_mutate(c2, config.mutation_rate, rng)
            if config.repair:
                c1 = budget_repair(c1, costs, values, budget)
                c2 = budget_repair(c2, costs, values, budget)
            new_pop.append(c1)
            if len(new_pop) < config.population_size:
                new_pop.append(c2)

        population = new_pop[: config.population_size]
        fitnesses = [fit(c) for c in population]

        gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
        if fitnesses[gen_best_idx] > best_overall_fit:
            best_overall = population[gen_best_idx][:]
            best_overall_fit = fitnesses[gen_best_idx]

        best_history.append(best_overall_fit)
        avg_history.append(sum(fitnesses) / len(fitnesses))

    best_cost = _total(best_overall, costs)
    return GAResult(
        best_chromosome=best_overall,
        best_fitness=best_overall_fit,
        best_cost=best_cost,
        convergence_history=best_history,
        avg_fitness_history=avg_history,
        generations_run=config.generations,
        population_size=config.population_size,
        leads_selected=sum(best_overall),
        budget_used=best_cost,
        budget_total=budget,
        config=config,
    )
