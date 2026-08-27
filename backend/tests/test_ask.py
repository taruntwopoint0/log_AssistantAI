"""Ask the Diagnosis: the graph, the controlled lookups, and the grounding.

The tests that matter here are the negative ones. Anyone can make a chatbot
answer; the question is whether it refuses when it should, and whether the model
can reach anything it was not handed.
"""

from __future__ import annotations

import pytest

from engine import query_assistant as qa
from engine.graph import CURRENT, attach_investigation, build_static_graph
from engine.knowledge import load_config
from engine.pipeline import investigate
from engine.query_tools import TOOLS, DiagnosisContext, run_tools
from gen_mock_logs import SCENARIOS


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def static_graph(cfg):
    return build_static_graph(cfg)


def _ctx(sample: str, cfg, static_graph) -> DiagnosisContext:
    inv = investigate(SCENARIOS[sample], use_ai=False).to_dict()
    inv["prediction_id"] = "test"
    return DiagnosisContext(
        investigation=inv,
        graph=attach_investigation(static_graph, inv, cfg["topology"]),
        topology=cfg["topology"], runbooks=cfg["runbooks"], incidents=cfg["incidents"],
    )


@pytest.fixture
def gateway(cfg, static_graph):
    return _ctx("gateway_timeout", cfg, static_graph)


@pytest.fixture
def unknown(cfg, static_graph):
    return _ctx("unrecognised", cfg, static_graph)


# --------------------------------------------------------------------------
# Graph
# --------------------------------------------------------------------------

def test_graph_is_built_entirely_from_config(static_graph, cfg):
    assert static_graph.nodes and static_graph.edges
    teams = {n.label for n in static_graph.nodes.values() if n.type == "Team"}
    configured = {l["owner"] for l in cfg["topology"]["layers"] if l.get("owner")}
    assert configured <= teams, "a team appeared that config never declared"


def test_no_dangling_edges(static_graph):
    for e in static_graph.edges:
        assert e.src in static_graph.nodes
        assert e.dst in static_graph.nodes


def test_owner_comes_from_a_graph_walk_not_a_lookup(gateway):
    """Incident -> CLASSIFIED_AS -> Layer -> OWNED_BY -> Team."""
    teams, path = gateway.graph.walk(CURRENT, ["CLASSIFIED_AS", "OWNED_BY"])
    assert [t.label for t in teams] == ["Network / API Gateway team"]
    assert path == ["This investigation", "CLASSIFIED_AS", "OWNED_BY"]


def test_the_current_investigation_is_attached_to_the_graph(gateway):
    rels = {r["rel"] for r in gateway.graph.relations(CURRENT)}
    assert {"CLASSIFIED_AS", "AFFECTS", "HAS_EVIDENCE", "ELIMINATES",
            "SIMILAR_TO", "USES_RUNBOOK"} <= rels


def test_attaching_an_investigation_does_not_mutate_the_static_graph(cfg, static_graph):
    before = len(static_graph.nodes)
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False).to_dict()
    attach_investigation(static_graph, inv, cfg["topology"])
    assert len(static_graph.nodes) == before


def test_walk_returns_empty_rather_than_guessing(gateway):
    nodes, _ = gateway.graph.walk(CURRENT, ["CLASSIFIED_AS", "NOT_A_REAL_RELATION"])
    assert nodes == []


# --------------------------------------------------------------------------
# Controlled lookups
# --------------------------------------------------------------------------

def test_every_registered_tool_runs_on_the_production_case(gateway):
    for name in TOOLS:
        result = run_tools([name], gateway)[0]
        assert result.tool == name
        assert result.ok or result.note, f"{name} failed silently"


def test_a_successful_tool_always_carries_provenance(gateway):
    for r in run_tools(list(TOOLS), gateway):
        if r.ok:
            assert r.source, f"{r.tool} returned data with no source"


def test_unknown_tool_names_are_dropped_never_executed(gateway):
    results = run_tools(["get_owner", "drop_database", "../../etc/passwd", "eval"], gateway)
    assert [r.tool for r in results] == ["get_owner"]


def test_tools_report_unavailable_rather_than_guessing(unknown):
    """The unrecognised log has no layer, so no owner and no precedent exist."""
    owner = run_tools(["get_owner"], unknown)[0]
    assert owner.ok is False
    assert "no owning team" in owner.note.lower()

    related = run_tools(["find_related_incidents"], unknown)[0]
    assert related.ok is False

    elim = run_tools(["get_eliminated_layers"], unknown)[0]
    assert elim.ok is False


def test_diagnosis_tool_reports_the_decline_honestly(unknown):
    d = run_tools(["get_diagnosis"], unknown)[0]
    assert d.ok is True
    assert d.data["layer"] == "Unknown"
    assert d.data["declined"] is True


def test_a_broken_tool_cannot_take_down_the_chat(gateway, monkeypatch):
    def boom(ctx):
        raise RuntimeError("bad config")
    monkeypatch.setitem(TOOLS, "get_owner", boom)
    r = run_tools(["get_owner"], gateway)[0]
    assert r.ok is False and "Tool failed" in r.note


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------

