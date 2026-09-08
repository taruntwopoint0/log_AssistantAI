"""Log-quality assessment and prevention advice.

Both are developer-facing and both are fully deterministic. The tests that
matter are the ones proving no model is involved and that a finding never
appears without the three things that make it actionable: what was observed,
what it cost, and what to change.
"""

from __future__ import annotations

import pytest

from engine import log_quality, prevention
from engine.knowledge import load_config
from engine.parser import parse
from engine.pipeline import investigate
from gen_mock_logs import SCENARIOS


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _assess(sample: str, cfg):
    parsed = parse(SCENARIOS[sample], cfg["topology"])
    return log_quality.assess(parsed, parsed.facts)


# --------------------------------------------------------------------------
# Log quality
# --------------------------------------------------------------------------

def test_every_check_reports_a_verdict(cfg):
    q = _assess("gateway_timeout", cfg)
    assert q.total == 10
    assert q.passed + len(q.gaps) == q.total


def test_a_gap_always_carries_observed_impact_and_fix(cfg):
    """A finding without these three is criticism, not feedback."""
    for name in SCENARIOS:
        for f in _assess(name, cfg).gaps:
            assert f.observed.strip(), f"{name}/{f.id} has no observation"
            assert f.impact.strip(), f"{name}/{f.id} has no impact"
            assert f.fix.strip(), f"{name}/{f.id} has no fix"
            assert f.severity in ("high", "medium", "low")


def test_strengths_are_reported_too(cfg):
    """A report listing only faults reads as nagging and gets ignored."""
    q = _assess("gateway_timeout", cfg)
    assert q.strengths
    names = {f.name for f in q.strengths}
    assert "Inner exceptions preserved" in names


def test_the_production_case_findings_are_correct(cfg):
    q = _assess("gateway_timeout", cfg)
    by_id = {f.id: f for f in q.findings}

    # These logs genuinely do not carry a correlation id or an explicit duration.
    assert by_id["correlation_id"].passed is False
    assert by_id["explicit_duration"].passed is False
    assert by_id["size_at_failure"].passed is False
    assert by_id["structured_logging"].passed is False

    # ...and they genuinely do these well.
    assert by_id["exception_chain"].passed is True
    assert by_id["timestamp_timezone"].passed is True
    assert by_id["endpoint_on_error"].passed is True
    assert by_id["success_outcome"].passed is True


def test_a_log_with_a_correlation_id_is_credited(cfg):
    text = (
        '11:20:07 INF CorrelationId=4f2c9a11-8bd3-4e7a-9c11-2f0a7e5d1b88 batch started\n'
        '11:21:07 ERR CorrelationId=4f2c9a11-8bd3-4e7a-9c11-2f0a7e5d1b88 call failed\n'
        "System.Net.Http.HttpRequestException: boom"
    )
    parsed = parse(text, cfg["topology"])
    q = log_quality.assess(parsed, parsed.facts)
    assert {f.id: f for f in q.findings}["correlation_id"].passed is True


def test_a_log_that_records_its_own_duration_is_credited(cfg):
    text = (
        "11:20:07 INF Supplier Details synced started\n"
        "11:21:07 ERR Call failed after 60123 ms\n"
        "System.Net.Http.HttpRequestException: boom"
    )
    parsed = parse(text, cfg["topology"])
    q = log_quality.assess(parsed, parsed.facts)
    assert {f.id: f for f in q.findings}["explicit_duration"].passed is True


def test_the_healthy_run_is_still_assessed(cfg):
    """Logging quality is independent of whether anything broke."""
    q = _assess("healthy_run", cfg)
    assert q.total == 10
    assert q.findings


def test_assessment_never_crashes_on_junk(cfg):
    for text in ["", "not a log at all", "\n\n\n"]:
        parsed = parse(text, cfg["topology"])
        q = log_quality.assess(parsed, parsed.facts)
        assert q.total == 10


# --------------------------------------------------------------------------
# Prevention
# --------------------------------------------------------------------------

def test_every_runbook_carries_prevention_advice(cfg):
    for rb_id, rb in cfg["runbooks"].items():
        assert rb.get("prevention"), f"{rb_id} has no prevention block"
        for item in rb["prevention"]:
            assert item["area"] in ("code", "config", "monitoring", "process")
            assert item["action"].strip()


def test_advice_comes_from_config_not_code(cfg):
    """The engine may compute numbers; it may not author advice."""
    rb = cfg["runbooks"]["RB-GATEWAY-60S"]
    built = prevention.build(rb, {"ceiling_seconds": 60, "observed_seconds_per_record": 0.18})
    assert [i["action"] for i in built.items] == [
        i["action"] for i in sorted(
            rb["prevention"], key=lambda i: prevention.AREA_ORDER[i["area"]])
    ]


def test_batch_size_is_computed_from_the_measured_rate():
    built = prevention.build({}, {
        "ceiling_seconds": 60.0,
        "observed_seconds_per_record": 0.1795,
        "rate_source": "observed",
        "projected_seconds": 96.7,
    })
    assert built.sizing is not None
    # 60 * 0.6 / 0.1795 = 200.5 -> 200
    assert built.sizing.safe_batch_size == 200
    assert "measured in this log" in built.sizing.basis


def test_the_computed_size_finishes_inside_the_ceiling():
    for ceiling, rate in [(60.0, 0.1795), (30.0, 0.5), (120.0, 0.02)]:
        built = prevention.build({}, {
            "ceiling_seconds": ceiling, "observed_seconds_per_record": rate,
            "rate_source": "observed",
        })
        assert built.sizing.safe_batch_size * rate <= ceiling, "would still be cut"


def test_a_baseline_rate_is_labelled_as_such():
    built = prevention.build({}, {
        "ceiling_seconds": 60.0, "observed_seconds_per_record": 0.1795,
        "rate_source": "baseline",
    })
    assert "not measured here" in built.sizing.basis


def test_no_sizing_is_offered_without_a_ceiling_or_a_rate():
    assert prevention.build({}, {"observed_seconds_per_record": 0.18}).sizing is None
    assert prevention.build({}, {"ceiling_seconds": 60}).sizing is None
    assert prevention.build({}, {}).sizing is None


def test_the_fix_text_no_longer_hardcodes_a_batch_size(cfg):
    """A number baked into prose is correct at exactly one throughput."""
    fix = cfg["runbooks"]["RB-GATEWAY-60S"]["fix"]
    assert "200 records" not in fix
    assert "36 seconds" not in fix


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_every_investigation_carries_both(name):
    inv = investigate(SCENARIOS[name], use_ai=False)
    assert inv.log_quality["total"] == 10
    assert "items" in inv.prevention


def test_the_production_case_recommends_a_concrete_batch_size():
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    sizing = inv.prevention["sizing"]
    assert sizing["safe_batch_size"] == 200
    assert sizing["safe_batch_size"] * sizing["seconds_per_record"] < sizing["ceiling_seconds"]


def test_neither_feature_needs_a_model(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    assert inv.log_quality["gaps"]
    assert inv.prevention["items"]


def test_both_survive_an_unrecognised_log():
    """Unknown layer means no runbook advice, but logging is still assessable."""
    inv = investigate(SCENARIOS["unrecognised"], use_ai=False)
    assert inv.log_quality["total"] == 10
    # RB-UNKNOWN does carry prevention: add a rule so it is recognised next time.
    assert inv.prevention["items"]


def test_results_stay_json_serialisable():
    import json
    for name in SCENARIOS:
        json.dumps(investigate(SCENARIOS[name], use_ai=False).to_dict())
