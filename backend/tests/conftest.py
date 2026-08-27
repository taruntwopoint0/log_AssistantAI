import sys
from pathlib import Path

# Tests import the engine as a package from the backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import os
import pytest


@pytest.fixture(autouse=True)
def _pin_lexical_backend(monkeypatch):
    """Keep the suite offline and reproducible.

    The shipped config enables the embedding backend, which is right for the
    running tool and wrong for tests: it would need a key, hit the network, and
    return scores that drift with the model. Tests that specifically exercise
    embeddings override this with their own monkeypatch.
    """
    monkeypatch.setenv("INVESTIGATOR_PRECEDENT_BACKEND", "lexical")
