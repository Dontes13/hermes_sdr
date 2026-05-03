"""End-to-end pipeline smoke test."""

from __future__ import annotations

from pathlib import Path

from enrichment_optimizer import generate as gen_mod
from enrichment_optimizer import optimize as optimize_mod


def test_full_pipeline():
    gen_mod.main()
    data = Path(gen_mod.__file__).parent / "data"
    assert (data / "leads_pool.csv").exists()
    assert (data / "leads_pool_50.csv").exists()
    assert (data / "budget.json").exists()

    summary = optimize_mod.main(seed=42)
    assert (data / "convergence.csv").exists()
    assert (data / "results_summary.json").exists()

    ga_value = summary["ga"]["total_value"]
    greedy_value = summary["greedy"]["total_value"]
    assert ga_value >= greedy_value * 0.95
    assert summary["ga"]["total_cost"] <= summary["budget"] + 1e-9
