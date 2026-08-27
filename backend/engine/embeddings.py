"""Optional embedding backend for precedent matching.

OFF BY DEFAULT. config/topology.json decides:

    "precedent": { "backend": "lexical" }        <- default, offline, deterministic
    "precedent": { "backend": "embeddings" }     <- semantic, needs a key

The lexical backend stays the default because it is deterministic, needs no
network and no key, and keeps the whole test suite offline. Embeddings buy
semantic reach - "connection terminated" matching "response ended prematurely" -
at the cost of a network call and a non-reproducible score.

WHAT GETS EMBEDDED
==================
Only the normalised signature from precedent._signature_key(): the exception
chain plus the distinguishing inner symptom. Never a raw stack trace. GUIDs,
timestamps, thread ids and file paths dominate a vector and produce confident
matches on boilerplate that every .NET exception shares.

Layer, host and the size/timing buckets stay OUTSIDE the vector, as separately
weighted components in precedent.py. Folding them into the text would let a
strong textual match drag in an incident from the wrong layer, which is the
exact failure the weighting was built to prevent.

CACHING
=======
A recurring fault produces the same signature every time, so embeddings are
cached in-process by that string and optionally persisted. Re-embedding a
signature you have already seen is pure waste.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

DEFAULT_EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768                       # 3072 default is overkill for short signatures
TASK_TYPE = "SEMANTIC_SIMILARITY"

CACHE_PATH = Path(
    os.environ.get("INVESTIGATOR_EMBED_CACHE")
    or Path(__file__).resolve().parents[1] / "embedding_cache.json"
)

_MEMORY: dict[str, list[float]] = {}
_disk_loaded = False


def _load_disk_cache() -> None:
    global _disk_loaded
    if _disk_loaded:
        return
    _disk_loaded = True
    if CACHE_PATH.exists():
        try:
            _MEMORY.update(json.loads(CACHE_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass


def _save_disk_cache() -> None:
    try:
        CACHE_PATH.write_text(json.dumps(_MEMORY), encoding="utf-8")
    except OSError:
        pass                          # a cache miss is never worth an error


def backend_name(topology: dict[str, Any] | None = None) -> str:
    """Which backend is configured. Env var overrides config, config overrides default."""
    env = os.environ.get("INVESTIGATOR_PRECEDENT_BACKEND", "").strip().lower()
    if env in ("lexical", "embeddings"):
        return env
    cfg = (topology or {}).get("precedent") or {}
    backend = str(cfg.get("backend", "lexical")).lower()
    return backend if backend in ("lexical", "embeddings") else "lexical"


def available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def embed(text: str) -> list[float] | None:
    """Embed one normalised signature. None on any failure, so callers fall back."""
    if not text:
        return None
    _load_disk_cache()
    if text in _MEMORY:
        return _MEMORY[text]

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model=os.environ.get("INVESTIGATOR_EMBED_MODEL", DEFAULT_EMBED_MODEL),
            contents=text,
            config=types.EmbedContentConfig(
                task_type=TASK_TYPE, output_dimensionality=EMBED_DIM
            ),
        )
        vector = list(result.embeddings[0].values)
    except Exception:
        return None                   # never let precedent matching hard-fail

    if not vector:
        return None
    _MEMORY[text] = vector
    _save_disk_cache()
    return vector


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    # Cosine runs -1..1; signatures are never opposed, so clamp to 0..1.
    return max(0.0, min(1.0, dot / (na * nb)))


# Raw cosine over short technical strings is badly compressed: everything shares
# the same vocabulary ("Exception", "timeout", "connection"), so even unrelated
# failures land high. Measured on real signatures:
#
#   response ended prematurely  vs  connection terminated early   0.965  (related)
#   response ended prematurely  vs  SQL pool size was reached     0.827  (unrelated)
#
# 0.827 for two unrelated layers would clear MIN_SIMILARITY on the signature
# component alone, which is precisely what the weighting exists to stop. So the
# raw cosine is rescaled: everything at or below the floor becomes 0, and the
# band above it is stretched back over 0..1. Tune SIMILARITY_FLOOR against your
# own incidents - it is the one number that decides whether this backend is
# safer or more dangerous than the lexical one.
SIMILARITY_FLOOR = 0.80


def calibrate(raw: float) -> float:
    if raw <= SIMILARITY_FLOOR:
        return 0.0
    return (raw - SIMILARITY_FLOOR) / (1.0 - SIMILARITY_FLOOR)


def similarity(a: str, b: str, raw: bool = False) -> float | None:
    """Calibrated semantic similarity, or None if embeddings are unavailable."""
    va, vb = embed(a), embed(b)
    if va is None or vb is None:
        return None
    score = cosine(va, vb)
    return score if raw else calibrate(score)


def clear_cache() -> None:
    _MEMORY.clear()
