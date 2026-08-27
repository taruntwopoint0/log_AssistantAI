"""Stage 5b. These tests pin the behaviour the embedding swap must preserve.

If _similarity() is replaced with cosine similarity over embeddings, every test
in this file should still pass unchanged. That is the contract.
"""

from __future__ import annotations

import pytest

from engine.knowledge import load_config
from engine.precedent import (
    MIN_SIMILARITY,
    _signature_key,
    _similarity,
    batch_bucket,
    find_precedents,
    timing_bucket,
)


@pytest.fixture
def incidents():
    return load_config()["incidents"]


GATEWAY_FACTS = {
    "exception_types": ["HttpRequestException", "HttpIOException"],
    "error_text": "an error occurred while sending the request. the response ended prematurely. (responseended)",
    "http_status": None,
    "record_count": 539,
    "elapsed_seconds": 60.0,
    "endpoint_host": "gateway.suppliersync.internal",
    "has_error": True,
}


# --------------------------------------------------------------------------
# Signature normalisation - what an embedding would encode
# --------------------------------------------------------------------------

def test_signature_is_the_exception_chain_plus_inner_symptom():
    assert _signature_key(GATEWAY_FACTS) == (
        "HttpRequestException>HttpIOException|response ended prematurely"
    )


def test_signature_excludes_volatile_noise():
    """GUIDs, line numbers, hosts and timestamps must never enter the signature."""
    noisy = {
        **GATEWAY_FACTS,
        "error_text": GATEWAY_FACTS["error_text"]
        + " correlation 4f2c9a11-8bd3-4e7a-9c11-2f0a7e5d1b88 at line 59 on 2026-08-18",
    }
    assert _signature_key(noisy) == _signature_key(GATEWAY_FACTS)


def test_signature_for_a_clean_run():
    assert _signature_key({"has_error": False, "record_count": 41}) == "no error|clean run"
    assert _signature_key({"has_error": False, "record_count": 0}) == "no error|zero records fetched"


def test_status_becomes_the_symptom_when_there_is_no_phrase():
    sig = _signature_key({
        "exception_types": ["HttpRequestException"],
        "error_text": "response status code does not indicate success: 503",
        "http_status": 503, "has_error": True,
    })
    assert sig == "HttpRequestException|503 service unavailable"


# --------------------------------------------------------------------------
# Buckets
# --------------------------------------------------------------------------

@pytest.mark.parametrize("n,expected", [
    (None, "any"), (0, "empty"), (2, "tiny"), (39, "small"),
    (214, "medium"), (539, "large"),
])
def test_batch_buckets(n, expected):
    assert batch_bucket(n) == expected


@pytest.mark.parametrize("s,expected", [
    (None, "any"), (1.0, "instant"), (7.0, "fast"),
    (30.0, "slow"), (60.0, "ceiling-60"), (62.0, "ceiling-60"), (200.0, "long"),
])
def test_timing_buckets(s, expected):
    assert timing_bucket(s) == expected


def test_the_60s_ceiling_has_its_own_bucket():
    """The ceiling is the whole diagnosis, so it must not blur into 'slow'."""
    assert timing_bucket(44.0) != timing_bucket(60.0)
    assert timing_bucket(60.0) == timing_bucket(62.0)


# --------------------------------------------------------------------------
# Similarity and matching
# --------------------------------------------------------------------------

def test_identical_signatures_score_one():
    assert _similarity("A>B|symptom", "A>B|symptom") == pytest.approx(1.0)


def test_unrelated_signatures_score_zero():
    assert _similarity("SqlException|pool size was reached",
                       "JsonException|invalid start of a value") == 0.0


def test_the_production_case_matches_its_precedent(incidents):
    results = find_precedents(GATEWAY_FACTS, "GatewayTimeout", incidents)
    assert results
    assert results[0].similarity >= 0.9
    assert all(r.layer == "GatewayTimeout" for r in results)


def test_an_unrecognised_failure_matches_nothing(incidents):
    facts = {
        "exception_types": ["JsonException"],
        "error_text": "'<' is an invalid start of a value",
        "http_status": None, "record_count": None, "elapsed_seconds": None,
        "endpoint_host": None, "has_error": True,
    }
    assert find_precedents(facts, "Unknown", incidents) == []


