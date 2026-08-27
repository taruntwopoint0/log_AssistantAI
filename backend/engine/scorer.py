"""Stage 6: how much should anyone trust this conclusion?

Confidence is computed from properties of the evidence. The model is never
asked how confident it is, because a model rating its own output answers "90%"
every time regardless of what it was given.

Bands are words, not percentages. High / Medium / Inconclusive survive being
wrong; "87% confident" invites an argument about the 87.

THE COVERAGE CAP
================
Silence from a source that was never connected is not evidence of health. With
3 of 7 sources connected, the band is ceilinged at Medium however clean the
evidence looks. This blocks the worst failure mode a tool like this has: a
partially deployed system producing high-confidence wrong answers because the
sources that would have contradicted it were never wired up.
"""

from __future__ import annotations

from typing import Any

from .models import Confidence, Dimension, Evidence, PrecedentMatch, RuleMatch

WEIGHTS = {
    "corroboration": 0.30,
    "elimination": 0.25,
    "specificity": 0.20,
    "precedent": 0.15,
    "temporal": 0.10,
}

HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40

_BAND_RANK = {"Inconclusive": 1, "Medium": 2, "High": 3}
_RANK_BAND = {v: k for k, v in _BAND_RANK.items()}

NO_CAP_COVERAGE = 0.85
MEDIUM_CAP_COVERAGE = 0.40

_SPECIFICITY_BASE = {"pinpoint": 1.0, "strong": 0.7, "broad": 0.4}

TEMPORAL_WINDOW_SECONDS = 300


def _to_seconds(hhmmss: str | None) -> int | None:
    if not hhmmss:
        return None
    try:
        h, m, s = (int(p) for p in hhmmss.split(":"))
    except ValueError:
        return None
    return h * 3600 + m * 60 + s


# --------------------------------------------------------------------------
# Dimensions
# --------------------------------------------------------------------------

def _corroboration(evidence: list[Evidence]) -> Dimension:
    """Independent sources that agree, not how many lines matched.

    Ten lines from one log file is one source, not ten witnesses.
    """
    sources = sorted({e.source for e in evidence if e.source})
    n = len(sources)
    score = {0: 0.0, 1: 0.35, 2: 0.65, 3: 0.85}.get(n, 1.0)
    if n == 0:
        detail = "No evidence was extracted."
    else:
        detail = f"{n} independent source(s) contributed evidence: {', '.join(sources)}."
    return Dimension("corroboration", WEIGHTS["corroboration"], score, detail)


def _elimination(rule: RuleMatch | None, candidates: list[str], layer: str) -> Dimension:
    if rule is None:
        return Dimension(
            "elimination", WEIGHTS["elimination"], 0.0,
            "No rule matched, so no candidate layer could be ruled out.",
        )
    ruled_out = [l for l in rule.eliminates if l in candidates and l != layer]
    denominator = len(candidates) - (1 if layer in candidates else 0)
    score = (len(ruled_out) / denominator) if denominator else 0.0
    detail = (
        f"{len(ruled_out)} of {denominator} competing layer(s) ruled out by "
        f"{rule.rule_id}."
    )
    return Dimension("elimination", WEIGHTS["elimination"], min(1.0, score), detail)


def _specificity(rule: RuleMatch | None, all_hits: list[RuleMatch]) -> Dimension:
    if rule is None:
        return Dimension(
            "specificity", WEIGHTS["specificity"], 0.0,
            "Evidence fell through every rule without pinning a layer.",
        )
    base = _SPECIFICITY_BASE.get(rule.specificity, 0.4)
    distinct_layers = {h.layer for h in all_hits}
    if len(distinct_layers) > 1:
        score = base * 0.75
        detail = (
            f"Rule {rule.rule_id} is {rule.specificity}, but "
            f"{len(distinct_layers)} layers matched; the highest priority won."
        )
    else:
        score = base
        detail = f"Rule {rule.rule_id} is {rule.specificity} and was the only layer matched."
    return Dimension("specificity", WEIGHTS["specificity"], min(1.0, score), detail)