@pytest.mark.parametrize("question,expected", [
    ("Which team owns this?", "get_owner"),
    ("Which application is affected?", "get_application"),
    ("Why is confidence only Medium?", "get_confidence_explanation"),
    ("Have we seen this before?", "find_related_incidents"),
    ("What fixed it last time?", "get_previous_resolution"),
    ("What should I check next?", "get_next_checks"),
    ("What should I not do?", "get_what_not_to_do"),
    ("How long did it take before it failed?", "get_timing"),
])
def test_the_briefs_questions_route_without_a_model(question, expected):
    assert expected in qa.keyword_match(question)


def test_routing_is_deterministic():
    q = "Which team owns this?"
    assert qa.keyword_match(q) == qa.keyword_match(q)


def test_the_model_is_not_consulted_when_keywords_match(monkeypatch):
    monkeypatch.setattr(qa, "_call_model",
                        lambda *a, **k: pytest.fail("model called unnecessarily"))
    tools, selector = qa.select_tools("Which team owns this?", "fake-key")
    assert selector == "keywords" and "get_owner" in tools


def test_a_model_inventing_a_tool_name_gets_it_dropped():
    assert qa._parse_tool_list('["get_owner", "exfiltrate_secrets"]') == ["get_owner"]
    assert qa._parse_tool_list('["rm -rf /"]') == []


def test_tool_list_parsing_survives_fences_and_prose():
    assert qa._parse_tool_list('```json\n["get_owner"]\n```') == ["get_owner"]
    assert qa._parse_tool_list('Sure! ["get_timing"] should do it.') == ["get_timing"]
    assert qa._parse_tool_list("not json at all") == []


# --------------------------------------------------------------------------
# Grounding
# --------------------------------------------------------------------------

def test_project_mode_works_with_no_model_at_all(gateway, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    a = qa.ask("Which team owns this?", "PROJECT", gateway)
    assert a.grounded is True
    assert a.model_used is False
    assert "Network / API Gateway team" in a.answer


def test_project_mode_refuses_without_an_investigation(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    a = qa.ask("Who owns this?", "PROJECT", None)
    assert "Run an investigation first" in a.answer
    assert a.tools_used == []


def test_project_mode_says_so_when_the_lookups_are_empty(unknown, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    a = qa.ask("Which team owns this?", "PROJECT", unknown)
    assert "don't have sufficient project evidence" in a.answer.lower()


def test_the_model_only_ever_receives_tool_output(gateway, monkeypatch):
    """The raw log must never reach the conversational prompt."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    captured: list[str] = []

    def capture(prompt, key, max_tokens=2000):
        captured.append(prompt)
        return "ok"

    monkeypatch.setattr(qa, "_call_model", capture)
    qa.ask("Why did you classify this as GatewayTimeout?", "PROJECT", gateway)

    assert captured
    prompt = captured[-1]
    assert "FetchGalileoApi.cs" not in prompt
    assert "--- End of inner exception stack trace ---" not in prompt
    assert gateway.inv["facts"]["error_text"] not in prompt


def test_internal_identifiers_are_withheld_from_the_chat_prompt(gateway, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    captured: list[str] = []
    monkeypatch.setattr(qa, "_call_model",
                        lambda p, k, max_tokens=2000: captured.append(p) or "ok")
    qa.ask("What fixed it last time?", "PROJECT", gateway)
    assert "gateway.suppliersync.internal" not in captured[-1]


def test_general_mode_is_given_no_project_facts(gateway, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    captured: list[str] = []
    monkeypatch.setattr(qa, "_call_model",
                        lambda p, k, max_tokens=2000: captured.append(p) or "ok")
    a = qa.ask("What is an HTTP 504?", "GENERAL", gateway)

    prompt = captured[-1]
    assert "GatewayTimeout" not in prompt
    assert "VERIFIED FACTS" not in prompt
    assert a.grounded is False
    assert a.tools_used == []


def test_a_model_failure_degrades_to_verified_facts(gateway, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")

    def boom(prompt, key, max_tokens=2000):
        raise RuntimeError("429 quota exhausted")

    monkeypatch.setattr(qa, "_call_model", boom)
    a = qa.ask("Which team owns this?", "PROJECT", gateway)
    assert a.grounded is True
    assert a.model_used is False
    assert "Network / API Gateway team" in a.answer
    assert "429" in a.error, "the reason must be surfaced, not swallowed"


def test_the_conversation_cannot_change_the_diagnosis(gateway, monkeypatch):
    """Whatever the model says, the investigation is untouched."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(
        qa, "_call_model",
        lambda p, k, max_tokens=2000:
            "Actually the root cause is GalileoDown and confidence is High.",
    )
    before = dict(gateway.inv)
    qa.ask("Is this really a gateway problem?", "PROJECT", gateway)
    assert gateway.inv["layer"] == before["layer"] == "GatewayTimeout"
    assert gateway.inv["confidence"]["band"] == "Medium"
    assert gateway.inv["eliminated"] == before["eliminated"]


def test_empty_question_is_handled(gateway):
    a = qa.ask("   ", "PROJECT", gateway)
    assert a.answer
    assert a.tools_used == []


def test_mode_defaults_to_project_on_junk_input(gateway, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert qa.ask("Who owns this?", "nonsense", gateway).mode == "PROJECT"