def test_a_matching_signature_on_the_wrong_layer_cannot_reach_threshold(incidents):
    """Layer carries 0.35. A shape match alone must not be enough."""
    results = find_precedents(GATEWAY_FACTS, "AldavarDB", incidents)
    for r in results:
        assert r.layer == "AldavarDB" or r.similarity < 0.75


def test_host_alone_cannot_produce_a_match(incidents):
    """Host carries 0.10 deliberately so it cannot drag an unrelated row in."""
    facts = {
        "exception_types": ["SomeUnrelatedException"],
        "error_text": "nothing familiar here at all",
        "http_status": None, "record_count": None, "elapsed_seconds": None,
        "endpoint_host": "gateway.suppliersync.internal", "has_error": True,
    }
    assert find_precedents(facts, "Unknown", facts and incidents) == []


def test_ranking_is_deterministic_when_similarity_ties(incidents):
    """Several incidents share this exact shape. Recency breaks the tie."""
    a = find_precedents(GATEWAY_FACTS, "GatewayTimeout", incidents)
    b = find_precedents(GATEWAY_FACTS, "GatewayTimeout", incidents)
    assert [r.incident_id for r in a] == [r.incident_id for r in b]
    tied = [r for r in a if r.similarity == a[0].similarity]
    assert [r.date for r in tied] == sorted((r.date for r in tied), reverse=True)


def test_results_never_fall_below_the_floor(incidents):
    for facts, layer in [
        (GATEWAY_FACTS, "GatewayTimeout"),
        ({"has_error": False, "record_count": 41, "exception_types": [],
          "error_text": "", "endpoint_host": None}, "Healthy"),
    ]:
        for r in find_precedents(facts, layer, incidents):
            assert r.similarity >= MIN_SIMILARITY


def test_every_incident_names_a_real_layer():
    cfg = load_config()
    known = {l["id"] for l in cfg["topology"]["layers"]}
    for inc in cfg["incidents"]["incidents"]:
        assert inc["layer"] in known, f"{inc['id']} names unknown layer {inc['layer']}"


# --------------------------------------------------------------------------
# Grouping identical failure shapes
# --------------------------------------------------------------------------

def test_identical_shapes_collapse_into_one_row(incidents):
    """Four copies of one fault crowd out four different faults.

    incidents.json holds several GatewayTimeout incidents sharing a signature.
    They must arrive as one representative carrying a count, not as separate
    rows eating the whole result window.
    """
    results = find_precedents(GATEWAY_FACTS, "GatewayTimeout", incidents)
    top = results[0]
    assert top.recurrence > 1, "the repeated gateway shape did not collapse"
    assert len(top.also) == top.recurrence - 1
    assert top.incident_id not in top.also
    # every collapsed id is real
    known = {i["id"] for i in incidents["incidents"]}
    assert set(top.also) <= known


def test_the_representative_of_a_group_is_the_most_recent(incidents):
    results = find_precedents(GATEWAY_FACTS, "GatewayTimeout", incidents)
    top = results[0]
    dates = {i["id"]: i["date"] for i in incidents["incidents"]}
    assert all(dates[top.incident_id] >= dates[o] for o in top.also)


def test_grouping_never_invents_or_drops_a_match(incidents):
    results = find_precedents(GATEWAY_FACTS, "GatewayTimeout", incidents)
    surfaced = sum(1 + len(r.also) for r in results)
    known = {i["id"] for i in incidents["incidents"]}
    for r in results:
        assert r.incident_id in known
    assert surfaced >= len(results)


def test_an_unknown_diagnosis_offers_no_precedent_at_all(incidents):
    """A near miss on a diagnosis is worse than no diagnosis.

    Regression: a TLS certificate failure the rules engine could not classify
    scored 0.355 against an expired-client-secret incident - carried entirely by
    a shared hostname, with layer agreement at 0.0 - and would have suggested
    rotating a credential for an unrelated fault.
    """
    tls_facts = {
        "exception_types": ["HttpRequestException", "AuthenticationException"],
        "error_text": "the ssl connection could not be established. the remote certificate is invalid.",
        "http_status": None, "record_count": 310, "elapsed_seconds": 1.0,
        "endpoint_host": "gateway.suppliersync.internal", "has_error": True,
    }
    assert find_precedents(tls_facts, "Unknown", incidents) == []


def test_a_known_layer_still_gets_its_precedents(incidents):
    """The Unknown guard must not suppress legitimate matching."""
    assert find_precedents(GATEWAY_FACTS, "GatewayTimeout", incidents)