def _precedent(precedents: list[PrecedentMatch]) -> Dimension:
    if not precedents:
        return Dimension(
            "precedent", WEIGHTS["precedent"], 0.0,
            "No resolved incident in config/incidents.json resembles this failure.",
        )
    best = precedents[0]
    score = best.similarity * (1.0 if best.fix_held else 0.6)
    held = "the fix held" if best.fix_held else "the attempted fix did NOT hold"
    detail = (
        f"Closest match {best.incident_id} ({best.date}) at "
        f"{best.similarity:.0%} similarity, and {held}."
    )
    return Dimension("precedent", WEIGHTS["precedent"], min(1.0, score), detail)


def _temporal(evidence: list[Evidence], facts: dict[str, Any]) -> Dimension:
    if not facts.get("has_error"):
        return Dimension(
            "temporal", WEIGHTS["temporal"], 0.6,
            "No failure in this log, so there is no failure moment to be tight to.",
        )

    error_at = _to_seconds(facts.get("error_time"))
    timed = [e for e in evidence if e.time and _to_seconds(e.time) is not None]

    if error_at is None or not timed:
        return Dimension(
            "temporal", WEIGHTS["temporal"], 0.4,
            "Evidence could not be placed on a timeline relative to the failure.",
        )

    near = [
        e for e in timed
        if abs((_to_seconds(e.time) or 0) - error_at) <= TEMPORAL_WINDOW_SECONDS
    ]
    score = len(near) / len(timed)
    detail = (
        f"{len(near)} of {len(timed)} timestamped observations fall within "
        f"{TEMPORAL_WINDOW_SECONDS // 60} minutes of the failure."
    )
    if facts.get("elapsed_seconds") is None:
        score *= 0.7
        detail += " Elapsed time could not be derived, which weakens the timeline."
    return Dimension("temporal", WEIGHTS["temporal"], min(1.0, score), detail)


# --------------------------------------------------------------------------
# Band assembly
# --------------------------------------------------------------------------

def _band_for(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "High"
    if score >= MEDIUM_THRESHOLD:
        return "Medium"
    return "Inconclusive"


def score(
    *,
    evidence: list[Evidence],
    facts: dict[str, Any],
    rule: RuleMatch | None,
    all_hits: list[RuleMatch],
    precedents: list[PrecedentMatch],
    candidates: list[str],
    layer: str,
    sources: list[dict[str, Any]],
) -> Confidence:
    dimensions = [
        _corroboration(evidence),
        _elimination(rule, candidates, layer),
        _specificity(rule, all_hits),
        _precedent(precedents),
        _temporal(evidence, facts),
    ]

    raw_score = sum(d.contribution for d in dimensions)
    raw_band = _band_for(raw_score)

    connected = sum(1 for s in sources if s["connected"])
    total = len(sources) or 1
    coverage = connected / total

    if coverage >= NO_CAP_COVERAGE:
        cap_band = "High"
        cap_reason = None
    elif coverage >= MEDIUM_CAP_COVERAGE:
        cap_band = "Medium"
        cap_reason = (
            f"Only {connected} of {total} diagnostic sources are connected. "
            f"Silence from the {total - connected} disconnected source(s) is not "
            f"evidence of their health, so the band is ceilinged at Medium."
        )
    else:
        cap_band = "Inconclusive"
        cap_reason = (
            f"Only {connected} of {total} diagnostic sources are connected. That is "
            f"too little coverage to support any conclusion above Inconclusive."
        )

    final_rank = min(_BAND_RANK[raw_band], _BAND_RANK[cap_band])
    band = _RANK_BAND[final_rank]

    # A layer the rules could not identify is never presented with confidence,
    # whatever the surrounding evidence scored.
    if layer == "Unknown":
        band = "Inconclusive"
        if cap_reason is None:
            cap_reason = "No rule matched the evidence, so no cause is being claimed."

    capped = band != raw_band

    return Confidence(
        band=band,
        raw_band=raw_band,
        raw_score=round(raw_score, 4),
        dimensions=dimensions,
        capped=capped,
        cap_reason=cap_reason if capped else None,
        coverage=round(coverage, 4),
        connected_sources=connected,
        total_sources=total,
    )
