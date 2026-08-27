"""Stage 7 containment: what may and may not leave the machine.

The claim these tests defend is deliberately narrow. Internal hostnames, IPs,
incident ids and team names never reach the model. System and layer names do.
Do not widen the claim without widening the tests.
"""

from __future__ import annotations

import pytest

from engine import writer
from engine.knowledge import load_config
from engine.pipeline import investigate
from engine.redaction import Redactor
from gen_mock_logs import SCENARIOS

INTERNAL_HOST = "gateway.suppliersync.internal"


@pytest.fixture
def topology():
    return load_config()["topology"]


@pytest.fixture
def payload(topology):
    inv = investigate(SCENARIOS["gateway_timeout"], use_ai=False)
    p = inv.to_dict()
    p["system"] = topology["system"]
    return p


@pytest.fixture
def prompt(payload):
    return writer._build_prompt(payload)


@pytest.fixture
def redactor(payload, topology, prompt):
    return Redactor.from_payload(payload, topology, scan_text=prompt)


# --------------------------------------------------------------------------
# The core guarantee
# --------------------------------------------------------------------------

def test_the_internal_host_never_appears_in_the_outbound_prompt(redactor, prompt):
    assert INTERNAL_HOST in prompt, "fixture is wrong if the host was not there to begin with"
    assert INTERNAL_HOST not in redactor.redact(prompt)


def test_no_configured_identifier_survives_redaction(redactor, prompt):
    assert redactor.leaked(redactor.redact(prompt)) == []


@pytest.mark.parametrize("name", list(SCENARIOS), ids=list(SCENARIOS))
def test_every_scenario_leaves_no_identifier_behind(name, topology):
    inv = investigate(SCENARIOS[name], use_ai=False)
    p = inv.to_dict()
    p["system"] = topology["system"]
    raw = writer._build_prompt(p)
    r = Redactor.from_payload(p, topology, scan_text=raw)
    assert r.leaked(r.redact(raw)) == []


def test_the_raw_log_is_never_in_the_prompt(prompt):
    """Only derived summaries are sent. Stack traces stay local."""
    assert "FetchGalileoApi.cs" not in prompt
    assert "at System.Net.Http.HttpConnection" not in prompt
    assert "--- End of inner exception stack trace ---" not in prompt


def test_error_text_is_never_in_the_prompt(payload, prompt):
    """facts.error_text holds the raw lowercased exception body. It must not go."""
    assert payload["facts"]["error_text"]
    assert payload["facts"]["error_text"] not in prompt


# --------------------------------------------------------------------------
# Round trip
# --------------------------------------------------------------------------

def test_restore_is_the_exact_inverse_of_redact(redactor, prompt):
    assert redactor.restore(redactor.redact(prompt)) == prompt


def test_restore_tolerates_a_model_changing_token_case(redactor):
    if not redactor.redactions:
        pytest.skip("nothing redacted")
    tok = redactor.redactions[0]
    assert tok.value in redactor.restore(f"see {tok.token.lower()} for detail")


def test_a_dropped_token_is_not_an_error(redactor):
    assert redactor.restore("the model ignored every placeholder") == (
        "the model ignored every placeholder"
    )


def test_tokens_are_unique(redactor):
    tokens = [r.token for r in redactor.redactions]
    assert len(tokens) == len(set(tokens))


def test_longer_values_are_replaced_first(topology):
    """A short value must not eat part of a longer one."""
    p = {"runbook": {"escalate_to": "x"},
         "precedents": [],
         "_t": "host a.b.internal and sub.a.b.internal both appear"}
    text = p["_t"]
    r = Redactor.from_payload(p, topology, scan_text=text)
    out = r.redact(text)
    assert "internal" not in out
    assert r.restore(out) == text


# --------------------------------------------------------------------------
# Config drives it, like everything else
# --------------------------------------------------------------------------

def test_redaction_can_be_switched_off_in_config(payload, topology, prompt):
    off = {**topology, "redaction": {**topology["redaction"], "enabled": False}}
    r = Redactor.from_payload(payload, off, scan_text=prompt)
    assert r.redactions == []
    assert r.redact(prompt) == prompt


def test_categories_are_individually_configurable(payload, topology, prompt):
    only_hosts = {**topology, "redaction": {
        **topology["redaction"],
        "redact_owners": False, "redact_incident_ids": False, "redact_ips": False,
    }}
    r = Redactor.from_payload(payload, only_hosts, scan_text=prompt)
    assert {x.kind for x in r.redactions} == {"host"}


def test_the_map_only_covers_what_is_actually_being_sent(redactor, prompt):
    """No token for an identifier that never entered the prompt."""
    for r in redactor.redactions:
        assert r.value in prompt


# --------------------------------------------------------------------------
# writer.write contract
# --------------------------------------------------------------------------

def test_no_key_means_no_prompt_is_built_or_sent(payload, topology, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    text, source, meta = writer.write(payload, topology)
    assert source == "template"
    assert meta["prompt_sent"] is None
    assert meta["redactions"] == []


def test_the_prompt_recorded_as_sent_is_the_redacted_one(payload, topology, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(writer, "_call_gemini", lambda p, k: "<HOST_1> was cut at 60s.")
    text, source, meta = writer.write(payload, topology)
    assert source == "gemini"
    assert meta["leak_check_passed"] is True
    assert INTERNAL_HOST not in meta["prompt_sent"]
    # ...but the user still sees the real host, restored locally
    assert INTERNAL_HOST in text


def test_a_model_failure_falls_back_without_losing_the_audit_trail(payload, topology, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")

    def boom(prompt, key):
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr(writer, "_call_gemini", boom)
    text, source, meta = writer.write(payload, topology)
    assert source == "template"
    assert text.strip()
    assert meta["redactions"], "the audit trail must survive a model failure"


def test_a_failed_leak_check_blocks_the_send_entirely(payload, topology, monkeypatch):
    """If anything survives the map, send nothing rather than leak."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")

    called = []
    monkeypatch.setattr(writer, "_call_gemini",
                        lambda p, k: called.append(p) or "should not happen")
    # A redactor that finds the host but refuses to replace it.
    monkeypatch.setattr(Redactor, "redact", lambda self, text: text)

    text, source, meta = writer.write(payload, topology)
    assert called == [], "the prompt must not be sent when the leak check fails"
    assert source == "template"
    assert meta["leak_check_passed"] is False
    assert meta["prompt_sent"] is None
    assert INTERNAL_HOST in meta["blocked_identifiers"]
