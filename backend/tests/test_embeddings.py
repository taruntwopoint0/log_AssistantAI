"""The optional embedding backend. Runs entirely offline: the network call is
stubbed, because a test that needs a key is a test that stops running.

The calibration tests are the important ones. Raw cosine over short technical
strings is compressed - unrelated failures measured 0.827 against each other on
the real model - and shipping that uncalibrated would let any incident match any
other on the signature component alone.
"""

from __future__ import annotations

import pytest

from engine import embeddings, precedent
from engine.knowledge import load_config


@pytest.fixture(autouse=True)
def clean_cache():
    embeddings.clear_cache()
    yield
    embeddings.clear_cache()


# --------------------------------------------------------------------------
# Backend selection
# --------------------------------------------------------------------------

def test_an_unconfigured_topology_falls_back_to_lexical(monkeypatch):
    monkeypatch.delenv("INVESTIGATOR_PRECEDENT_BACKEND", raising=False)
    assert embeddings.backend_name({}) == "lexical"


def test_the_shipped_config_enables_embeddings(monkeypatch):
    monkeypatch.delenv("INVESTIGATOR_PRECEDENT_BACKEND", raising=False)
    assert embeddings.backend_name(load_config()["topology"]) == "embeddings"


def test_config_selects_the_backend(monkeypatch):
    monkeypatch.delenv("INVESTIGATOR_PRECEDENT_BACKEND", raising=False)
    assert embeddings.backend_name({"precedent": {"backend": "embeddings"}}) == "embeddings"


def test_env_overrides_config(monkeypatch):
    monkeypatch.setenv("INVESTIGATOR_PRECEDENT_BACKEND", "lexical")
    assert embeddings.backend_name({"precedent": {"backend": "embeddings"}}) == "lexical"


def test_a_junk_backend_name_falls_back_to_lexical(monkeypatch):
    monkeypatch.delenv("INVESTIGATOR_PRECEDENT_BACKEND", raising=False)
    assert embeddings.backend_name({"precedent": {"backend": "pinecone"}}) == "lexical"


# --------------------------------------------------------------------------
# Calibration - the reason this backend is safe to enable
# --------------------------------------------------------------------------

def test_calibration_floors_the_compressed_range():
    """Measured on the real model: unrelated signatures scored 0.827 raw."""
    assert embeddings.calibrate(0.827) < 0.20, "unrelated pairs must not clear the floor"
    assert embeddings.calibrate(0.965) > 0.75, "genuinely similar pairs must survive"
    assert embeddings.calibrate(0.80) == 0.0
    assert embeddings.calibrate(0.50) == 0.0
    assert embeddings.calibrate(1.0) == pytest.approx(1.0)


def test_calibration_is_monotonic():
    xs = [0.5, 0.8, 0.85, 0.9, 0.95, 1.0]
    ys = [embeddings.calibrate(x) for x in xs]
    assert ys == sorted(ys)


def test_an_unrelated_pair_cannot_clear_the_precedent_floor():
    """0.133 * 0.45 signature weight is far below MIN_SIMILARITY."""
    contribution = embeddings.calibrate(0.827) * precedent.WEIGHTS["signature"]
    assert contribution < precedent.MIN_SIMILARITY


# --------------------------------------------------------------------------
# Cosine
# --------------------------------------------------------------------------

def test_cosine_basics():
    assert embeddings.cosine([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
    assert embeddings.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert embeddings.cosine([1, 0], [-1, 0]) == 0.0, "clamped, never negative"
    assert embeddings.cosine([], [1]) == 0.0
    assert embeddings.cosine([0, 0], [1, 1]) == 0.0


# --------------------------------------------------------------------------
# Failure and fallback
# --------------------------------------------------------------------------

def test_no_key_means_no_embedding(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(embeddings, "_load_disk_cache", lambda: None)
    assert embeddings.embed("anything") is None
    assert embeddings.similarity("a", "b") is None


def test_precedent_falls_back_to_lexical_when_embeddings_fail(monkeypatch):
    """Selecting embeddings must never break matching if the call fails."""
    monkeypatch.setenv("INVESTIGATOR_PRECEDENT_BACKEND", "embeddings")
    monkeypatch.setattr(embeddings, "similarity", lambda a, b: None)
    a = "HttpRequestException>HttpIOException|response ended prematurely"
    assert precedent._similarity(a, a) == precedent._lexical_similarity(a, a) == 1.0


def test_embedding_backend_is_used_when_selected(monkeypatch):
    monkeypatch.setenv("INVESTIGATOR_PRECEDENT_BACKEND", "embeddings")
    monkeypatch.setattr(embeddings, "similarity", lambda a, b: 0.42)
    assert precedent._similarity("x", "y") == 0.42


def test_signature_only_is_ever_embedded(monkeypatch):
    """The guard that matters: no stack trace may reach the embedding API."""
    monkeypatch.setenv("INVESTIGATOR_PRECEDENT_BACKEND", "embeddings")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    seen: list[str] = []

    def fake_embed(text):
        seen.append(text)
        return [1.0, 0.0]

    monkeypatch.setattr(embeddings, "embed", fake_embed)

    from engine.pipeline import investigate
    from gen_mock_logs import SCENARIOS
    investigate(SCENARIOS["gateway_timeout"], use_ai=False)

    assert seen, "the embedding backend was not exercised"
    for text in seen:
        assert "FetchGalileoApi.cs" not in text
        assert "   at " not in text
        assert len(text) < 200, f"a signature should be short, got {len(text)} chars"


def test_embeddings_are_cached_by_signature(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(embeddings, "_load_disk_cache", lambda: None)
    monkeypatch.setattr(embeddings, "_save_disk_cache", lambda: None)
    calls: list[str] = []

    class FakeEmb:
        values = [1.0, 2.0, 3.0]

    class FakeModels:
        def embed_content(self, **kw):
            calls.append(kw["contents"])
            return type("R", (), {"embeddings": [FakeEmb()]})()

    class FakeClient:
        def __init__(self, **kw):
            self.models = FakeModels()

    import sys, types as pytypes
    fake_genai = pytypes.ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_types = pytypes.ModuleType("google.genai.types")
    fake_types.EmbedContentConfig = lambda **kw: kw
    fake_google = pytypes.ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)

    embeddings.embed("SqlException|pool size was reached")
    embeddings.embed("SqlException|pool size was reached")
    assert len(calls) == 1, "a repeated signature must not be re-embedded"
