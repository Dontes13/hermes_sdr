"""Fixtures for enrichment_optimizer tests."""

from __future__ import annotations

import pytest

from enrichment_optimizer import generate as gen_mod


@pytest.fixture(scope="session")
def small_pool():
    """50-lead pool at seed=42. Stable across runs."""
    df = gen_mod.generate(n=50, seed=42)
    return df.to_dict(orient="records")


@pytest.fixture(scope="session")
def small_budget(small_pool):
    return sum(l["enrichment_cost"] for l in small_pool) * 0.60


@pytest.fixture(scope="session")
def tiny_pool():
    """12-lead pool so brute-force over 2^12 subsets is cheap."""
    df = gen_mod.generate(n=12, seed=123)
    return df.to_dict(orient="records")


@pytest.fixture(scope="session")
def tiny_budget(tiny_pool):
    return sum(l["enrichment_cost"] for l in tiny_pool) * 0.60
