"""Stage 5b: has this failure been seen and resolved before?

TWO BACKENDS, ONE CONTRACT
==========================
``_similarity()`` is the swap point and both backends now exist behind it.
config/topology.json chooses:

    "precedent": { "backend": "lexical" }      <- default: offline, deterministic
    "precedent": { "backend": "embeddings" }   <- semantic, needs a key

Nothing downstream changes either way. ``find_precedents`` keeps the same
signature, the same threshold semantics and the same PrecedentMatch output, so
scorer.py and writer.py are untouched. If embeddings are selected but the key or
the network is missing, it falls back to lexical rather than failing.

DO NOT EMBED RAW STACK TRACES. GUIDs, timestamps, thread ids and file paths
dominate the vector and produce confident matches on boilerplate that every
.NET exception shares. Embed the output of ``_signature_key()`` instead: the
exception chain plus the distinguishing inner symptom, with the layer, host and
size/timing buckets carried as separate weighted components rather than folded
into the text.

The four weighted components are the same for both backends:

    0.45  signature   exception chain + inner symptom, Dice coefficient
    0.35  layer       exact match on the layer the rules engine chose
    0.10  host        exact match on the endpoint host
    0.10  facts       batch-size bucket and timing bucket agreement

The weighting is deliberately top-heavy on signature and layer so an unrelated
incident cannot drift into range on host alone. ``MIN_SIMILARITY`` is a floor,
not a ranking cutoff: below it, the honest answer is that there is no
precedent, not that the closest row is the precedent.
"""

from __future__ import annotations

import re
from typing import Any

from . import embeddings
from .models import PrecedentMatch

MIN_SIMILARITY = 0.35
MAX_RESULTS = 3

WEIGHTS = {"signature": 0.45, "layer": 0.35, "host": 0.10, "facts": 0.10}

_STOPWORDS = {"the", "a", "an", "of", "was", "is", "for", "to", "in", "on", "at", "and"}


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------

def _signature_key(facts: dict[str, Any]) -> str:
    """The normalised failure shape. This is what an embedding would encode."""
    chain = ">".join(facts.get("exception_types") or [])
    symptom = _inner_symptom(facts)

    if not chain and not symptom:
        if facts.get("has_error"):
            return "unclassified error"
        if facts.get("record_count") == 0:
            return "no error|zero records fetched"
        return "no error|clean run"

    return f"{chain}|{symptom}" if symptom else chain


def _inner_symptom(facts: dict[str, Any]) -> str:
    text = (facts.get("error_text") or "").lower()
    for phrase in (
        "the response ended prematurely",
        "connection refused",
        "no such host is known",
        "actively refused",
        "login failed for user",
        "pool size was reached",
        "timeout expired",
        "unhandled exception",
    ):
        if phrase in text:
            return phrase.replace("the response", "response")
    status = facts.get("http_status")
    if status:
        return f"{status} {_status_word(status)}"
    return ""


def _status_word(status: int) -> str:
    return {
        401: "unauthorized", 403: "forbidden", 404: "not found",
        500: "internal server error", 502: "bad gateway",
        503: "service unavailable", 504: "gateway timeout",
    }.get(status, "")


def batch_bucket(record_count: int | None) -> str:
    if record_count is None:
        return "any"
    if record_count == 0:
        return "empty"
    if record_count < 10:
        return "tiny"
    if record_count < 100:
        return "small"
    if record_count < 300:
        return "medium"
    return "large"


def timing_bucket(elapsed: float | None) -> str:
    if elapsed is None:
        return "any"
    if elapsed < 2:
        return "instant"
    if elapsed < 15:
        return "fast"
    if 55 <= elapsed <= 66:
        return "ceiling-60"
    if elapsed < 45:
        return "slow"
    return "long"


def _tokens(sig: str) -> set[str]:
    parts = re.split(r"[^A-Za-z0-9]+", sig.lower())
    return {p for p in parts if p and p not in _STOPWORDS}


# --------------------------------------------------------------------------
# Similarity
# --------------------------------------------------------------------------

