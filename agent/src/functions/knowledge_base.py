from functools import lru_cache
from pathlib import Path

_KB_PATH = Path(__file__).parent.parent / "prompts" / "helios_kb.md"


@lru_cache(maxsize=1)
def load_knowledge_base() -> str:
    """Load the Helios knowledge base. Cached after first read."""
    return _KB_PATH.read_text()
