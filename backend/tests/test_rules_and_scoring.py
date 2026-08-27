"""Stages 4 and 6: the layer decision and the confidence band.

These are the tests that defend the design principle. If any of them can be
made to pass by a language model, the principle has been broken.
"""

from __future__ import annotations

import pytest

from engine import rules_engine
from engine.knowledge import candidate_layers, load_config, source_status
from engine.models import Dimension, PrecedentMatch, RuleMatch
from engine.scorer import score


@pytest.fixture
def cfg():
    return load_config()


# --------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cond,facts,expected", [
    ({"fact": "n", "op": "eq", "value": 5}, {"n": 5}, True),
    ({"fact": "n", "op": "eq", "value": 5}, {"n": 6}, False),
    ({"fact": "n", "op": "gte", "value": 100}, {"n": 539}, True),
    ({"fact": "n", "op": "gte", "value": 100}, {"n": 39}, False),
    ({"fact": "n", "op": "lt", "value": 10}, {"n": 5}, True),
    ({"fact": "n", "op": "near", "value": 60, "tolerance": 6}, {"n": 62}, True),
    ({"fact": "n", "op": "near", "value": 60, "tolerance": 6}, {"n": 70}, False),
    ({"fact": "s", "op": "in", "value": [401, 403]}, {"s": 401}, True),
    ({"fact": "s", "op": "in", "value": [401, 403]}, {"s": 503}, False),
    ({"fact": "l", "op": "contains", "value": "SocketException"}, {"l": ["HttpRequestException", "SocketException"]}, True),
    ({"fact": "l", "op": "contains", "value": "socketexception"}, {"l": ["SocketException"]}, True),
    ({"fact": "l", "op": "contains", "value": "SqlException"}, {"l": ["SocketException"]}, False),
    ({"fact": "t", "op": "matches", "value": "response ended prematurely"}, {"t": "The Response Ended Prematurely. (ResponseEnded)"}, True),
    ({"fact": "t", "op": "matches", "value": "connection refused"}, {"t": "no route to host"}, False),
    ({"fact": "x", "op": "exists"}, {"x": 1}, True),
    ({"fact": "x", "op": "exists"}, {"x": None}, False),
    ({"fact": "x", "op": "absent"}, {}, True),
])
def test_operators(cond, facts, expected):
    ok, _ = rules_engine._eval_condition(cond, facts)
    assert ok is expected


def test_missing_fact_never_crashes_a_rule():
    ok, _ = rules_engine._eval_condition({"fact": "nope", "op": "gte", "value": 1}, {})
    assert ok is False


def test_unknown_operator_is_a_loud_config_error():
    with pytest.raises(ValueError, match="Unknown operator"):
        rules_engine._eval_condition({"fact": "n", "op": "approximately", "value": 1}, {"n": 1})


# --------------------------------------------------------------------------
# Rule matching
# --------------------------------------------------------------------------

def test_all_of_requires_every_condition():
    rule = {
        "id": "R-T", "layer": "X",
        "all_of": [
            {"fact": "a", "op": "eq", "value": 1},
            {"fact": "b", "op": "eq", "value": 2},
        ],
    }
    assert rules_engine.evaluate_rule(rule, {"a": 1, "b": 2})[0] is True
    assert rules_engine.evaluate_rule(rule, {"a": 1, "b": 9})[0] is False


def test_any_of_requires_only_one():
    rule = {
        "id": "R-T", "layer": "X",
        "any_of": [
            {"fact": "a", "op": "eq", "value": 1},
            {"fact": "b", "op": "eq", "value": 2},
        ],
    }
    assert rules_engine.evaluate_rule(rule, {"a": 1, "b": 9})[0] is True
    assert rules_engine.evaluate_rule(rule, {"a": 9, "b": 9})[0] is False


def test_rule_with_no_conditions_is_rejected():
    with pytest.raises(ValueError, match="no conditions"):
        rules_engine.evaluate_rule({"id": "R-EMPTY", "layer": "X"}, {})


def test_highest_priority_rule_wins(cfg):
    """A 401 could look like several things. Priority decides, not the model."""
    facts = {
        "has_error": True, "http_status": 401,
        "exception_types": ["HttpRequestException"], "error_text": "unauthorized",
        "record_count": 128, "elapsed_seconds": 1.0,
        "small_batches_succeeded": False, "projection_exceeds_elapsed": True,
    }
    rule, hits = rules_engine.evaluate(facts, cfg["rules"])
    assert rule.layer == "Auth"
    assert rule.priority == max(h.priority for h in hits)


def test_no_matching_rule_returns_none_rather_than_a_guess(cfg):
    facts = {
        "has_error": True, "http_status": None,
        "exception_types": ["JsonException"],
        "error_text": "'<' is an invalid start of a value",
        "record_count": None, "elapsed_seconds": None,
        "small_batches_succeeded": False, "projection_exceeds_elapsed": False,
        "service_state": None,
    }
    rule, hits = rules_engine.evaluate(facts, cfg["rules"])
    assert rule is None
    assert hits == []