def _lexical_similarity(a: str, b: str) -> float:
    """Dice coefficient over signature tokens. Deterministic and offline."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb)
    return (2.0 * overlap) / (len(ta) + len(tb))


def _similarity(a: str, b: str, topology: dict[str, Any] | None = None) -> float:
    """Similarity between two normalised signatures.

    THE SWAP POINT. When config selects the embedding backend this is cosine
    similarity over embedded signatures; otherwise it is the lexical Dice score.
    Either way the contract is identical - two signature strings in, 0..1 out -
    so nothing downstream in this module, in scorer.py or in writer.py changes.

    Embeddings are only ever computed over ``_signature_key()`` output. Never a
    raw stack trace. See engine/embeddings.py for why.
    """
    if embeddings.backend_name(topology) == "embeddings":
        semantic = embeddings.similarity(a, b)
        if semantic is not None:
            return semantic
        # No key, no network, or the call failed: fall back rather than fail.
    return _lexical_similarity(a, b)


def _facts_similarity(facts: dict[str, Any], incident: dict[str, Any]) -> float:
    scores: list[float] = []

    want_batch = batch_bucket(facts.get("record_count"))
    have_batch = incident.get("batch_bucket", "any")
    if "any" in (want_batch, have_batch):
        scores.append(0.5)
    else:
        scores.append(1.0 if want_batch == have_batch else 0.0)

    want_timing = timing_bucket(facts.get("elapsed_seconds"))
    have_timing = incident.get("timing_bucket", "any")
    if "any" in (want_timing, have_timing):
        scores.append(0.5)
    else:
        scores.append(1.0 if want_timing == have_timing else 0.0)

    return sum(scores) / len(scores)


def find_precedents(
    facts: dict[str, Any],
    layer: str,
    incidents_cfg: dict[str, Any],
    topology: dict[str, Any] | None = None,
) -> list[PrecedentMatch]:
    # When the rules engine declined to name a layer, offer no precedent at all.
    #
    # Layer agreement carries 0.35 of the score. With layer at 0.0 the remaining
    # signal is host (0.10) and size/timing buckets (0.10), and nearly every
    # incident in the file shares the same host - so a "match" here is carried
    # by noise. Observed: an unclassifiable TLS certificate failure scored 0.355
    # against an expired-client-secret incident and would have told an engineer
    # to rotate a credential.
    #
    # RB-UNKNOWN puts it plainly: "Do not act on the closest-looking runbook. A
    # near miss on a diagnosis is worse than no diagnosis." Saying nothing is
    # the correct output when the cause is unknown.
    if layer == "Unknown":
        return []

    signature = _signature_key(facts)
    host = facts.get("endpoint_host")
    results: list[PrecedentMatch] = []

    for inc in incidents_cfg.get("incidents", []):
        sig_score = _similarity(signature, inc.get("signature", ""), topology)
        layer_score = 1.0 if inc.get("layer") == layer else 0.0

        inc_host = inc.get("host")
        if not host or not inc_host:
            host_score = 0.5
        else:
            host_score = 1.0 if host == inc_host else 0.0

        facts_score = _facts_similarity(facts, inc)

        components = {
            "signature": sig_score,
            "layer": layer_score,
            "host": host_score,
            "facts": facts_score,
        }
        total = sum(WEIGHTS[k] * v for k, v in components.items())

        if total >= MIN_SIMILARITY:
            results.append(
                PrecedentMatch(
                    incident_id=inc["id"],
                    date=inc.get("date", ""),
                    title=inc.get("title", ""),
                    layer=inc.get("layer", ""),
                    similarity=round(total, 3),
                    fix_held=bool(inc.get("fix_held")),
                    resolution=inc.get("resolution", ""),
                    resolved_by=inc.get("resolved_by"),
                    time_to_resolve_hours=inc.get("time_to_resolve_hours"),
                    components={k: round(v, 3) for k, v in components.items()},
                )
            )

    # Identical failure shapes score identically, which happens often because a
    # recurring fault is the normal case. Break ties on recency so the ranking
    # is deterministic rather than dependent on order in incidents.json.
    results.sort(key=lambda r: (r.similarity, r.date), reverse=True)

    # Collapse identical shapes. Four copies of one fault crowd out the four
    # DIFFERENT faults an engineer actually wants to compare against, and
    # "seen 4 times, fix held every time" is better information than four
    # near-identical rows anyway. The representative is the most recent.
    grouped: dict[tuple[str, str], PrecedentMatch] = {}
    for r in results:
        key = (_incident_signature(incidents_cfg, r.incident_id), r.layer)
        if key in grouped:
            head = grouped[key]
            head.recurrence += 1
            head.also.append(r.incident_id)
        else:
            grouped[key] = r
    return list(grouped.values())[:MAX_RESULTS]


def _incident_signature(incidents_cfg: dict[str, Any], incident_id: str) -> str:
    for inc in incidents_cfg.get("incidents", []):
        if inc.get("id") == incident_id:
            return inc.get("signature", incident_id)
    return incident_id
