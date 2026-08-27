"""End-to-end: all eight scenarios, plus the guarantees the pitch rests on.

Everything here runs with use_ai=False. If a test in this file needs a model to
pass, the design principle has been broken.
"""

from __future__ import annotations

import pytest

from engine.pipeline import investigate
from gen_mock_logs import EXPECTED, SCENARIOS


@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_scenario_concludes_the_expected_layer_and_band(name):
    inv = investigate(SCENARIOS[name], use_ai=False)
    expected = EXPECTED[name]
    assert inv.layer == expected["layer"]
    assert inv.confidence.band == expected["band"]


@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_every_scenario_runs_without_a_model(name):
    inv = investigate(SCENARIOS[name], use_ai=False)
    assert inv.narrative_source == "template"
    assert inv.narrative.strip()


@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_result_is_json_serialisable(name):
    import json
    inv = investigate(SCENARIOS[name], use_ai=False)
    json.dumps(inv.to_dict())


# --------------------------------------------------------------------------
# The production case
# --------------------------------------------------------------------------

def test_production_case_finds_the_timing_contradiction():
    """The finding that makes the project worth building.

    539 records at the rate measured in this same log needs ~97s. The call died
    at 60s. That gap is the root cause, and it is arithmetic, not inference.
    """
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    t = inv.timing
    assert t["record_count"] == 539
    assert t["elapsed_seconds"] == 60.0
    assert t["ceiling_seconds"] == 60.0
    assert t["projected_seconds"] > 90
    assert t["rate_source"] == "observed", "the rate must come from the log, not a constant"
    assert t["projected_seconds"] > t["elapsed_seconds"] * 1.5


def test_production_case_does_not_blame_galileo():
    """The manual checklist's dead end. Galileo answers small batches all day."""
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    assert inv.layer != "GalileoDown"
    assert "GalileoDown" in inv.eliminated
    assert "small batches" in inv.eliminated["GalileoDown"].lower()


def test_production_case_rules_out_the_client_timeout():
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    assert any("client" in e.summary.lower() for e in inv.evidence)
    assert any("do not raise the httpclient timeout" in d.lower()
               for d in inv.runbook["do_not"])


def test_production_case_recommends_chunking():
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    assert "chunk" in inv.runbook["fix"].lower()


def test_production_case_matches_its_precedent():
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    assert inv.precedents
    assert inv.precedents[0].similarity >= 0.9


# --------------------------------------------------------------------------
# The demo moments
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_coverage_toggle_never_changes_the_root_cause(name):
    """Demo moment 2. The band moves; the diagnosis must not."""
    capped = investigate(SCENARIOS[name], use_ai=False)
    lifted = investigate(SCENARIOS[name], use_ai=False, force_all_connected=True)
    assert capped.layer == lifted.layer
    assert capped.rule == lifted.rule
    assert list(capped.eliminated) == list(lifted.eliminated)


def test_coverage_toggle_lifts_the_production_case_to_high():
    capped = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    lifted = investigate(SCENARIOS["gateway_timeout"], use_ai=False,
                         force_all_connected=True)
    assert capped.confidence.band == "Medium"
    assert capped.confidence.capped is True
    assert lifted.confidence.band == "High"
    assert lifted.confidence.capped is False


def test_unrecognised_declines_to_guess():
    """Demo moment 3, and the most important behaviour in the tool."""
    inv = investigate(SCENARIOS["unrecognised"], use_ai=False)
    assert inv.layer == "Unknown"
    assert inv.confidence.band == "Inconclusive"
    assert inv.rule is None
    assert inv.eliminated == {}
    assert inv.precedents == []
    assert inv.owner is None


def test_unrecognised_still_shows_its_working():
    """Declining to guess is not the same as saying nothing."""
    inv = investigate(SCENARIOS["unrecognised"], use_ai=False)
    assert inv.evidence, "the tool must still show what it looked at"
    assert inv.runbook is not None
    assert "rules.json" in " ".join(inv.runbook["checks"])


def test_healthy_run_is_not_forced_into_a_diagnosis():
    inv = investigate(SCENARIOS["healthy_run"], use_ai=False)
    assert inv.layer == "Healthy"
    assert inv.facts["has_error"] is False
    assert inv.facts["record_count"] > 0


# --------------------------------------------------------------------------
# Invariants
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_no_scenario_reaches_high_under_the_real_source_coverage(name):
    """With 3 of 7 sources wired up, nothing may claim High. Ever."""
    inv = investigate(SCENARIOS[name], use_ai=False)
    assert inv.confidence.band in ("Medium", "Inconclusive")


@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_a_layer_is_never_reported_without_its_owner_and_runbook(name):
    inv = investigate(SCENARIOS[name], use_ai=False)
    assert inv.runbook is not None
    if inv.layer not in ("Unknown", "Healthy"):
        assert inv.owner, f"{inv.layer} reported with no owning team"


@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_a_layer_never_eliminates_itself(name):
    inv = investigate(SCENARIOS[name], use_ai=False)
    assert inv.layer not in inv.eliminated


def test_results_are_deterministic():
    """Same input, same output, every time. No sampling anywhere in stages 1-6."""
    runs = [investigate(SCENARIOS["gateway_timeout"], use_ai=False) for _ in range(5)]
    first = runs[0].to_dict()
    for other in runs[1:]:
        assert other.to_dict() == first


def test_the_narrative_is_decoration_not_data():
    """Deleting the prose must leave every decision intact."""
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    inv.narrative = ""
    d = inv.to_dict()
    assert d["layer"] == "GatewayTimeout"
    assert d["confidence"]["band"] == "Medium"
    assert d["runbook"]["fix"]
    assert d["timing"]["projected_seconds"] > 90