def test_every_configured_rule_names_a_real_layer(cfg):
    known = {l["id"] for l in cfg["topology"]["layers"]}
    for rule in cfg["rules"]["rules"]:
        assert rule["layer"] in known, f"{rule['id']} names unknown layer {rule['layer']}"
        for elim in rule.get("eliminates", []):
            assert elim in known, f"{rule['id']} eliminates unknown layer {elim}"


def test_every_layer_has_a_runbook_that_exists(cfg):
    for layer in cfg["topology"]["layers"]:
        rb = layer.get("runbook_id")
        assert rb in cfg["runbooks"], f"{layer['id']} points at missing runbook {rb}"


def test_rule_priorities_are_unique(cfg):
    priorities = [r["priority"] for r in cfg["rules"]["rules"]]
    assert len(priorities) == len(set(priorities)), "ambiguous rule ordering"


# --------------------------------------------------------------------------
# Confidence and the coverage cap
# --------------------------------------------------------------------------

def _rule(eliminates=(), specificity="pinpoint"):
    return RuleMatch(
        rule_id="R-T", layer="GatewayTimeout", title="t", rationale="r",
        specificity=specificity, priority=100, matched_conditions=[],
        eliminates=list(eliminates), elimination_reasons={},
    )


def _sources(connected: int, total: int = 7):
    return [
        {"id": f"s{i}", "name": f"s{i}", "checks": "",
         "connected": i < connected, "configured_connected": i < connected}
        for i in range(total)
    ]


def _strong_inputs(sources):
    from engine.models import Evidence
    cands = ["GatewayTimeout", "GalileoDown", "Network", "AldavarDB",
             "DatabaseViews", "WindowsService", "Auth"]
    return dict(
        evidence=[
            Evidence("a", "a", "app_logs", time="11:21:07"),
            Evidence("b", "b", "ald_sat", time="11:21:07"),
            Evidence("c", "c", "database_views", time="11:20:07"),
            Evidence("d", "d", "windows_service", time="11:21:07"),
        ],
        facts={"has_error": True, "error_time": "11:21:07", "elapsed_seconds": 60.0},
        rule=_rule(eliminates=[c for c in cands if c != "GatewayTimeout"]),
        all_hits=[_rule()],
        precedents=[PrecedentMatch("INC-1", "2026-07-31", "t", "GatewayTimeout",
                                   1.0, True, "res", "team", 26.0)],
        candidates=cands,
        layer="GatewayTimeout",
        sources=sources,
    )


def test_perfect_evidence_reaches_high_when_coverage_is_full():
    c = score(**_strong_inputs(_sources(7)))
    assert c.raw_band == "High"
    assert c.band == "High"
    assert c.capped is False


def test_the_coverage_cap_holds_perfect_evidence_at_medium():
    """The whole point: 3 of 7 sources cannot produce a High band."""
    c = score(**_strong_inputs(_sources(3)))
    assert c.raw_band == "High"
    assert c.band == "Medium"
    assert c.capped is True
    assert "3 of 7" in c.cap_reason


def test_very_low_coverage_caps_at_inconclusive():
    c = score(**_strong_inputs(_sources(1)))
    assert c.raw_band == "High"
    assert c.band == "Inconclusive"


def test_the_cap_never_raises_a_weak_band():
    """Full coverage must not promote thin evidence."""
    args = _strong_inputs(_sources(7))
    args["rule"] = None
    args["all_hits"] = []
    args["precedents"] = []
    args["evidence"] = args["evidence"][:1]
    c = score(**args)
    assert c.band in ("Inconclusive", "Medium")
    assert c.band == c.raw_band


def test_unknown_layer_is_always_inconclusive_however_it_scored():
    args = _strong_inputs(_sources(7))
    args["layer"] = "Unknown"
    c = score(**args)
    assert c.band == "Inconclusive"


def test_corroboration_counts_sources_not_lines():
    from engine.models import Evidence
    args = _strong_inputs(_sources(7))
    many_lines_one_source = [Evidence(f"k{i}", f"s{i}", "app_logs", time="11:21:07")
                             for i in range(20)]
    args["evidence"] = many_lines_one_source
    c = score(**args)
    corroboration = next(d for d in c.dimensions if d.name == "corroboration")
    assert corroboration.score == 0.35, "20 lines from one file is still one witness"


def test_precedent_whose_fix_did_not_hold_scores_lower():
    held = _strong_inputs(_sources(7))
    not_held = _strong_inputs(_sources(7))
    not_held["precedents"] = [PrecedentMatch("INC-2", "2026-05-18", "t", "GatewayTimeout",
                                             1.0, False, "res", "team", 48.0)]
    a = next(d for d in score(**held).dimensions if d.name == "precedent")
    b = next(d for d in score(**not_held).dimensions if d.name == "precedent")
    assert b.score < a.score


def test_dimension_weights_sum_to_one():
    c = score(**_strong_inputs(_sources(7)))
    assert sum(d.weight for d in c.dimensions) == pytest.approx(1.0)


def test_source_toggle_changes_coverage_only(cfg):
    normal = source_status(cfg["topology"])
    forced = source_status(cfg["topology"], force_all_connected=True)
    assert sum(s["connected"] for s in normal) == 3
    assert sum(s["connected"] for s in forced) == 7
    assert [s["id"] for s in normal] == [s["id"] for s in forced]
