"""Session-scoped fixture: ensure a trained model exists before score tests run."""

from pathlib import Path

import pytest

from lead_scorer import generate as gen_mod
from lead_scorer import train as train_mod

MODEL_PATH = Path(__file__).parent.parent / "models" / "lead_scorer.joblib"
CSV_PATH = Path(__file__).parent.parent / "data" / "leads_synthetic.csv"


@pytest.fixture(scope="session", autouse=True)
def ensure_trained_model():
    if not CSV_PATH.exists():
        gen_mod.main()
    if not MODEL_PATH.exists():
        train_mod.train()
    yield
